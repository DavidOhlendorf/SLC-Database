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
from variables.models import Variable, QuestionVariableWave
from variables.versioning import normalize_variable_name, parse_variable_name
from waves.models import WaveQuestion, Wave


@dataclass(frozen=True)
class CreateQuestionForPageResult:
    question: Question
    waves: list[Wave]

@dataclass(frozen=True)
class VariableVersionRequest:
    source_variable_id: int
    new_varname: str
    inherit_suffix_metadata: bool = True

@dataclass(frozen=True)
class CreateQuestionVersionResult:
    question: Question
    version_group: QuestionVersionGroup
    waves: list[Wave]
    variables: list[Variable]


def _unique_ids(ids: Sequence[int]) -> list[int]:
    """Entfernt Duplikate und behält die ursprüngliche Reihenfolge bei."""
    unique_ids = []
    seen = set()
    for object_id in ids:
        if object_id not in seen:
            seen.add(object_id)
            unique_ids.append(object_id)
    return unique_ids


def _copy_rows_with_variable_mapping(
    rows: list[dict] | None,
    variable_mapping: dict[str, str],
) -> list:
    """
    Kopiert JSON-Zeilen und ersetzt ausgewählte alte Variablennamen.
 

    Variablenfelder ohne neue Variablenversion werden geleert. Der Abgleich
    erfolgt case-insensitive, die gespeicherten neuen Namen sind kanonisch.
    Nicht-dict-Einträge werden defensiv unverändert tief kopiert.
    """
    copied_rows = deepcopy(rows or [])
    normalized_mapping = {
        old_name.casefold(): new_name
        for old_name, new_name in variable_mapping.items()
    }

    for row in copied_rows:
        if not isinstance(row, dict) or "variable" not in row:
            continue
        old_name = str(row.get("variable") or "").strip()
        row["variable"] = normalized_mapping.get(old_name.casefold(), "")

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
    group_name: str | None = None,
    version_reason: str | None = None,
    variable_versions: Sequence[VariableVersionRequest] = (),
) -> CreateQuestionVersionResult:
    """
    Erstellt eine eigenständige neue Version einer bestehenden Frage.

    Kopiert werden die fachlichen Inhalte der Frage sowie Konstrukt und
    Keywords. Nicht übernommen werden Legacy-ID und bestehende Seiten-/
    Wellenzuordnungen. Optional ausgewählte Variablen werden als neue,
    versionierte Variablen angelegt, mit allen Zielgruppen verknüpft und in
    Items bzw. Antwortoptionen eingesetzt. Nicht ausgewählte Variablennamen
    werden geleert. Beim ersten Versionieren muss ein Name für die neu
    angelegte Versionsgruppe übergeben werden.
    """

    cleaned_version_reason = (version_reason or "").strip()

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

    normalized_variable_versions: list[VariableVersionRequest] = []
    seen_source_ids: set[int] = set()
    seen_new_names: set[str] = set()

    for variable_version in variable_versions:
        source_variable_id = int(variable_version.source_variable_id)
        if source_variable_id in seen_source_ids:
            raise ValueError(
                "Eine Ausgangsvariable wurde mehrfach zur Versionierung ausgewählt."
            )

        try:
            new_varname = normalize_variable_name(variable_version.new_varname)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        normalized_key = new_varname.casefold()
        if normalized_key in seen_new_names:
            raise ValueError(
                f"Der neue Variablenname '{new_varname}' wurde mehrfach vergeben."
            )

        seen_source_ids.add(source_variable_id)
        seen_new_names.add(normalized_key)
        inherit_suffix_metadata = variable_version.inherit_suffix_metadata
        if not isinstance(inherit_suffix_metadata, bool):
            raise ValueError(
                "Die Auswahl zur Übernahme der Suffixe ist ungültig."
            )

        normalized_variable_versions.append(
            VariableVersionRequest(
                source_variable_id=source_variable_id,
                new_varname=new_varname,
                inherit_suffix_metadata=inherit_suffix_metadata,
            )
        )


    with transaction.atomic():
        # Ausgangsfrage sperren, damit parallele Requests nicht gleichzeitig
        # unterschiedliche Versionsgruppen oder dieselbe Versionsnummer erzeugen.
        source = (
            Question.objects
            .select_for_update()
            .get(pk=source_question.pk)
        )

        selected_source_ids = {
            item.source_variable_id
            for item in normalized_variable_versions
        }
        linked_source_ids = set(
            QuestionVariableWave.objects
            .filter(question=source, variable_id__in=selected_source_ids)
            .values_list("variable_id", flat=True)
        )
        if selected_source_ids != linked_source_ids:
            raise ValueError(
                "Mindestens eine ausgewählte Ausgangsvariable gehört nicht zur Frage."
            )

        source_variables = {
            variable.id: variable
            for variable in (
                Variable.objects
                .select_for_update()
                .filter(id__in=selected_source_ids)
            )
        }

        for item in normalized_variable_versions:
            source_variable = source_variables[item.source_variable_id]

            if Variable.objects.filter(varname__iexact=item.new_varname).exists():
                raise ValueError(
                    f"Der Variablenname '{item.new_varname}' ist bereits vergeben."
                )
            
            try:
                source_suffixes = parse_variable_name(
                    source_variable.varname
                ).non_version_suffixes
                target_suffixes = parse_variable_name(
                    item.new_varname
                ).non_version_suffixes
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            if (
                item.inherit_suffix_metadata
                and source_suffixes != target_suffixes
            ):
                raise ValueError(
                    f"Bei '{item.new_varname}' wurden Suffixe verändert. "
                    "Deaktiviere die Übernahme der Zusatzmerkmale, wenn diese Änderung beabsichtigt ist."
                )



        if source.version_group_id is None:

            cleaned_group_name = (group_name or "").strip()
            if not cleaned_group_name:
                raise ValueError(
                    "Bitte gib einen Namen für die neue Versionsgruppe an."
                )
            if len(cleaned_group_name) > 255:
                raise ValueError(
                    "Der Name der Versionsgruppe darf höchstens 255 Zeichen lang sein."
                )

            version_group = QuestionVersionGroup.objects.create(
                name=cleaned_group_name,
            )
            
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

        created_variables: list[Variable] = []
        variable_mapping: dict[str, str] = {}

        for item in normalized_variable_versions:
            source_variable = source_variables[item.source_variable_id]
            inherit_suffix_metadata = item.inherit_suffix_metadata
            new_variable = Variable.objects.create(
                legacy_id=None,
                varname=item.new_varname,
                varlab=source_variable.varlab,
                vallab=None,
                ver=True,
                gen=source_variable.gen if inherit_suffix_metadata else False,
                plausi=(
                    source_variable.plausi if inherit_suffix_metadata else False
                ),
                flag=source_variable.flag if inherit_suffix_metadata else False,
                reason_ver=(
                    cleaned_version_reason
                    or f"Version von {source_variable.varname}"
                ),
                reason_gen=(
                    source_variable.reason_gen if inherit_suffix_metadata else None
                ),
                reason_plausi=(
                    source_variable.reason_plausi if inherit_suffix_metadata else None
                ),
                reason_flag=(
                    source_variable.reason_flag if inherit_suffix_metadata else None
                ),
                is_technical=source_variable.is_technical,
                comment=source_variable.comment,
            )
            created_variables.append(new_variable)
            variable_mapping[source_variable.varname] = new_variable.varname


        new_question = Question.objects.create(
            legacy_id=None,
            version_group=version_group,
            version_number=next_version_number,
            version_reason=cleaned_version_reason,
            questiontext=source.questiontext,
            question_type=source.question_type,
            question_type_other=source.question_type_other,
            instruction=source.instruction,
            item_stem=source.item_stem,
            items=_copy_rows_with_variable_mapping(source.items, variable_mapping),
            missing_values=source.missing_values,
            top_categories=source.top_categories,
            answer_options=_copy_rows_with_variable_mapping(
                source.answer_options,
                variable_mapping,
            ),
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

        if created_variables:
            QuestionVariableWave.objects.bulk_create(
                [
                    QuestionVariableWave(
                        question=new_question,
                        variable=variable,
                        wave_id=wave_id,
                    )
                    for variable in created_variables
                    for wave_id in wave_ids_unique
                ]
            )

            VariableWaveThrough = Variable.waves.through
            VariableWaveThrough.objects.bulk_create(
                [
                    VariableWaveThrough(
                        variable_id=variable.id,
                        wave_id=wave_id,
                    )
                    for variable in created_variables
                    for wave_id in wave_ids_unique
                ],
                ignore_conflicts=True,
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
        variables=created_variables,
    )