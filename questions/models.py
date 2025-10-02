from django.db import models

class Keyword(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

class Question(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    questiontext = models.TextField()
    waves = models.ManyToManyField("waves.Wave", through="waves.WaveQuestion", related_name="questions")
    keywords = models.ManyToManyField(Keyword, related_name="questions")

    def __str__(self):
        return f"Q{self.id}: {self.questiontext[:100]}"

