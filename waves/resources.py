from import_export import resources
from .models import Wave

class WaveResource(resources.ModelResource):
    class Meta:
        model = Wave
        fields = (
            'id',
            'legacy_id',
            'name',
            'start_date',
            'end_date',
            'is_locked',
        )
