# waves/models.py

from django.db import models
from questions.models import Question

# Das zentrale Modell für eine Befragung
class Survey(models.Model):
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Eindeutiger Name der Befragung, z. B. 'EJ 2022'"
    )

    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Jahr der Befragung"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "name"]

    def __str__(self):
        return f"{self.name}"


# Modell für eine Erhebungsgruppe innerhalb einer Befragung (wave-Name hier aus legacy-Gründen)
class Wave(models.Model):

    survey = models.ForeignKey(
        "Survey",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="waves",
        verbose_name="Befragung",
    )


    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    surveyyear = models.CharField(max_length=10)
    start_date = models.DateField(null=True, blank=True, verbose_name="Feldstart")
    end_date = models.DateField(null=True, blank=True, verbose_name="Feldende")
    cycle = models.CharField(max_length=200, verbose_name="Befragtengruppe")
    is_locked = models.BooleanField(default=False)

    class Instrument(models.TextChoices):
        CAWI = "CAWI", "CAWI"
        PAPI = "PAPI", "PAPI"

    instrument = models.CharField(max_length=10, choices=Instrument.choices, verbose_name="Erhebungsmodus")


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "cycle", "instrument"],
                name="uniq_wave_cycle_instrument_per_survey",
            )
        ]


    def save(self, *args, **kwargs):
        if self.survey and not self.surveyyear:
            self.surveyyear = str(self.survey.year) if self.survey.year else "n/a"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.survey} - {self.cycle} - {self.instrument}"
    
    @property
    def can_be_deleted(self) -> bool:
        """
        Eine Gruppe darf aus Sicherheitsgründen nur gelöscht werden, wenn:
        - sie nicht admins-seitig gesperrt ist
        - keine Fragen verknüpft sind
        - keine Seiten verknüpft sind
        """
        if self.is_locked:
            return False

        has_questions = self.wavequestion_set.exists()
        has_pages = self.pages.exists()

        return not (has_questions or has_pages)

    @property
    def delete_block_reason(self) -> str:
        """
        Begründung, warum eine Wave nicht gelöscht werden darf.
        Priorität: Sperre > Fragen > Seiten
        """
        if self.is_locked:
            return "Diese Gruppe gehört zu einer abgeschlossenen Befragung und kann nicht gelöscht werden."

        if self.wavequestion_set.exists():
            return "Diese Gruppe kann nicht gelöscht werden, weil bereits Fragen verknüpft sind."

        if self.pages.exists():
            return "Diese Gruppe kann nicht gelöscht werden, weil bereits Seiten verknüpft sind."

        return ""


class WaveQuestion(models.Model):
    wave = models.ForeignKey(Wave, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    legacy_screenshot_id = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["wave", "question"],
                name="uq_wavequestion_wave_question",
            )
        ]
    
    def __str__(self):
        return f"{self.wave} ⟷ {self.question}"
    
