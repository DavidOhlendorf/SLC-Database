# variables/models.py
from django.db import models
from django.core.exceptions import ValidationError


def validate_vallab_values(value):
    """
    Erwartet eine Liste von Dicts mit Keys: value (int), order (int), text (str).
    Beispiel: [{"value":1, "order":1, "text":"Ja"}, ...]
    """
    if value is None:
        return
    if not isinstance(value, list):
        raise ValidationError("values muss eine Liste sein.")
    orders = []
    for i, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValidationError(f"Eintrag {i} ist kein Objekt (Dict).")
        missing = {"value", "order", "text"} - set(item.keys())
        if missing:
            raise ValidationError(f"Eintrag {i} fehlt/fehlen Schlüssel: {', '.join(sorted(missing))}.")
        if not isinstance(item["value"], int):
            raise ValidationError(f"Eintrag {i}: 'value' muss Integer sein.")
        if not isinstance(item["order"], int):
            raise ValidationError(f"Eintrag {i}: 'order' muss Integer sein.")
        if not isinstance(item["text"], str):
            raise ValidationError(f"Eintrag {i}: 'text' muss String sein.")
        orders.append(item["order"])
    if len(orders) != len(set(orders)):
        raise ValidationError("Die 'order'-Werte müssen innerhalb eines Labelsets eindeutig sein.")


class ValLab(models.Model):
    legacy_id = models.IntegerField(null=True, blank=True, unique=True, db_index=True)
    vallabname = models.CharField(max_length=255, unique=True)
    values = models.JSONField(default=list, validators=[validate_vallab_values],help_text="Liste von Objekten mit Schlüsseln value (int), order (int), text (str).")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("vallabname",)

    def __str__(self):
        return self.vallabname

    # Hilfsfunktionen
    def as_choices(self):
        """[(value, text)] in definierter 'order'—Reihenfolge."""
        items = sorted(self.values, key=lambda x: x.get("order", 0))
        return [(item["value"], item["text"]) for item in items]

    def value_map(self):
        """{value: text} für schnelle Nachschlagezwecke."""
        return {item["value"]: item["text"] for item in self.values}
