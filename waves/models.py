from django.db import models
from questions.models import Question

class Survey(models.Model):
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Eindeutiger Survey-Name, z. B. 'EJ 2022'"
    )

    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optionales Jahr des Surveys"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "name"]

    def __str__(self):
        return f"{self.name}"




class Wave(models.Model):

    survey = models.ForeignKey(
        "Survey",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="waves",
    )


    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    surveyyear = models.CharField(max_length=10)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    cycle = models.CharField(max_length=200)
    instrument = models.CharField(max_length=50, blank=True, null=True)
    is_locked = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.surveyyear} - {self.cycle} - {self.instrument}"

class WaveQuestion(models.Model):
    wave = models.ForeignKey(Wave, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    legacy_screenshot_id = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.wave} ⟷ {self.question}"
    
