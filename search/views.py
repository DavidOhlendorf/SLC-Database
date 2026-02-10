import re
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from django.db.models import Q, F, Prefetch
from django.db.models.functions import Lower

from django.core.paginator import Paginator
from django.contrib.postgres.search import TrigramSimilarity, SearchQuery, SearchRank, SearchVector, TrigramWordSimilarity

from collections import defaultdict
from questions.models import Question, Keyword
from variables.models import Variable, QuestionVariableWave
from waves.models import Wave, Survey

ALLOWED_TYPES = {"all", "questions", "variables", "constructs"}
ALLOWED_SORTS = {"relevance", "alpha"}
RESULTS_PER_PAGE = 20


# Hilfsfunktion: Suche nach Fragen (für Hauptsuche und für API-Endpunkt)
# Später evtl. auslagern in search/utils.py und für Vars erweitern (aktuell nicht einheitlich)
def search_questions(q: str, wave_ids=None, include_keywords=True):
    """
    Search for questions using full-text search, trigram similarity, and keyword matching.
    
    Args:
        q: Search query string
        wave_ids: Optional list of wave IDs to filter results
        include_keywords: Whether to include keyword-based matching in the search
        
    Returns:
        Tuple of (found_questions_list, score_map_dict)
    """
    q = (q or "").strip()
    if len(q) < 2:
        return [], {}

    q_lower = q.lower()
    wave_ids = wave_ids or []

    # Basis-QuerySet nur mit Wellen-Filter
    base_qs_q = Question.objects.all()
    if wave_ids:
        base_qs_q = base_qs_q.filter(waves__id__in=wave_ids)

    # ---- 1) Volltextsuche (tsvector) mit deutschem Analyzer
    ts_query = SearchQuery(q, config="german", search_type="websearch")
    ts_rows = (
        base_qs_q
        .annotate(sv=SearchVector("questiontext", weight="A", config="german"))
        .filter(sv=ts_query)
        .annotate(ts_rank=SearchRank(F("sv"), ts_query, normalization=32))
        .values("id", "ts_rank")
    )
    ts_map = {r["id"]: float(r["ts_rank"] or 0.0) for r in ts_rows}

    # ---- 2) Trigram-Suche im Fragetext (Fuzzy-Fallback) für Tippfehler/Teilstrings
    tg_rows = (
        base_qs_q
        .annotate(sim=TrigramWordSimilarity(q_lower, "questiontext"))
        .filter(sim__gt=0.6) # Mindestähnlichkeit
        .values("id", "sim")
    )
    tg_map = {r["id"]: float(r["sim"] or 0.0) for r in tg_rows}

    # ---- 3) Wortgrenzen-Boost: wenn der Suchbegriff als eigenes Wort im Text steht
    word_boundary = rf"\m{re.escape(q_lower)}\M"
    wb_ids = set(
        base_qs_q
        .annotate(qt=Lower("questiontext"))
        .filter(qt__iregex=word_boundary)
        .values_list("id", flat=True)
    )

    # ---- 4) Keyword-Score: bestes passendes Keyword (entweder direkter Treffer per contains oder fuzzy per trgm)
    kw_map = {}
    if include_keywords:
        kw_rows = (
            Keyword.objects
            .annotate(nl=Lower("name"))
            .annotate(sim=TrigramSimilarity(F("nl"), q_lower))
            .filter(Q(nl__istartswith=q_lower) | Q(sim__gt=0.6))
            .values("id", "sim")[:15]
        )
        kw_id_to_score = {r["id"]: float(r["sim"] or 0.0) for r in kw_rows}

        # Hole die zu den keywords aus kw_id_to_score gehörenden Fragen
        kw_links = (
            base_qs_q
            .filter(keywords__in=list(kw_id_to_score.keys()))
            .values("id", "keywords__id")
            .distinct()
        )

        # SearchMap: FrageID -> bestes Keyword-Score
        kw_map = {}
        for r in kw_links:
            qid = r["id"]; kwid = r["keywords__id"]
            kw_map[qid] = max(kw_map.get(qid, 0.0), kw_id_to_score.get(kwid, 0.0))


    # ---- 5) Finaler Score pro Frage aus den Einzelkomponenten
    #   Logik:
    #     Textscore = max(TS, TG*0.6, WB*0.95)
    #     Score aus dem Fragetext wird gebildet aus dem höchsten Wert der drei Komponenten:
    #       - Volltext-Score per ts_vector (TS) 
    #       - Trigram-Score (TG), aber nur 60% Gewicht, damit Textrelevanz höher gewichtet wird
    #       - Wortgrenzen-Bonus (WB), fester Wert 0.95 --> bei direktem Worttreffer im Fragetext wird geboostet
    #     Keyword-Score (KW) = bestes Keyword * 0.8
    #     Bestes Keyword (entweder direkter Treffer oder fuzzy) bekommt 80% Gewicht, damit Fragetext-Relevanz höher gewichtet wird
    #     Finaler Score = Textscore + Keyword-Score * 0.15 (wenn Textscore > 0) bzw. + Keyword-Score * 0.10 (wenn kein Textscore)
    #     Falls beide Scores > 0 sind, wird ein Bonus von +0.15 vergeben (max. 1.2 insgesamt), damit Fragen mit sowohl Text- als auch Keyword-Treffern bevorzugt werden.

    candidate_ids = set(ts_map) | set(tg_map) | wb_ids | (set(kw_map) if include_keywords else set())
    if not candidate_ids:
        return [], {}

    final_score_map = {}
    for qid in candidate_ids:
        ts = ts_map.get(qid, 0.0)
        tg = tg_map.get(qid, 0.0) * 0.6
        wb = 0.95 if qid in wb_ids else 0.0
        text_score = max(ts, tg, wb)

        if include_keywords:
            kw_score = kw_map.get(qid, 0.0) * 0.8
            both = (text_score > 0.0 and kw_score > 0.0)
            if text_score > 0:
                relevance = text_score + 0.15 * kw_score
            else:
                relevance = 0.10 * kw_score 
            if both:
                relevance = min(1.2, relevance + 0.15)
        else:
            relevance = text_score

        final_score_map[qid] = relevance

     # ---- 6) Materialisieren, Facetten zählen, sortieren, paginieren
    found = list(
        base_qs_q
        .filter(id__in=final_score_map.keys())
        .only("id", "questiontext")
        .prefetch_related(Prefetch("waves", queryset=Wave.objects.select_related("survey")))
        .distinct()
    )

    return found, final_score_map


