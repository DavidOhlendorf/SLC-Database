from django.db import models

class Wave(models.Model):
    name = models.CharField(max_length=200, unique=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)  # entspricht deiner „Welle sperren“-Logik

    def __str__(self):
        return self.name
