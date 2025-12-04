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

    # Ehemalige ID Access-Datenbank
    legacy_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True
    )

    # Fragetext (qt)
    questiontext = models.TextField(
        help_text="Fragetext (qt).",
    )

    class QuestionType(models.TextChoices):
        OPEN = "open", "Offene Frage"
        SINGLE_VERTICAL = "single_vertical", "Einfachauswahl vertikal"
        SINGLE_HORIZONTAL = "single_horizontal", "Einfachauswahl horizontal"
        MULTI_VERTICAL = "multi_vertical", "Mehrfachauswahl vertikal"
        MULTI_HORIZONTAL = "multi_horizontal", "Mehrfachauswahl horizontal"
        MATRIX_SINGLE = "matrix_single", "Einfachauswahl-Matrix"
        MATRIX_MULTI = "matrix_multi", "Mehrfachauswahl-Matrix"
        SEMANTIC_DIFF = "semantic_diff", "Semantisches Differenzial"
        OTHER = "other", "Sonstiger Fragetyp"

    # Fragetyp (qt)
    question_type = models.CharField(
        max_length=50,
        choices=QuestionType.choices,
        blank=True,
        help_text="Fragetyp (qt).",
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

    # Zugeordnete Wellen
    waves = models.ManyToManyField(
        "waves.Wave", 
        through="waves.WaveQuestion",
        related_name="questions"
    )
    
    #  Zugeordnete Schlagwörter
    keywords = models.ManyToManyField(
        Keyword,
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
        return reverse("question_detail", args=[self.pk])


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
