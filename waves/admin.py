from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Wave
from .resources import WaveResource

@admin.register(Wave)
class WaveAdmin(ImportExportModelAdmin):
    resource_class = WaveResource
    list_display = ('name', 'start_date', 'end_date', 'is_locked')
    search_fields = ('name',)


