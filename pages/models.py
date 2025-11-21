from django.db import models

from waves.models import Wave
from questions.models import Question


class WavePage(models.Model):

    wave = models.ForeignKey(
        Wave,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    pagename = models.CharField(
        max_length=200,
        help_text="Interner Seitenname, z.B. 'dem123'.",
    )

    class Meta:
        unique_together = ("wave", "pagename")
        ordering = ["wave", "pagename"]

    def __str__(self) -> str:
        return f"{self.wave} – {self.pagename}"


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

    def __str__(self) -> str:
        return f"{self.wave_page} – {self.question}"


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

    def __str__(self) -> str:
        return f"{self.wave_page} – {self.language}/{self.device}"
