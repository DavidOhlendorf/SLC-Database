# pages/services/page_cleanup.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Set

from variables.models import Variable
from questions.models import QuestionVariableWave
from waves.models import WaveQuestion
from pages.models import WavePage, WavePageQuestion

from django.db.models import OuterRef, Exists


@dataclass(frozen=True)
class RemovalCleanupResult:
    deleted_wavequestions: int
    deleted_variable_wave_links: int
    orphan_question_ids: list[int]


# Funktion bereinigt Datenbankeinträge nach dem Entfernen von Fragen durh die Seitenbearbeitung.
def apply_question_removals_from_page(
    *,
    page: WavePage,
    removed_question_ids: list[int],
    wave_ids: list[int],
    compute_orphans: bool = True,
) -> RemovalCleanupResult:
    deleted_wq = cleanup_wavequestions_for_removed_questions(
        page=page,
        removed_question_ids=removed_question_ids,
        wave_ids=wave_ids,
    )

    deleted_m2m_total = 0
    for wid in wave_ids:
        deleted_m2m_total += cleanup_after_removing_questions(
            wave_id=wid,
            removed_question_ids=removed_question_ids,
        )

    orphan_qids = get_new_orphan_question_ids(removed_question_ids) if compute_orphans else []

    return RemovalCleanupResult(
        deleted_wavequestions=deleted_wq,
        deleted_variable_wave_links=deleted_m2m_total,
        orphan_question_ids=orphan_qids,
    )



# Funktion bereinigt Datenbankeinträge nach dem Entfernen von Fragen durh die Seitenbearbeitung.
#
# Dies kann aus zwei Gründen notwendig sein:
#   1) weil gesamte Seiten gelöscht werden
#   2) weil Fragen von Seiten entfernt werden (oder für bestimmte Befragungen ausgeblendet werden)
#
# Dabei werden folgende Bereinigungen durchgeführt:
#   - Löschen der Triad-Einträge (QuestionVariableWave) für die entfernten Fragen
#   - Entfernen der M2M-Einträge Variable↔Wave für Variablen, die in der Befragung
#     nicht mehr über verbleibende Fragen gebraucht werden.
#   - Technische Variablen werden nicht angefasst, da diese in Befragungen vorkommen können, ohne auf Seiten zu sein.


def cleanup_after_removing_questions(
    *,
    wave_id: int,
    removed_question_ids: Iterable[int],
) -> int:

    removed_qids = set(int(x) for x in removed_question_ids or [])
    if not removed_qids:
        return 0

    # 1) Welche Fragen kommen in dieser Befragungsgruppe (nach dem Entfernen) noch irgendwo auf Seiten vor?
    remaining_qids_in_wave: Set[int] = set(
        WavePageQuestion.objects
        .filter(wave_page__waves__id=wave_id)
        .values_list("question_id", flat=True)
        .distinct()
    )

    # 2) Behalte nur die Fragen, die auf keiner Seite der Befragung mehr vorkommen
    actually_removed_qids = removed_qids - remaining_qids_in_wave
    if not actually_removed_qids:
        return 0


    # 3) Triad-Zeilen (Questions - Variables - Waves) für diese entfernten Fragen holen
    triad_qs = QuestionVariableWave.objects.filter(
        wave_id=wave_id,
        question_id__in=actually_removed_qids,
    )

    affected_var_ids = set(triad_qs.values_list("variable_id", flat=True).distinct())

    # a) Triad-Einträge löschen (Verknüpfung der Variablen mit den entfernten Fragen in der Befragung)
    triad_qs.delete()

    if not affected_var_ids:
        return 0


    # 4) Identifiziere Variablen, die in der Befragungsgruppe noch über verbleibende Fragen gebraucht werden
    still_used_var_ids = set(
        QuestionVariableWave.objects.filter(
            wave_id=wave_id,
            question_id__in=remaining_qids_in_wave,
            variable_id__in=affected_var_ids,
        ).values_list("variable_id", flat=True).distinct()
    )

    to_remove_var_ids = affected_var_ids - still_used_var_ids
    if not to_remove_var_ids:
        return 0

    non_technical_var_ids = list(
        Variable.objects.filter(
            id__in=to_remove_var_ids,
            is_technical=False,
        ).values_list("id", flat=True)
    )
    if not non_technical_var_ids:
        return 0

    # 5) Variable↔Wave M2M bereinigen
    through = Variable._meta.get_field("waves").remote_field.through
    deleted, _ = through.objects.filter(
        wave_id=wave_id,
        variable_id__in=non_technical_var_ids,
    ).delete()

    return deleted




# Orphan Cleanup Utilities for Questions after deleting or modifiying Pages
def cleanup_wavequestions_for_removed_questions(*, page, removed_question_ids: list[int], wave_ids: list[int]) -> int:
    """
    Phase (a): Entfernt WaveQuestion-Verknüpgungen (wave, question),
    wenn die Frage in dieser Befragtengruppe auf keiner anderen Seite mehr vorkommt (bei core sollte das nicht sein, bei episodes möglich).
    Gibt Anzahl gelöschter WaveQuestion-Links zurück.
    """
    if not removed_question_ids or not wave_ids:
        return 0

    other_usage = WavePageQuestion.objects.filter(
        question_id=OuterRef("question_id"),
        wave_page__waves__id=OuterRef("wave_id"),
    ).exclude(wave_page=page)

    wq_qs = WaveQuestion.objects.filter(
        wave_id__in=wave_ids,
        question_id__in=removed_question_ids,
    ).annotate(
        keep=Exists(other_usage)
    )

    deleted, _ = wq_qs.filter(keep=False).delete()
    return deleted


def get_new_orphan_question_ids(candidate_question_ids: list[int]) -> list[int]:
    """
    Phase (b): 'Orphan' = Frage ist in keiner wave mehr referenziert.
    Gibt Liste der verwaisten Frage-IDs zurück
    """
    if not candidate_question_ids:
        return []

    still_in_any_wave = set(
        WaveQuestion.objects
        .filter(question_id__in=candidate_question_ids)
        .values_list("question_id", flat=True)
        .distinct()
    )
    return [qid for qid in candidate_question_ids if qid not in still_in_any_wave]
