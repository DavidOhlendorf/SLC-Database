from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Wave, WaveQuestion
from .resources import WaveResource, WaveQuestionResource

@admin.register(Wave)
class WaveAdmin(ImportExportModelAdmin):
    resource_class = WaveResource
    list_display = ('name', 'start_date', 'end_date', 'is_locked')
    search_fields = ('name',)

@admin.register(WaveQuestion)
class WaveQuestionAdmin(ImportExportModelAdmin):
    resource_class = WaveQuestionResource
    list_display = ('wave', 'question')
    list_filter = ('wave',)
    search_fields = ('question__questiontext', 'wave__name')
