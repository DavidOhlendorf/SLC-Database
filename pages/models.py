from django.db import models
from waves.models import Wave
from questions.models import Question
from django.db.models import Q, Case, When, Value, BooleanField


# QuerySet mit Annotations zur Vollständigkeitsprüfung von Seiten
class WavePageQuerySet(models.QuerySet):
    def with_completeness(self):
        missing = (
            Q(pagename__isnull=True) | Q(pagename="") |
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
        "waves.Wave",
        through="WavePageWave",
        related_name="pages",
        blank=True,
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



# Modell für QML/XML-Code einer Befragungsseite
class WavePageQml(models.Model):
    wave_page = models.OneToOneField(
        WavePage,
        on_delete=models.CASCADE,
        related_name="qml_file",
    )

    source_filename = models.CharField(
        max_length=255,
        help_text="Ursprünglicher Dateiname der importierten XML-Datei, z. B. 'dem_08.xml'.",
    )

    xml_uid = models.CharField(
        max_length=200,
        blank=True,
        help_text="UID aus der XML-Datei, z. B. aus <zofar:page uid='dem_08'>.",
    )

    xml_content = models.TextField(
        help_text="Gesamter importierter XML-/QML-Code der Seite.",
    )

    imported_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Zeitpunkt des ersten Imports.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Zeitpunkt der letzten Aktualisierung.",
    )

    class Meta:
        ordering = ["wave_page"]
        verbose_name = "QML-Datei (page)"
        verbose_name_plural = "QML-Dateien (page)"

    def __str__(self) -> str:
        return f"{self.wave_page} – {self.source_filename}"
    

# Modell für die Verknüpfung von Seiten und Befragungswellen mit Sortierreihenfolge
class WavePageWave(models.Model):
    page = models.ForeignKey("WavePage", on_delete=models.CASCADE, related_name="wave_links")
    wave = models.ForeignKey("waves.Wave", on_delete=models.CASCADE, related_name="page_links")
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    # Fragebogenmodule
    module = models.ForeignKey(
        "waves.WaveModule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_links",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["wave", "page"], name="uq_wavepagewave_wave_page"),
        ]
        indexes = [
            models.Index(fields=["wave", "sort_order"], name="idx_wavepagewave_wave_sort"),
        ]
