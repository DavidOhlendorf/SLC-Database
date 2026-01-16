from django.db import models
from waves.models import Wave
from questions.models import Question
from django.db.models import Q, Case, When, Value, BooleanField


# QuerySet mit Annotations zur Vollständigkeitsprüfung von Seiten
class WavePageQuerySet(models.QuerySet):
    def with_completeness(self):
        missing = (
            Q(pagename__isnull=True) | Q(pagename="") |
            Q(transition_control__isnull=True) | Q(transition_control="") |
            Q(transitions__isnull=True) | Q(transitions="")
        )
        return self.annotate(
            is_incomplete=Case(
                When(missing, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

# Modell für Befragungsseiten
class WavePage(models.Model):

    objects = WavePageQuerySet.as_manager()
    
    waves = models.ManyToManyField(
        Wave,
        related_name="pages",
        blank=True,
        help_text="Befragtengruppen, die diese Seite sehen.",
    )

    # Interner Seitenname (pn)
    pagename = models.CharField(
        max_length=200,
        help_text="Interner Seitenname, z.B. 'dem_123' (pn).",
    )

    # Überschrift auf der Seite (hl)
    page_heading = models.TextField(
        max_length=255,
        blank=True,
        help_text="Überschrift der Seite (hl).",
    )

    # Einleitungstext auf der Seite (in)
    introduction = models.TextField(
        blank=True,
        help_text="Einleitungstext auf Seitenebene (in).",
    )

    # Transitionskontrolle (tc)
    transition_control = models.TextField(
        blank=True,
        help_text="Transitionskontrolle (tc).",
    )

    # Einblendbedingungen (vc)
    visibility_conditions = models.TextField(
        blank=True,
        help_text="Einblendbedingungen (vc).",
    )

    # Antwortvalidierungen (av)
    answer_validations = models.TextField(
        blank=True,
        help_text="Antwortvalidierungen (av).",
    )

    # Korrekturhinweise (kh)
    correction_notes = models.TextField(
        blank=True,
        help_text="Korrekturhinweise (kh).",
    )

    # Forcierungsvariablen (fv)
    forcing_variables = models.TextField(
        blank=True,
        help_text="Forcierungsvariablen (fv).",
    )

    # Hilfsvariablen (hv)
    helper_variables = models.TextField(    
        blank=True,
        help_text="Hilfsvariablen (hv).",
    )

    # Steuerungsvariablen (sv)
    control_variables = models.TextField(
        blank=True,
        help_text="Steuerungsvariablen (sv).",
    )

    # Formatierung (fo)
    formatting = models.TextField(
        blank=True,
        help_text="Formatierung (fo).",
    )

    # Seitenübergänge (tr)
    transitions = models.TextField(
        blank=True,
        help_text="Filter (tr).",
    )

    # Programmierhinweise zur Seite (hi)
    page_programming_notes = models.TextField(
        blank=True,
        help_text="Zusätzliche Hinweise zur Programmierung (hi).",
    )



    class Meta:
        ordering = ["pagename"]
        verbose_name = "page"
        verbose_name_plural = "pages"

    def __str__(self) -> str:
        return self.pagename



# Modell für Fragen auf Befragungsseiten
class WavePageQuestion(models.Model):

    wave_page = models.ForeignKey(
        WavePage,
        on_delete=models.CASCADE,
        related_name="page_questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="page_links",
    )

    class Meta:
        unique_together = ("wave_page", "question")
        ordering = ["wave_page", "question"]
        verbose_name = "questions on page"
        verbose_name_plural = "questions on page"

    def __str__(self) -> str:
        return f"{self.wave_page} – {self.question}"



# Modell für Screenshots von Befragungsseiten
class WavePageScreenshot(models.Model):

    wave_page = models.ForeignKey(
        WavePage,
        on_delete=models.CASCADE,
        related_name="screenshots",
    )

    image_path = models.CharField(
        max_length=500,
        help_text="Pfad/Dateiname zum Screenshot (z.B. im media-Ordner).",
    )

    language = models.CharField(
        max_length=5,
        default="de",
        help_text="Sprache, z.B. 'de' oder 'en'.",
    )

    device = models.CharField(
        max_length=20,
        default="desktop",
        help_text="z.B. 'desktop' oder 'mobile'.",
    )

    class Meta:
        ordering = ["wave_page", "language", "device"]
        verbose_name = "Screenshot (page)"
        verbose_name_plural = "Screenshots (page)"

    def __str__(self) -> str:
        return f"{self.wave_page} – {self.language}/{self.device}"
