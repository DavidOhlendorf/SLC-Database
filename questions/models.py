from django.db import models
from django.urls import reverse

class Keyword(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, unique=True)

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
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    questiontext = models.TextField()
    waves = models.ManyToManyField("waves.Wave", through="waves.WaveQuestion", related_name="questions")
    keywords = models.ManyToManyField(Keyword, related_name="questions")
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


def screenshot_upload_path(instance, filename):
    try:
        first_wq = instance.wavequestions.first()
        if first_wq:
            w = first_wq.wave
            folder = f"{w.surveyyear}_{w.instrument}".replace(" ", "_").lower()
        else:
            folder = "unsorted"
    except Exception:
        folder = "unsorted"

    return f"screenshots/{folder}/{filename}"



class QuestionScreenshot(models.Model):
    legacy_id = models.IntegerField(unique=True, null=True, blank=True)
    image = models.ImageField(upload_to=screenshot_upload_path)
    caption = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    wavequestions = models.ManyToManyField(
        "waves.WaveQuestion",
        blank=True,
        related_name="screenshots"
    )

    def __str__(self):
        return f"Screenshot {self.id}"
