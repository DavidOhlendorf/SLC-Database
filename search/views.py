import re
from django.shortcuts import render, redirect
from django.db.models import Q, F, Prefetch
from django.db.models.functions import Lower
from django.core.paginator import Paginator
from django.contrib.postgres.search import TrigramSimilarity, SearchQuery, SearchRank, SearchVector
from collections import defaultdict
from questions.models import Question, Construct, Keyword
from variables.models import Variable
from waves.models import Wave

ALLOWED_TYPES = {"all", "questions", "variables", "constructs"}
ALLOWED_SORTS = {"relevance", "alpha"}
RESULTS_PER_PAGE = 20

# Landing-Page für die Suche
def search_landing(request):
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
        return redirect("search_landing")

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
    all_waves = Wave.objects.order_by(F("surveyyear").desc(nulls_last=True))
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
            ("constructs", "Konstrukte"),
        ],
        "all_waves": all_waves,
        "selected_waves": selected_waves,
        "selected_wave_ids": [w.id for w in selected_waves],
    }

    # Für Facetten: Zähler und Set
    facet_counter = defaultdict(int)
    facet_waves_set = set()



    # =========================
    # QUESTIONS 
    # =========================
    if search_type in {"all", "questions"}:
        q_lower = q.lower()


    # Basis-QuerySet nur mit Wellen-Filter
    base_qs_q = Question.objects.all()
    if wave_ids:
        base_qs_q = base_qs_q.filter(waves__id__in=wave_ids)


    # ---- 1) Volltext (tsvector) mit deutschem Analyzer
    ts_query = SearchQuery(q, config="german", search_type="websearch")

    ts_rows = (
        base_qs_q
        .annotate(sv=SearchVector("questiontext", weight="A", config="german"))
        .filter(sv=ts_query)
        .annotate(ts_rank=SearchRank(F("sv"), ts_query, normalization=32))
        .values("id", "ts_rank")
    )
    ts_map = {r["id"]: float(r["ts_rank"] or 0.0) for r in ts_rows}


    # ---- 2) Trigram (Fuzzy-Fallback) für Tippfehler/Teilstrings
    tg_rows = (
        base_qs_q
        .annotate(qt=Lower("questiontext"))
        .annotate(sim=TrigramSimilarity(F("qt"), q_lower))
        .filter(sim__gt=0.25) 
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

    # ---- 4) Keyword-Score: bestes passendes Keyword (contains oder trgm)
    kw_rows = (
        Keyword.objects
        .annotate(nl=Lower("name"))
        .annotate(sim=TrigramSimilarity(F("nl"), q_lower))
        .filter(Q(nl__contains=q_lower) | Q(sim__gt=0.25))
        .values("id", "sim")[:200]
    )
    kw_id_to_score = {r["id"]: float(r["sim"] or 0.0) for r in kw_rows}

    kw_links = (
        base_qs_q
        .filter(keywords__in=list(kw_id_to_score.keys()))
        .values("id", "keywords__id")
        .distinct()
    )
    kw_map = {}
    for r in kw_links:
        qid = r["id"]; kwid = r["keywords__id"]
        kw_map[qid] = max(kw_map.get(qid, 0.0), kw_id_to_score.get(kwid, 0.0))

    # ---- 5) Finaler Score pro Frage
    #   text_score = max(ts_rank, trigram*0.6, worttreffer?0.95:0)
    #   kw_score   = bestes Keyword * 0.8
    #   kombi-bonus: wenn beides matched -> +0.15 (auf 1.2 gedeckelt)

    candidate_ids = set(ts_map) | set(tg_map) | wb_ids | set(kw_map)
    final_score_map = {}
    for qid in candidate_ids:
        ts = ts_map.get(qid, 0.0)
        tg = tg_map.get(qid, 0.0) * 0.6
        wb = 0.95 if qid in wb_ids else 0.0
        text_score = max(ts, tg, wb)

        kw_score = kw_map.get(qid, 0.0) * 0.8
        both = (text_score > 0.0 and kw_score > 0.0)

        relevance = max(text_score, kw_score)
        if both:
            relevance = min(1.2, relevance + 0.15)

        final_score_map[qid] = relevance

    # ---- 6) Materialisieren, Facetten zählen, sortieren, paginieren
    questions_found = list(
        base_qs_q
        .filter(id__in=final_score_map.keys())
        .only("id", "questiontext")
        .prefetch_related(Prefetch("waves"))
        .distinct()
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

        # --- 1. Kandidaten über varname/varlab ---       
        var_candidates_qs = (
            Variable.objects
            .annotate(vn=Lower("varname"), vl=Lower("varlab"))
            .annotate(sim_varlab=TrigramSimilarity(F("vn"), q_lower))
            .filter(
                Q(vn__startswith=q_lower) | Q(vl__contains=q_lower) | Q(sim_varlab__gt=0.2))
            .values("id", "varname", "sim_varlab")[:200]
        )


        # Map: varID -> Score aus varlab/varname
        var_text_score_map = {}
        for row in var_candidates_qs:
            vid = row["id"]
            score = float(row["sim_varlab"] or 0.0)  
            if (row["varname"] or "").lower().startswith(q_lower):
                score = max(score, 1.0)               
            var_text_score_map[vid] = score


        # --- 2. Kandidaten über Keywords (indirekt via Question) ---
        # 2a. Relevante Keywords finden
        kw_candidates_vars = (
            Keyword.objects
            .annotate(nl=Lower("name"))
            .annotate(sim_kw=TrigramSimilarity(Lower("name"), q_lower))
            .filter(Q(nl__contains=q_lower) | Q(sim_kw__gt=0.25))
            .values("id", "sim_kw")
            .order_by("-sim_kw")[:200]
        )

        kw_id_to_score_vars = {}
        for row in kw_candidates_vars:
            kwid = row["id"]
            kw_score = row["sim_kw"] or 0
            kw_id_to_score_vars[kwid] = kw_score

        kw_ids_vars = list(kw_id_to_score_vars.keys())

        # 2b. Welche Variablen hängen an Fragen, die diese Keywords haben?
        # Wir gehen: Variable -> question -> keywords
        var_kw_links = (
            Variable.objects
            .filter(question__keywords__in=kw_ids_vars)
            .values("id", "question__keywords__id")
            .distinct()
        )

        kw_score_map_for_var = {}
        for row in var_kw_links:
            vid = row["id"]
            kwid = row["question__keywords__id"]
            score = kw_id_to_score_vars.get(kwid, 0)
            if vid not in kw_score_map_for_var or score > kw_score_map_for_var[vid]:
                kw_score_map_for_var[vid] = score


        # --- 3. Scores mergen (max aus Texttreffer vs. Keywordtreffer) ---
        final_var_score_map = {}

        # zuerst Scores aus varname/varlab
        for vid, score in var_text_score_map.items():
            final_var_score_map[vid] = score

        # dann Keyword-Scores reinmergen, wenn höher
        for vid, score in kw_score_map_for_var.items():
            if vid not in final_var_score_map or score > final_var_score_map[vid]:
                final_var_score_map[vid] = score


        # Falls gar nichts gefunden wurde (kann passieren), leeres Handling
        found_var_ids = list(final_var_score_map.keys())

        base_qs_v = Variable.objects.all()
        if wave_ids:
            base_qs_v = base_qs_v.filter(waves__id__in=wave_ids)

        variables_found = list(
            base_qs_v
            .filter(id__in=found_var_ids)
            .only("id", "varname", "varlab", "question_id")
            .select_related("question")
            .prefetch_related(Prefetch("waves"))
            .distinct()
        )


        # 4. Sortierung
        if sort == "alpha":
            variables_sorted = sorted(
                variables_found,
                key=lambda obj: ((obj.varname or obj.varlab or "")).lower()
            )

        else:  # relevance (default)
            variables_sorted = sorted(
                variables_found,
                key=lambda obj: final_var_score_map.get(obj.id, 0),
                reverse=True
            )

        # Wellen einsammeln, die in den Ergebnissen vorkommen
        for obj in variables_found:
            for w in obj.waves.all():
                facet_counter[w.id] += 1
                facet_waves_set.add(w)


        # Debug-Score anhängen
        for obj in variables_sorted:
            obj.relevance = final_var_score_map.get(obj.id, 0)

        if search_type == "all":
            ctx["variables"] = variables_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(variables_sorted, request)
            ctx["variables_page"] = page_obj
            ctx["variables"] = page_obj.object_list
       
        # Count für Anzeige in Tabs / Überschriften
        ctx["variables_count"] = len(variables_sorted)
        ctx.setdefault("variables_count", 0)
  
    # =========================
    # CONSTRUCTS
    # =========================
    if search_type in {"all", "constructs"}:
        q_lower = q.lower()

        qs_constructs = (
            Construct.objects
            .annotate(l1=Lower("level_1"), l2=Lower("level_2"))
            .filter(Q(l1__contains=q_lower) | Q(l2__contains=q_lower))
            .distinct()
        )

        # Sortierung

        if sort == "alpha":
            qs_constructs = qs_constructs.order_by(Lower("level_1").asc(), Lower("level_2").asc(), "id")

        else:  # relevance
            qs_constructs = (
                qs_constructs
                .annotate(
                    sim_l1=TrigramSimilarity("level_1", q),
                    sim_l2=TrigramSimilarity("level_2", q),
                    sim=F("sim_l1") * 0.6 + F("sim_l2") * 0.4,
                )
                .order_by(F("sim").desc(nulls_last=True), "id")
            )

        if search_type == "all":
            ctx["constructs"] = qs_constructs[:ctx["TOP_N"]]
        else:
            page_obj = paginate_queryset(qs_constructs, request)
            ctx["constructs_page"] = page_obj
            ctx["constructs"] = page_obj.object_list

        # Count für Anzeige
        ctx["constructs_count"] = qs_constructs.count()
        ctx.setdefault("constructs_count", 0)


    # Facetten-Wellen sortieren nach Anzahl Treffer + Jahr
    facet_waves_sorted = sorted(
        facet_waves_set,
        key=lambda w: ((w.surveyyear is not None), w.surveyyear or 0),
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
