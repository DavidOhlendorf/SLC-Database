# pages/services/page_edit_services.py
# Service-Funktionen für die Bearbeitung von Pages 

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
# Fragen können im Datenmodell über das WaveQuestion-Modell mit Befragungen verknüpft dsein UND gleichzeitig über die Zugehörigkeit der Seite zu Befragungen.
# Dies ist erforderlich, da Fragen zwar auf Seiten liegen können, aber für bestimmte Befragungsgruppen ausgeblendet sein können.
# Die Bearbeitung von Seiten erfordert daher ein Synchronisieren der WaveQuestion-Objekte, um die gewünschte Zuordnung von Fragen zu Befragungen korrekt abzubilden.

def sync_wavequestions_for_page(
    *,
    page: WavePage,
    selected_waves_by_qid: Dict[int, Set[int]],
    allowed_wave_ids: Set[int],
    write_debug_pairs: bool = False,
) -> WaveQuestionSyncResult:

    # 1) Defensive: nur erlaubte Waves zulassen (Page-waves)
    normalized: Dict[int, Set[int]] = {}
    for qid, wids in (selected_waves_by_qid or {}).items():
        normalized[qid] = set(wids) & allowed_wave_ids

    qids = list(normalized.keys())
    if not qids or not allowed_wave_ids:
        return WaveQuestionSyncResult(created=0, deleted=0)

    # 2) Existierende Paare (qid,wid) laden
    existing_pairs = set(
        WaveQuestion.objects
        .filter(question_id__in=qids, wave_id__in=allowed_wave_ids)
        .values_list("question_id", "wave_id")
    )

    # 3) Desired Paare bilden
    desired_pairs: Set[Tuple[int, int]] = set()
    for qid, wids in normalized.items():
        for wid in wids:
            desired_pairs.add((qid, wid))

    to_create = desired_pairs - existing_pairs
    candidate_deletes = existing_pairs - desired_pairs
    if not to_create and not candidate_deletes:
        return WaveQuestionSyncResult(created=0, deleted=0)

    # 4) Kandidaten fürs Löschen müssen „Other page“-Check bestehen.
    #
    #    Die Verknüpfung einer Frage mit einer Befragung über WaveQuestion ist nur dann löschbar, wenn die Frage nicht auf einer anderen Seite derselben Befragung erscheint.
    
    deletable_pairs: List[Tuple[int, int]] = []
    if candidate_deletes:
        by_wid: Dict[int, Set[int]] = {}
        for qid, wid in candidate_deletes:
            by_wid.setdefault(wid, set()).add(qid)

        for wid, qid_set in by_wid.items():
            other_qids = set(
                WavePageQuestion.objects
                .filter(
                    question_id__in=qid_set,
                    wave_page__waves__id=wid,
                )
                .exclude(wave_page=page)
                .values_list("question_id", flat=True)
                .distinct()
            )
            # löschbar = Kandidaten, die nicht auf anderen Seiten derselben Befragung liegen
            for qid in (qid_set - other_qids):
                deletable_pairs.append((qid, wid))

    # 5) DB schreiben (bulk create, dann bulk delete)
    created_count = 0
    deleted_count = 0

    if to_create:
        objs = [WaveQuestion(question_id=qid, wave_id=wid) for (qid, wid) in to_create]
        WaveQuestion.objects.bulk_create(objs, ignore_conflicts=True)
        created_count = len(to_create)

    if deletable_pairs:
        q = Q()
        for qid, wid in deletable_pairs:
            q |= Q(question_id=qid, wave_id=wid)
        deleted_count, _ = WaveQuestion.objects.filter(q).delete()

    if write_debug_pairs:
        return WaveQuestionSyncResult(
            created=created_count,
            deleted=deleted_count,
            created_pairs=tuple(sorted(to_create)),
            deleted_pairs=tuple(sorted(deletable_pairs)),
        )

    return WaveQuestionSyncResult(created=created_count, deleted=deleted_count)
