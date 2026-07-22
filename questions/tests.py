from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from pages.models import WavePage, WavePageQuestion
from waves.models import Survey, Wave, WaveQuestion

from .models import Keyword, Question, QuestionVersionGroup
from .utils import create_question_version


class QuestionVersioningModelTests(TestCase):
    def test_existing_question_defaults_to_no_group_and_version_zero(self):
        question = Question.objects.create(questiontext="Beispielfrage")

        self.assertIsNone(question.version_group)
        self.assertEqual(question.version_number, 0)

    def test_question_without_group_rejects_nonzero_version_number(self):
        question = Question(questiontext="Beispielfrage", version_number=1)

        with self.assertRaises(ValidationError) as context:
            question.full_clean()

        self.assertIn("version_number", context.exception.message_dict)

    def test_version_numbers_must_be_unique_within_group(self):
        group = QuestionVersionGroup.objects.create(name="Geschlecht")
        Question.objects.create(
            questiontext="Ursprungsfassung",
            version_group=group,
            version_number=0,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Question.objects.create(
                    questiontext="Weitere Ursprungsfassung",
                    version_group=group,
                    version_number=0,
                )

    def test_same_version_number_is_allowed_in_different_groups(self):
        first_group = QuestionVersionGroup.objects.create(name="Geschlecht")
        second_group = QuestionVersionGroup.objects.create(name="Alter")

        Question.objects.create(
            questiontext="Geschlecht",
            version_group=first_group,
            version_number=0,
        )
        Question.objects.create(
            questiontext="Alter",
            version_group=second_group,
            version_number=0,
        )

        self.assertEqual(Question.objects.count(), 2)

    def test_version_group_cannot_be_deleted_while_questions_reference_it(self):
        group = QuestionVersionGroup.objects.create(name="Geschlecht")
        Question.objects.create(
            questiontext="Geschlecht",
            version_group=group,
            version_number=0,
        )

        with self.assertRaises(ProtectedError):
            group.delete()


class QuestionVersionCreationTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(name="Testbefragung", year=2026)
        self.wave = Wave.objects.create(
            survey=self.survey,
            surveyyear="2026",
            cycle="Gruppe A",
            instrument=Wave.Instrument.CAWI,
        )
        self.second_wave = Wave.objects.create(
            survey=self.survey,
            surveyyear="2026",
            cycle="Gruppe B",
            instrument=Wave.Instrument.CAWI,
        )
        self.page = WavePage.objects.create(pagename="dem_01")
        self.page.waves.add(self.wave, self.second_wave)

    def test_create_version_copies_content_and_clears_variable_names(self):
        keyword = Keyword.objects.create(name="Geschlecht")
        source = Question.objects.create(
            legacy_id=123,
            questiontext="Nennen Sie uns bitte Ihr Geschlecht.",
            question_type=Question.QuestionType.SINGLE_VERTICAL,
            instruction="Bitte auswählen.",
            item_stem="Stamm",
            items=[{"uid": "it1", "variable": "dem123", "label": "Item"}],
            missing_values="-999",
            top_categories="Kategorie",
            answer_options=[
                {"uid": "ao1", "variable": "dem123", "value": "1", "label": "männlich"}
            ],
        )
        source.keywords.add(keyword)

        result = create_question_version(
            source_question=source,
            page=self.page,
            wave_ids=[self.wave.id, self.second_wave.id],
        )

        source.refresh_from_db()
        new_question = result.question

        self.assertIsNotNone(source.version_group_id)
        self.assertEqual(source.version_number, 0)
        self.assertEqual(new_question.version_group_id, source.version_group_id)
        self.assertEqual(new_question.version_number, 1)
        self.assertIsNone(new_question.legacy_id)
        self.assertEqual(new_question.questiontext, source.questiontext)
        self.assertEqual(new_question.question_type, source.question_type)
        self.assertEqual(new_question.instruction, source.instruction)
        self.assertEqual(new_question.items[0]["variable"], "")
        self.assertEqual(new_question.answer_options[0]["variable"], "")
        self.assertEqual(
            list(new_question.keywords.values_list("id", flat=True)),
            [keyword.id],
        )
        self.assertTrue(
            WavePageQuestion.objects.filter(
                wave_page=self.page,
                question=new_question,
            ).exists()
        )
        self.assertEqual(
            set(
                WaveQuestion.objects
                .filter(question=new_question)
                .values_list("wave_id", flat=True)
            ),
            {self.wave.id, self.second_wave.id},
        )

    def test_create_version_uses_next_number_in_existing_group(self):
        group = QuestionVersionGroup.objects.create(name="Geschlecht")
        Question.objects.create(
            questiontext="Version 0",
            version_group=group,
            version_number=0,
        )
        source = Question.objects.create(
            questiontext="Version 2",
            version_group=group,
            version_number=2,
        )

        result = create_question_version(
            source_question=source,
            page=self.page,
            wave_ids=[self.wave.id],
        )

        self.assertEqual(result.question.version_group, group)
        self.assertEqual(result.question.version_number, 3)

    def test_create_version_rejects_wave_not_linked_to_page(self):
        other_survey = Survey.objects.create(name="Andere Befragung", year=2025)
        other_wave = Wave.objects.create(
            survey=other_survey,
            surveyyear="2025",
            cycle="Andere Gruppe",
            instrument=Wave.Instrument.CAWI,
        )
        source = Question.objects.create(questiontext="Ausgangsfrage")

        with self.assertRaisesMessage(
            ValueError,
            "gehört nicht zur Zielseite oder ist abgeschlossen",
        ):
            create_question_version(
                source_question=source,
                page=self.page,
                wave_ids=[other_wave.id],
            )

        source.refresh_from_db()
        self.assertIsNone(source.version_group_id)
        self.assertEqual(Question.objects.count(), 1)

    def test_create_version_rejects_page_connected_to_locked_wave(self):
        locked_wave = Wave.objects.create(
            survey=self.survey,
            surveyyear="2026",
            cycle="Abgeschlossene Gruppe",
            instrument=Wave.Instrument.CAWI,
            is_locked=True,
        )
        self.page.waves.add(locked_wave)
        source = Question.objects.create(questiontext="Ausgangsfrage")

        with self.assertRaisesMessage(
            ValueError,
            "mit einer abgeschlossenen Befragung verknüpft",
        ):
            create_question_version(
                source_question=source,
                page=self.page,
                wave_ids=[self.wave.id],
            )