# Landing-Page für die Suche
def search_landing(request):
    """
    Render the search landing page.
    """
    return render(request, "search/landing.html")

# Paginierungs-Hilfsfunktionen
def paginate_list(items, request, per_page=RESULTS_PER_PAGE):
    """
    Paginierung für bereits materialisierte Python-Listen.
    """
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj

# Paginierung für QuerySets
def paginate_queryset(qs, request, per_page=RESULTS_PER_PAGE):
    """
    klassische Paginierung für QuerySets in den Constructs.
    """
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj


def search(request):
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("search:search_landing")

    search_type = (request.GET.get("type") or "all").lower()
    if search_type not in ALLOWED_TYPES:
        search_type = "all"

    sort = (request.GET.get("sort") or "relevance").lower()
    if sort not in ALLOWED_SORTS:
        sort = "relevance"

    # Wellen-Filter
    wave_ids = []
    try:
        wave_ids = [int(x) for x in request.GET.getlist("waves") if x.strip().isdigit()]
    except Exception:
        wave_ids = []
    
    # Für Auswahl + Chips
    all_waves = Wave.objects.select_related("survey").order_by(
        F("survey__year").desc(nulls_last=True),
        "survey__name",
        "cycle",
        "instrument",
        "id",
    )
    selected_waves = list(all_waves.filter(id__in=wave_ids)) if wave_ids else []

    ctx = {
        "q": q,
        "type": search_type,
        "sort": sort,
        "has_query": True,
        "TOP_N": 5,
        "tabs": [
            ("all", "Alle"),
            ("questions", "Fragen"),
            ("variables", "Variablen"),
        ],
        "all_waves": all_waves,
        "selected_waves": selected_waves,
        "selected_wave_ids": [w.id for w in selected_waves],
        "show_relevance": settings.DEBUG, # Debug: show Relevance-Scores
    }

    # Für Facetten: Zähler und Set
    facet_counter = defaultdict(int)
    facet_waves_set = set()



    # =========================
    # QUESTIONS 
    # =========================
    if search_type in {"all", "questions"}:
        questions_found, final_score_map = search_questions(
        q=q,
        wave_ids=wave_ids,
        include_keywords=True,
        )

        if sort == "alpha":
            questions_sorted = sorted(
                questions_found,
                key=lambda obj: (obj.questiontext or "").lower()
            )
        else:
            questions_sorted = sorted(
                questions_found,
                key=lambda obj: final_score_map.get(obj.id, 0.0),
                reverse=True
            )

        # Facetten-Zähler
        for obj in questions_found:
            for w in obj.waves.all():
                facet_counter[w.id] += 1
                facet_waves_set.add(w)

        # Debug/Anzeige
        for obj in questions_sorted:
            obj.relevance = final_score_map.get(obj.id, 0.0)

        if search_type == "all":
            ctx["questions"] = questions_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(questions_sorted, request)
            ctx["questions_page"] = page_obj
            ctx["questions"] = page_obj.object_list

        ctx["questions_count"] = len(questions_sorted)
        ctx.setdefault("questions_count", 0)


    # =========================
    # VARIABLES
    # =========================

    if search_type in {"all", "variables"}:
        q_lower = q.lower()

        # Basis-QuerySet der Variablen inkl. optionalem Wellenfilter
        base_qs_v = Variable.objects.all()
        if wave_ids:
            base_qs_v = base_qs_v.filter(waves__id__in=wave_ids)

        # ---- 1) Volltext (tsvector) auf varlab
        ts_query_v = SearchQuery(q, config="german", search_type="websearch")
        ts_rows_v = (
            base_qs_v
            .annotate(sv=SearchVector("varlab", weight="A", config="german"))
            .filter(sv=ts_query_v)
            .annotate(ts_rank=SearchRank(F("sv"), ts_query_v, normalization=32))
            .values("id", "ts_rank")
        )
        ts_map_v = {r["id"]: float(r["ts_rank"] or 0.0) for r in ts_rows_v}

        # ---- 2) Trigram (Fuzzy) auf varlab (Tippfehler/Teilstrings)
        tg_rows_v = (
            base_qs_v
            .annotate(sim=TrigramWordSimilarity(q_lower, "varlab"))
            .filter(sim__gt=0.6)
            .values("id", "sim")
        )
        tg_map_v = {r["id"]: float(r["sim"] or 0.0) for r in tg_rows_v}


        # ---- 3) Wortgrenzen-Boost auf varlab
        word_boundary = rf"\m{re.escape(q_lower)}\M"
        wb_ids_v = set(
            base_qs_v
            .annotate(vl=Lower("varlab"))
            .filter(vl__iregex=word_boundary)
            .values_list("id", flat=True)
        )

        # ---- 4) Varname: nur Prefix-Match (keine Fuzzy/Volltext)
        vn_rows = (
            base_qs_v
            .annotate(vn=Lower("varname"))
            .filter(vn__startswith=q_lower)
            .values_list("id", "vn")
        )

        # fester Bonus für Prefix
        vn_map = {}
        for vid, vn in vn_rows:
            score = 1.0
            if vn == q_lower:
                score = 1.05
            vn_map[vid] = max(vn_map.get(vid, 0.0), score)


        # ---- 5) Keywords
        kw_rows_v = (
            Keyword.objects
            .annotate(nl=Lower("name"))
            .annotate(sim=TrigramSimilarity(F("nl"), q_lower))
            .filter(Q(nl__istartswith=q_lower) | Q(sim__gt=0.6))
            .values("id", "sim")[:15]
        )
        kw_id_to_score_v = {r["id"]: float(r["sim"] or 0.0) for r in kw_rows_v}

        if kw_id_to_score_v:
            var_kw_links = (
                QuestionVariableWave.objects
                .filter(
                    variable__in=base_qs_v,
                    question__keywords__in=list(kw_id_to_score_v.keys()),
                )
                .values("variable_id", "question__keywords__id")
                .distinct()
            )
        else:
            var_kw_links = []


        kw_map_v = {}
        for r in var_kw_links:
            vid = r["variable_id"]
            kwid = r["question__keywords__id"]
            kw_score = kw_id_to_score_v.get(kwid, 0.0)
            kw_map_v[vid] = max(kw_map_v.get(vid, 0.0), kw_score)

        # ---- 6) Finaler Score pro Frage aus den Einzelkomponenten
        #   Logik:
        #     Textscore = max(TS, TG*0.6, WB*0.95)
        #     Score aus dem Variablenlabel wird gebildet aus dem höchsten Wert der vier Komponenten:
        #       - Volltext-Score per ts_vector (TS) 
        #       - Trigram-Score (TG), aber nur 60% Gewicht, damit Textrelevanz höher gewichtet wird
        #       - Wortgrenzen-Bonus (WB), fester Wert 0.95 --> bei direktem Worttreffer im Fragetext wird geboostet
        #       - Varname-Prefix-Bonus (VN), fester Wert 1.0 bzw. 1.05 bei exaktem Treffer
        #     Keyword-Score (KW) = bestes Keyword * 0.8
        #     Bestes Keyword (entweder direkter Treffer oder fuzzy) bekommt 80% Gewicht, damit Varlabel-Relevanz höher gewichtet wird
        #     Finaler Score = Textscore + Keyword-Score * 0.15 (wenn Textscore > 0) bzw. + Keyword-Score * 0.10 (wenn kein Textscore)
        #     Falls beide Scores > 0 sind, wird ein Bonus von +0.15 vergeben (max. 1.2 insgesamt), damit Fragen mit sowohl Text- als auch Keyword-Treffern bevorzugt werden.

        candidate_ids_v = set(ts_map_v) | set(tg_map_v) | wb_ids_v | set(vn_map) | set(kw_map_v)
        final_var_score_map = {}
        for vid in candidate_ids_v:
            ts = ts_map_v.get(vid, 0.0)
            tg = tg_map_v.get(vid, 0.0) * 0.6
            wb = 0.95 if vid in wb_ids_v else 0.0
            vn = vn_map.get(vid, 0.0)    
            text_score = max(ts, tg, wb, vn)

            kw_score = kw_map_v.get(vid, 0.0) * 0.8
            both = (text_score > 0.0 and kw_score > 0.0)

            if text_score > 0:
                relevance = text_score + 0.15 * kw_score
            else:
                relevance = 0.10 * kw_score 

            if both:
                relevance = min(1.2, relevance + 0.15)

            final_var_score_map[vid] = relevance

        # ---- 7) Materialisieren, Facetten zählen, sortieren, paginieren
        variables_found = list(
            base_qs_v
            .filter(id__in=final_var_score_map.keys())
            .only("id", "varname", "varlab")
            .prefetch_related(Prefetch("waves", queryset=Wave.objects.select_related("survey")))
            .distinct()
        )

        if sort == "alpha":
            variables_sorted = sorted(
                variables_found,
                key=lambda obj: ((obj.varname or obj.varlab or "")).lower()
            )
        else:
            variables_sorted = sorted(
                variables_found,
                key=lambda obj: final_var_score_map.get(obj.id, 0.0),
                reverse=True
            )

        # Facetten (Wellen)
        for obj in variables_found:
            for w in obj.waves.all():
                facet_counter[w.id] += 1
                facet_waves_set.add(w)

        # Debug/Anzeige
        for obj in variables_sorted:
            obj.relevance = final_var_score_map.get(obj.id, 0.0)

        if search_type == "all":
            ctx["variables"] = variables_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(variables_sorted, request)
            ctx["variables_page"] = page_obj
            ctx["variables"] = page_obj.object_list

        ctx["variables_count"] = len(variables_sorted)
        ctx.setdefault("variables_count", 0)

  
    # =========================
    # CONSTRUCTS - Currently disabled
    # =========================
    # Construct search is currently not implemented
    # To enable, uncomment this section and ensure Construct model is available


    # Facetten-Wellen sortieren nach Anzahl Treffer + Jahr
    facet_waves_sorted = sorted(
        facet_waves_set,
        key=lambda w: (
            (w.survey_id is not None),
            (w.survey.year if w.survey_id and w.survey.year is not None else -1),
            (w.survey.name if w.survey_id else ""),
            w.id,
        ),
        reverse=True
    )


    ctx["facet_waves"] = [
        {
            "wave": w,
            "count": int(facet_counter.get(w.id, 0)),
            "selected": (w.id in ctx["selected_wave_ids"]),
        }
        for w in facet_waves_sorted
    ]

    ctx["all_waves_facets"] = [
        {
            "wave": w,
            "count": int(facet_counter.get(w.id, 0)),
            "selected": (w.id in ctx["selected_wave_ids"]),
        }
        for w in all_waves
    ]


    ctx["facet_counts"] = {w.id: int(facet_counter.get(w.id, 0)) for w in facet_waves_set}


    # Rendern
    return render(request, "search/search.html", ctx)



# API-Endpunkt: "Kleine" Suche nach Fragen für den Frage-Picker im Page-Editor
#  Nur Fragen, keine Keywords, keine Facetten, nur Relevanz-Sortierung, Top 20
@require_GET
def search_questions_api(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": True, "results": []})

    wave_ids = []
    try:
        wave_ids = [int(x) for x in request.GET.getlist("waves") if x.strip().isdigit()]
    except Exception:
        wave_ids = []

    found, score_map = search_questions(
        q=q,
        wave_ids=wave_ids,
        include_keywords=False,
    )

    # API: immer nach Relevanz + Top 20
    found_sorted = sorted(
        found,
        key=lambda obj: score_map.get(obj.id, 0.0),
        reverse=True
    )[:20]

    results = [
        {"id": obj.id, "label": (obj.questiontext or "")[:200]}
        for obj in found_sorted
    ]
    return JsonResponse({"ok": True, "results": results})
