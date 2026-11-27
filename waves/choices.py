from django.db import models


class QuestionnairePart(models.TextChoices):
    CORE = "core", "Core"
    EPISODES = "episodes", "Episodes"