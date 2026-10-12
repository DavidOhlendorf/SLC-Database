from django.conf import settings
from django.db import models


class SLCSettings(models.Model):
    """
    Anchor model to attach global SLC permissions (Editor role).
    No rows needed.
    """
    class Meta:
        managed = True
        default_permissions = ()
        permissions = [
            ("can_edit_slc", "Can edit SLC database"),
        ]


class UserPreferences(models.Model):
    """
    Persönliche Einstellungen eines Benutzers.
    Jeder User kann genau einen Preferences-Datensatz besitzen.
    """

    class Theme(models.TextChoices):
        BERRY_AQUA = "berry-aqua", "Berry & Aqua"
        NORDIC_POP = "nordic-pop", "Nordic Pop"
        CITRUS_PLUM = "citrus-plum", "Citrus & Plum"
        SLATE_SAGE = "slate-sage", "Slate & Sage"
        CLASSIC_BLUE = "classic-blue", "Classic Blue"
        SIGNAL_POP = "signal-pop", "Signal Pop"
        DEEP_OCEAN = "deep-ocean", "Deep Ocean"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    theme = models.CharField(
        max_length=30,
        choices=Theme.choices,
        default=Theme.DEEP_OCEAN,
        verbose_name="Farbschema",
    )

    class Meta:
        verbose_name = "Benutzereinstellung"
        verbose_name_plural = "Benutzereinstellungen"

    def __str__(self):
        return f"Einstellungen: {self.user.get_username()}"