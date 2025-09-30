from django.db import models
from questions.models import Question

class Wave(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, unique=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_locked = models.BooleanField(default=False) 

    def __str__(self):
        return self.name

class WaveQuestion(models.Model):
    wave = models.ForeignKey(Wave, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['wave', 'question'], name='unique_wave_question')
        ]

    def __str__(self):
        return f"{self.wave} ⟷ {self.question}"