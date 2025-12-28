from django.db.models import OuterRef, Exists
from pages.models import WavePageQuestion
from waves.models import WaveQuestion


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

    delete_count = wq_qs.filter(keep=False).count()
    wq_qs.filter(keep=False).delete()
    return delete_count


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
