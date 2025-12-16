from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from .models import Survey, Wave, WaveQuestion
from .resources import WaveResource, WaveQuestionResource


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("name", "year", "wave_count")
    search_fields = ("name",)
    list_filter = ("year",)
    ordering = ("-year", "name")

    def wave_count(self, obj):
        return obj.waves.count()

    wave_count.short_description = "Waves"


@admin.register(Wave)
class WaveAdmin(ImportExportModelAdmin):
    resource_class = WaveResource
    list_display = ("survey", "cycle", "instrument", "start_date", "end_date", "is_locked")
    list_filter = ("survey", "instrument", "is_locked")
    search_fields = ("cycle", "survey__name", "surveyyear")


@admin.register(WaveQuestion)
class WaveQuestionAdmin(ImportExportModelAdmin):
    resource_class = WaveQuestionResource
    list_display = ("wave", "question")
    list_filter = ("wave",)
    search_fields = ("question__questiontext", "wave__cycle")

