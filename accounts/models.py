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