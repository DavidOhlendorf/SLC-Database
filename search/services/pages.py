from collections import defaultdict

from django.db.models import F, Prefetch, Q
from django.db.models.functions import Lower

from pages.models import (
    WavePage,
    WavePageQuestion,
    WavePageWave,
)
from questions.models import Keyword

from .questions import search_questions


# Suche nach Seiten basierend auf Seitennamen und zugeordneten Fragen einschließlich deren Schlagwörtern.
def search_pages(q: str, wave_ids=None, question_search_result=None,):

    q = (q or "").strip()

    if not q:
        return [], {}

    q_lower = q.lower()
    wave_ids = list(wave_ids or [])

    base_queryset = WavePage.objects.all()

    if wave_ids:
        base_queryset = base_queryset.filter(
            waves__id__in=wave_ids
        )

    # Direkte Treffer im Seitennamen haben die höchste Priorität.
    pagename_rows = (
        base_queryset
        .annotate(pagename_lower=Lower("pagename"))
        .filter(
            Q(pagename_lower__startswith=q_lower)
            | Q(pagename_lower__contains=q_lower)
        )
        .values_list("id", "pagename_lower")
    )

    pagename_scores = {}

    for page_id, pagename_lower in pagename_rows:
        if pagename_lower == q_lower:
            score = 1.2
        elif pagename_lower.startswith(q_lower):
            score = 1.1
        else:
            score = 0.95

        pagename_scores[page_id] = max(
            pagename_scores.get(page_id, 0.0),
            score,
        )

    # Inhaltliche Treffer werden vom vorhandenen Fragenservice ermittelt.
    # Damit gelten dieselben Regeln für Fragetext und Keywords.
    # In der globalen Suche können bereits berechnete Fragentreffer
    # übergeben werden. Bei alleiniger Seitensuche ermittelt der
    # Service die Fragentreffer selbst.
    if question_search_result is None:
        matched_questions, question_score_map = search_questions(
            q=q,
            wave_ids=wave_ids,
            include_keywords=True,
        )
    else:
        matched_questions, question_score_map = question_search_result


    matched_question_ids = {
        question.id
        for question in matched_questions
    }

    page_question_scores = defaultdict(float)
    page_question_wave_ids = defaultdict(set)

    if matched_question_ids:
        matching_link_queryset = WavePageQuestion.objects.filter(
            wave_page__in=base_queryset,
            question_id__in=matched_question_ids,
        )

        # Die Frage muss auf dieser Seite ausdrücklich der ausgewählten
        # Welle zugeordnet sein.
        if wave_ids:
            matching_link_queryset = (
                matching_link_queryset.filter(
                    waves__id__in=wave_ids
                )
            )

        matching_link_rows = (
            matching_link_queryset
            .values(
                "wave_page_id",
                "question_id",
                "waves__id",
            )
            .distinct()
        )

        for row in matching_link_rows:
            page_id = row["wave_page_id"]
            question_id = row["question_id"]
            wave_id = row["waves__id"]

            # Inhaltliche Treffer bleiben etwas unter einem direkten
            # Seitennamen-Treffer gewichtet.
            page_question_scores[page_id] = max(
                page_question_scores[page_id],
                question_score_map.get(question_id, 0.0) * 0.9,
            )

            if wave_id is not None:
                page_question_wave_ids[page_id].add(wave_id)

    candidate_ids = (
        set(pagename_scores)
        | set(page_question_scores)
    )

    if not candidate_ids:
        return [], {}

    relevance_scores = {
        page_id: max(
            pagename_scores.get(page_id, 0.0),
            page_question_scores.get(page_id, 0.0),
        )
        for page_id in candidate_ids
    }

    # Wellen- und Modulinformationen für die spätere Ergebnisanzeige.
    all_wave_links = (
        WavePageWave.objects
        .select_related("wave__survey", "module")
        .order_by(
            F("wave__survey__year").desc(nulls_last=True),
            F("wave__start_date").desc(nulls_last=True),
            "wave__cycle",
            "wave__instrument",
            "sort_order",
            "id",
        )
    )

    displayed_wave_links = all_wave_links

    if wave_ids:
        displayed_wave_links = displayed_wave_links.filter(
            wave_id__in=wave_ids
        )

    # Passende Fragen vorbereiten, damit später auf der Seitenkarte
    # nachvollziehbar ist, warum die Seite gefunden wurde.
    matching_question_links = (
        WavePageQuestion.objects
        .filter(question_id__in=matched_question_ids)
        .select_related("question")
        .prefetch_related(
            Prefetch(
                "question__keywords",
                queryset=Keyword.objects.order_by("name"),
            )
        )
        .order_by("sort_order", "id")
    )

    if wave_ids:
        matching_question_links = (
            matching_question_links
            .filter(waves__id__in=wave_ids)
            .distinct()
        )

    matched_pages = list(
        base_queryset
        .filter(id__in=candidate_ids)
        .only(
            "id",
            "pagename",
            "page_heading",
            "introduction",
        )
        .prefetch_related(
            Prefetch(
                "wave_links",
                queryset=all_wave_links,
                to_attr="search_all_wave_links",
            ),
            Prefetch(
                "wave_links",
                queryset=displayed_wave_links,
                to_attr="search_display_wave_links",
            ),
            Prefetch(
                "page_questions",
                queryset=matching_question_links,
                to_attr="search_matching_question_links",
            ),
        )
        .distinct()
    )

    for page in matched_pages:
        page.relevance = relevance_scores.get(page.id, 0.0)

        if page.id in pagename_scores:
            page.search_match_wave_ids = {
                link.wave_id
                for link in page.search_all_wave_links
            }
        else:
            page.search_match_wave_ids = set(
                page_question_wave_ids.get(page.id, set())
            )

    return matched_pages, relevance_scores

# Sortierung der Seiten
def sort_pages(pages, score_map, sort):

    if sort == "alpha":
        return sorted(
            pages,
            key=lambda page: (
                (page.pagename or "").lower(),
                page.id,
            ),
        )

    return sorted(
        pages,
        key=lambda page: (
            -score_map.get(page.id, 0.0),
            (page.pagename or "").lower(),
            page.id,
        ),
    )