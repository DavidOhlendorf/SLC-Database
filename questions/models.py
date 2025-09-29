from django.db import models
from waves.models import Wave

class Question(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    questiontext = models.TextField()
    waves = models.ManyToManyField(Wave, through='WaveQuestion', related_name='questions')

    def __str__(self):
        return self.questiontext

class WaveQuestion(models.Model):
    wave = models.ForeignKey(Wave, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('wave', 'question') 

    def __str__(self):
        return f"{self.wave} ⟷ Q{self.question_id}"
