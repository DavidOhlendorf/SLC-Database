# pages/services/page_sync.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple, List

from waves.models import WaveQuestion
from pages.models import WavePage, WavePageQuestion

from django.db.models import Q


@dataclass(frozen=True)
class WaveQuestionSyncResult:
    created: int
    deleted: int

    # fürs Debuggen/Logging:
    created_pairs: Tuple[Tuple[int, int], ...] = ()
    deleted_pairs: Tuple[Tuple[int, int], ...] = ()


# Funktion synchronisiert die Zuordnung von Fragen zu Befragungen für eine gegebene Fragebogenseite.


def sync_wavequestions_for_page(
    *,
    page: WavePage,
    selected_waves_by_qid: Dict[int, Set[int]],
    allowed_wave_ids: Set[int],
    write_debug_pairs: bool = False,
) -> WaveQuestionSyncResult:
    """
    Synchronisiert die Wave-Zuordnungen der Fragen einer Seite.

    Dabei werden zwei Ebenen gepflegt:

    1. WavePageQuestion.waves:
       Auf welchen Waves gilt eine Frage auf genau dieser Seite?

    2. WaveQuestion:
       In welchen Waves kommt die Frage insgesamt irgendwo vor?

    WaveQuestion wird nur entfernt, wenn die Frage in der betreffenden
    Wave auf keiner anderen Seite mehr verwendet wird.
    """

    # ------------------------------------------------------------
    # 1. Eingaben defensiv auf Waves der Seite begrenzen
    # ------------------------------------------------------------

    normalized: Dict[int, Set[int]] = {}

    for qid, wids in (selected_waves_by_qid or {}).items():
        normalized[qid] = set(wids) & allowed_wave_ids

    qids = list(normalized.keys())

    if not qids or not allowed_wave_ids:
        return WaveQuestionSyncResult(
            created=0,
            deleted=0,
        )

    # ------------------------------------------------------------
    # 2. Seitenbezogene Zuordnung speichern
    #
    #    WavePageQuestion.waves beschreibt künftig ausdrücklich:
    #
    #    Frage Q gilt auf Seite P für Wave W.
    # ------------------------------------------------------------

    page_links = {
        link.question_id: link
        for link in (
            WavePageQuestion.objects
            .filter(
                wave_page=page,
                question_id__in=qids,
            )
        )
    }

    for qid, selected_wave_ids in normalized.items():
        link = page_links.get(qid)

        if link is None:
            continue

        selected_waves = page.waves.filter(
            id__in=selected_wave_ids
        )

        link.waves.set(selected_waves)

    # ------------------------------------------------------------
    # 3. Bestehende globale WaveQuestion-Paare laden
    # ------------------------------------------------------------

    existing_pairs = set(
        WaveQuestion.objects
        .filter(
            question_id__in=qids,
            wave_id__in=allowed_wave_ids,
        )
        .values_list(
            "question_id",
            "wave_id",
        )
    )

    # ------------------------------------------------------------
    # 4. Gewünschte globale WaveQuestion-Paare
    # ------------------------------------------------------------

    desired_pairs: Set[Tuple[int, int]] = set()

    for qid, wave_ids in normalized.items():
        for wave_id in wave_ids:
            desired_pairs.add(
                (qid, wave_id)
            )

    to_create = desired_pairs - existing_pairs
    candidate_deletes = existing_pairs - desired_pairs

    # ------------------------------------------------------------
    # 5. Löschkandidaten gegen andere Seiten prüfen
    #
    #
    #     Ist genau diese Frage auf der anderen Seite
    #     für diese Wave aktiviert?
    # ------------------------------------------------------------

    deletable_pairs: List[Tuple[int, int]] = []

    if candidate_deletes:
        by_wave_id: Dict[int, Set[int]] = {}

        for qid, wave_id in candidate_deletes:
            by_wave_id.setdefault(
                wave_id,
                set(),
            ).add(qid)

        for wave_id, question_ids in by_wave_id.items():

            other_question_ids = set(
                WavePageQuestion.objects
                .filter(
                    question_id__in=question_ids,
                    waves__id=wave_id,
                )
                .exclude(wave_page=page)
                .values_list(
                    "question_id",
                    flat=True,
                )
                .distinct()
            )

            for qid in (
                question_ids - other_question_ids
            ):
                deletable_pairs.append(
                    (qid, wave_id)
                )

    # ------------------------------------------------------------
    # 6. Globale WaveQuestion-Zuordnungen schreiben
    # ------------------------------------------------------------

    created_count = 0
    deleted_count = 0

    if to_create:
        objects = [
            WaveQuestion(
                question_id=qid,
                wave_id=wave_id,
            )
            for qid, wave_id in to_create
        ]

        WaveQuestion.objects.bulk_create(
            objects,
            ignore_conflicts=True,
        )

        created_count = len(to_create)

    if deletable_pairs:
        query = Q()

        for qid, wave_id in deletable_pairs:
            query |= Q(
                question_id=qid,
                wave_id=wave_id,
            )

        deleted_count, _ = (
            WaveQuestion.objects
            .filter(query)
            .delete()
        )

    if write_debug_pairs:
        return WaveQuestionSyncResult(
            created=created_count,
            deleted=deleted_count,
            created_pairs=tuple(
                sorted(to_create)
            ),
            deleted_pairs=tuple(
                sorted(deletable_pairs)
            ),
        )

    return WaveQuestionSyncResult(
        created=created_count,
        deleted=deleted_count,
    )