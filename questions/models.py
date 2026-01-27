from django.db import models
from django.urls import reverse
from django.db.models.functions import Lower 
from django.db.models import BooleanField, Case, When, Value, Q, OuterRef, Exists
from variables.models import QuestionVariableWave  


# Completeness check for Question model
class QuestionQuerySet(models.QuerySet):

    def with_completeness(self):

        # Triad: hat die Frage überhaupt Variablen?
        triad_exists = QuestionVariableWave.objects.filter(question_id=OuterRef("pk"))

        # Keywords Exists auf M2M-through
        kw_through = Question.keywords.through
        kw_exists = kw_through.objects.filter(question_id=OuterRef("pk"))

        # Fehlende Kernelemente
        missing_core = (
            Q(questiontext__isnull=True) | Q(questiontext="") |
            Q(question_type__isnull=True) | Q(question_type="") |
            Q(answer_options__isnull=True) | Q(answer_options=[])
        )

        incomplete_expr = missing_core | ~Exists(triad_exists) | ~Exists(kw_exists)

        return self.annotate(
            is_incomplete=Case(
                When(incomplete_expr, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )


class Keyword(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, unique=False)

    class Meta:
        # Enforce case-insensitive uniqueness on 'name'
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uniq_keyword_name_lower"),
        ]

    def __str__(self):
        return self.name
    

class ConstructPaper(models.Model):
    title = models.CharField(max_length=255)
    filepath = models.CharField(max_length=500, blank=True, null=True)
    legacy_id = models.IntegerField(blank=True, null=True, unique=True)

    def __str__(self):
        return self.title or f"Konstruktpapier {self.id}"
    

class Construct(models.Model):
    level_1 = models.CharField(max_length=255, blank=True, null=True)
    level_2 = models.CharField(max_length=255, blank=True, null=True)
    constructpaper = models.ForeignKey(
        ConstructPaper,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="constructs",
    )
    legacy_id = models.IntegerField(blank=True, null=True, unique=True)

    def __str__(self):
        return f"{self.level_1} - {self.level_2}"


class Question(models.Model):

    objects = QuestionQuerySet.as_manager()

    # Ehemalige ID Access-Datenbank
    legacy_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True
    )

    # Fragetext (q)
    questiontext = models.TextField(
        blank=True,
        help_text="Fragetext (q).",
    )

    class QuestionType(models.TextChoices):
        OPEN = "open", "Offene Frage"
        SINGLE_VERTICAL = "single_vertical", "Einfachauswahl vertikal"
        SINGLE_HORIZONTAL = "single_horizontal", "Einfachauswahl horizontal"
        SINGLE_DROPDOWN = "single_dropdown", "Einfachauswahl Dropdown"
        MULTI_VERTICAL = "multi_vertical", "Mehrfachauswahl vertikal"
        MULTI_HORIZONTAL = "multi_horizontal", "Mehrfachauswahl horizontal"
        MATRIX_SINGLE_VERTICAL = "matrix_single_vertical", "Einfachauswahl-Matrix vertikal"
        MATRIX_SINGLE_HORIZONTAL = "matrix_single_horizontal", "Einfachauswahl-Matrix horizontal"
        MATRIX_MULTI = "matrix_multi", "Mehrfachauswahl-Matrix"
        SEMANTIC_DIFF = "semantic_diff", "Semantisches Differenzial"
        MATRIX_DOUBLE = "matrix_double", "Doppel-Matrix"
        DATEPICKER = "datepicker", "Datepicker"
        OTHER = "other", "Sonstiger Fragetyp / Mischtypen"

    # Fragetyp (qt)
    question_type = models.CharField(
        max_length=50,
        choices=QuestionType.choices,
        blank=True,
        help_text="Fragetyp (qt).",
    )

    # Freitext nur wenn question_type == OTHER
    question_type_other = models.CharField(
        max_length=255,
        blank=True,
        help_text="Freitext, falls 'Sonstiger Fragetyp'.",
    )


    # Instruktionstext (is)
    instruction = models.TextField(
        blank=True,
        help_text="Instruktionstext (is).",
    )

    # Itemstamm (st), v. a. für Matrizen
    item_stem = models.TextField(
        blank=True,
        help_text="Itemstamm, z. B. 'Ich bin jemand, der…' (st).",
    )

    # Items (it)
    items = models.JSONField(
        default=list,
        blank=True,
        help_text="Items der Frage als Liste von Objekten, z.B. [{'uid': 'it1', 'value': '1', 'label': 'stimme zu'}].",
    )

    # fehlende Werte (mv)
    missing_values = models.TextField(
        blank= True,
        help_text="Fehlende Werte (mv) im Format mv: Wert : anzuzeigender Wert : Wertelabel (z. B.  mv: -999 : : Das weiß ich nicht.)."
    )

    # Überkategorien (ka)
    top_categories = models.TextField(
        blank= True,
        help_text="Gruppierung von Items/Antwortoptionen nach übergeordndeten Kategorien (ka)"
    )

    # Antwortoptionen (ao)
    answer_options = models.JSONField(
    default=list,
    blank=True,
    help_text="Antwortoptionen der Frage als Liste von Objekten, z.B. [{'uid': 'ao1', 'value': '1', 'label': 'sehr gut'}].",
    
    )

    # Zugeordnete Wellen
    waves = models.ManyToManyField(
        "waves.Wave", 
        through="waves.WaveQuestion",
        related_name="questions"
    )
    
    #  Zugeordnete Schlagwörter
    keywords = models.ManyToManyField(
        Keyword,
        blank=True,
        related_name="questions"
    )

    # Zugeordnetes Konstrukt
    construct = models.ForeignKey(
        Construct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )

    def __str__(self):
        return f"Q{self.id}: {self.questiontext[:100]}"
    
    def get_absolute_url(self):
        return reverse("questions:question_detail", args=[self.pk])
    


# Legacy: required by old migrations (0007_questionscreenshot)
def screenshot_upload_path(instance, filename):
    return f"legacy/question_screenshots/{filename}"