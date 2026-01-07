# pages/querysets.py
# completeness check for WavePage model

from django.db import models
from django.db.models import Q, Case, When, Value, BooleanField


class WavePageQuerySet(models.QuerySet):
    def with_completeness(self):
        missing = (
            Q(pagename__isnull=True) | Q(pagename="") |
            Q(transition_control__isnull=True) | Q(transition_control="") |
            Q(transitions__isnull=True) | Q(transitions="")
        )
        return self.annotate(
            is_incomplete=Case(
                When(missing, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )