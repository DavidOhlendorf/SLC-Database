# questions/utils.py
# Utility-Funktionen zum Anlegen und Versionieren von Fragen

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Sequence

from django.db import transaction
from django.db.models import Max

from pages.models import WavePage, WavePageQuestion
from questions.models import Question, QuestionVersionGroup
from waves.models import WaveQuestion, Wave


@dataclass(frozen=True)
class CreateQuestionForPageResult:
    question: Question
    waves: list[Wave]


@dataclass(frozen=True)
class CreateQuestionVersionResult:
    question: Question
    version_group: QuestionVersionGroup
    waves: list[Wave]


def _unique_ids(ids: Sequence[int]) -> list[int]:
    """Entfernt Duplikate und behält die ursprüngliche Reihenfolge bei."""
    unique_ids = []
    seen = set()
    for object_id in ids:
        if object_id not in seen:
            seen.add(object_id)
            unique_ids.append(object_id)
    return unique_ids


def _copy_rows_without_variables(rows: list[dict] | None) -> list:
    """
    Kopiert JSON-Zeilen vollständig, leert aber vorhandene Variablennamen.

    Nicht-dict-Einträge werden defensiv unverändert tief kopiert. Regulär
    enthalten die JSON-Felder ausschließlich Dictionaries.
    """
    copied_rows = deepcopy(rows or [])
    for row in copied_rows:
        if isinstance(row, dict) and "variable" in row:
            row["variable"] = ""
    return copied_rows




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

    wave_ids_unique = _unique_ids(wave_ids)
    selected_waves = list(Wave.objects.filter(id__in=wave_ids_unique))

    with transaction.atomic():
        # Neue Frage anlegen
        q = Question.objects.create(questiontext=questiontext)

        # Verknüpfung mit Seite
        WavePageQuestion.objects.create(wave_page=page, question=q)

        # Verknüpfung mit Befragtengruppen
        WaveQuestion.objects.bulk_create(
            [WaveQuestion(wave_id=wid, question=q) for wid in wave_ids_unique],
        )

    return CreateQuestionForPageResult(question=q, waves=selected_waves)


def create_question_version(
    *,
    source_question: Question,
    page: WavePage,
    wave_ids: Sequence[int],
) -> CreateQuestionVersionResult:
    """
    Erstellt eine eigenständige neue Version einer bestehenden Frage.

    Kopiert werden die fachlichen Inhalte der Frage sowie Konstrukt und
    Keywords. Nicht übernommen werden Legacy-ID, Variablenverknüpfungen und
    bestehende Seiten-/Wellenzuordnungen. Variablennamen in Items und
    Antwortoptionen werden geleert.
    """

    wave_ids_unique = _unique_ids(wave_ids)
    if not wave_ids_unique:
        raise ValueError("Mindestens eine Befragungsgruppe muss ausgewählt werden.")

    # Zielseite und Zielwellen auch auf Service-Ebene absichern.
    if page.waves.filter(is_locked=True).exists():
        raise ValueError(
            "Die Zielseite ist mit einer abgeschlossenen Befragung verknüpft."
        )

    allowed_wave_ids = set(
        page.waves.filter(is_locked=False).values_list("id", flat=True)
    )
    if not set(wave_ids_unique).issubset(allowed_wave_ids):
        raise ValueError(
            "Mindestens eine ausgewählte Befragungsgruppe gehört nicht zur "
            "Zielseite oder ist abgeschlossen."
        )

    with transaction.atomic():
        # Ausgangsfrage sperren, damit parallele Requests nicht gleichzeitig
        # unterschiedliche Versionsgruppen oder dieselbe Versionsnummer erzeugen.
        source = (
            Question.objects
            .select_for_update()
            .get(pk=source_question.pk)
        )

        if source.version_group_id is None:
            version_group = QuestionVersionGroup.objects.create()
            source.version_group = version_group
            source.version_number = 0
            source.save(update_fields=("version_group", "version_number"))
        else:
            version_group = (
                QuestionVersionGroup.objects
                .select_for_update()
                .get(pk=source.version_group_id)
            )

        max_version_number = (
            Question.objects
            .filter(version_group=version_group)
            .aggregate(max_number=Max("version_number"))["max_number"]
        )
        next_version_number = (max_version_number or 0) + 1

        new_question = Question.objects.create(
            legacy_id=None,
            version_group=version_group,
            version_number=next_version_number,
            questiontext=source.questiontext,
            question_type=source.question_type,
            question_type_other=source.question_type_other,
            instruction=source.instruction,
            item_stem=source.item_stem,
            items=_copy_rows_without_variables(source.items),
            missing_values=source.missing_values,
            top_categories=source.top_categories,
            answer_options=_copy_rows_without_variables(source.answer_options),
            construct_id=source.construct_id,
        )
        new_question.keywords.set(source.keywords.all())

        last_sort_order = (
            WavePageQuestion.objects
            .filter(wave_page=page)
            .aggregate(max_order=Max("sort_order"))["max_order"]
        )
        WavePageQuestion.objects.create(
            wave_page=page,
            question=new_question,
            sort_order=(last_sort_order + 1) if last_sort_order is not None else 0,
        )

        WaveQuestion.objects.bulk_create(
            [
                WaveQuestion(wave_id=wave_id, question=new_question)
                for wave_id in wave_ids_unique
            ]
        )

    selected_waves_by_id = {
        wave.id: wave
        for wave in Wave.objects.filter(id__in=wave_ids_unique)
    }
    selected_waves = [
        selected_waves_by_id[wave_id]
        for wave_id in wave_ids_unique
        if wave_id in selected_waves_by_id
    ]

    return CreateQuestionVersionResult(
        question=new_question,
        version_group=version_group,
        waves=selected_waves,
    )