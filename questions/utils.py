# questions/utils.py
# Utility-Funktion zum Anlegen einer Frage und Verknüpfen mit Seite und Waves

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.db import transaction

from pages.models import WavePage, WavePageQuestion
from questions.models import Question
from waves.models import WaveQuestion, Wave


@dataclass(frozen=True)
class CreateQuestionForPageResult:
    question: Question
    waves: list[Wave]


def create_question_for_page(
    *,
    page: WavePage,
    questiontext: str,
    wave_ids: Sequence[int],
) -> CreateQuestionForPageResult:
    """
    Legt eine neue Question an und verknüpft sie
    - mit der Fragebogenseite (WavePageQuestion)
    - mit den ausgewählten Befragtengruppen (WaveQuestion)

    Validierung der UI-Regeln (z.B. locked) sollte die View machen.
    Diese Funktion geht davon aus, dass wave_ids bereits "erlaubt" sind.
    """

    # defensive: Duplikate raus, Reihenfolge stabil halten
    wave_ids_unique = []
    seen = set()
    for wid in wave_ids:
        if wid not in seen:
            seen.add(wid)
            wave_ids_unique.append(wid)

    selected_waves = list(Wave.objects.filter(id__in=wave_ids_unique))

    with transaction.atomic():
        # Neue Frage anlegen
        q = Question.objects.create(questiontext=questiontext)

        # Verknüpfung mit Seite
        WavePageQuestion.objects.create(wave_page=page, question=q)

        # Verknüpfung mit Befragtengruppen
        WaveQuestion.objects.bulk_create(
            [WaveQuestion(wave_id=wid, question=q) for wid in wave_ids],
        )

    return CreateQuestionForPageResult(question=q, waves=selected_waves)
