import re

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
    TrigramWordSimilarity,
)
from django.db.models import F, Prefetch, Q
from django.db.models.functions import Lower

from questions.formatting import strip_pv_formatting
from questions.models import Keyword, Question
from waves.models import Wave





# Service-Funktion für die Suche nach Fragen basierend auf verschiedenen Kriterien:
# - Volltextsuche (tsvector) mit deutschem Analyzer
# - Trigram-Suche für Fuzzy-Matches
# - Wortgrenzen-Boost
# - Keyword-Score
# Liefert eine Liste von Fragen und eine Mapping von Frage-ID zu finalem Score.

def search_questions(q: str, wave_ids=None, include_keywords=True):
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
        .only("id", "questiontext", "version_group_id", "version_number")
        .prefetch_related(
            Prefetch(
                "waves",
                queryset=Wave.objects.select_related("survey").order_by(
                    F("survey__year").desc(nulls_last=True),
                    F("start_date").desc(nulls_last=True),
                    "cycle",
                    "instrument",
                    "id",
                ),
            )
        )
        .distinct()
    )

    return found, final_score_map




# ---- Gruppierung von Suchergebnissen nach Versionsgruppen ----------------
#   Fasst Suchtreffer zu Ergebniskarten zusammen.
#   Für Treffer mit Versionsgruppe werden alle Fragen dieser Gruppe geladen.
#   Bei aktivem Wellenfilter werden nur Gruppenmitglieder berücksichtigt, die
#   mindestens einer ausgewählten Welle zugeordnet sind. Ungruppierte Fragen
#   bleiben eigenständige Karten.

def build_question_groups(matched_questions, score_map, wave_ids=None):

    matched_questions = list(matched_questions)
    wave_ids = list(wave_ids or [])

    if not matched_questions:
        return []

    matched_group_ids = {
        question.version_group_id
        for question in matched_questions
        if question.version_group_id is not None
    }
    matched_ungrouped_ids = {
        question.id
        for question in matched_questions
        if question.version_group_id is None
    }

    display_filter = Q()
    if matched_group_ids:
        display_filter |= Q(version_group_id__in=matched_group_ids)
    if matched_ungrouped_ids:
        display_filter |= Q(id__in=matched_ungrouped_ids)

    display_qs = Question.objects.filter(display_filter)
    if wave_ids:
        display_qs = display_qs.filter(waves__id__in=wave_ids)

    displayed_questions = list(
        display_qs
        .select_related("version_group")
        .prefetch_related(
            Prefetch(
                "waves",
                queryset=Wave.objects.select_related("survey").order_by(
                    F("survey__year").desc(nulls_last=True),
                    F("start_date").desc(nulls_last=True),
                    "cycle",
                    "instrument",
                    "id",
                ),
            ),
            Prefetch(
                "keywords",
                queryset=Keyword.objects.order_by("name"),
            ),
        )
        .distinct()
    )

    grouped = {}
    for question in displayed_questions:
        question.relevance = score_map.get(question.id, 0.0)

        if question.version_group_id is not None:
            group_key = ("version_group", question.version_group_id)
            group_name = (question.version_group.name or "").strip()
            is_version_group = True
        else:
            group_key = ("question", question.id)
            group_name = ""
            is_version_group = False

        if group_key not in grouped:
            grouped[group_key] = {
                "key": group_key,
                "name": group_name,
                "is_version_group": is_version_group,
                "questions": [],
                "relevance": 0.0,
                "sort_label": "",
            }

        grouped[group_key]["questions"].append(question)

    result = []
    for group in grouped.values():
        group["questions"].sort(
            key=lambda question: (
                -score_map.get(question.id, 0.0),
                question.version_number,
                question.id,
            )
        )

        group["primary_question"] = group["questions"][0]
        group["other_questions"] = group["questions"][1:]

        group["relevance"] = max(
            (score_map.get(question.id, 0.0) for question in group["questions"]),
            default=0.0,
        )

        if group["name"]:
            group["sort_label"] = group["name"].lower()
        else:
            first_version = min(
                group["questions"],
                key=lambda question: (question.version_number, question.id),
            )
            group["sort_label"] = strip_pv_formatting(first_version.questiontext).lower()

        result.append(group)

    return result


# ---- Sortierung von Ergebniskarten ----------------------------------------
# Sortiert Ergebniskarten, ohne die Reihenfolge in der Karte zu ändern.
def sort_question_groups(question_groups, sort):
    if sort == "alpha":
        return sorted(
            question_groups,
            key=lambda group: (group["sort_label"], group["key"]),
        )

    return sorted(
        question_groups,
        key=lambda group: (
            -group["relevance"],
            group["sort_label"],
            group["key"],
        ),
    )
