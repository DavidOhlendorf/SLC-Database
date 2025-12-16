from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from .models import Survey, Wave, WaveQuestion
from .resources import WaveResource, WaveQuestionResource
from questions.models import QuestionScreenshot


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


class QuestionScreenshotInline(admin.TabularInline):
    model = QuestionScreenshot.wavequestions.through
    extra = 1
    verbose_name = "Screenshot"
    verbose_name_plural = "Screenshots"
    autocomplete_fields = ["questionscreenshot"]


@admin.register(WaveQuestion)
class WaveQuestionAdmin(ImportExportModelAdmin):
    resource_class = WaveQuestionResource
    list_display = ("wave", "question")
    list_filter = ("wave",)
    search_fields = ("question__questiontext", "wave__cycle")
    readonly_fields = ("preview_screenshots",)

    def preview_screenshots(self, obj):
        shots = obj.screenshots.all()
        if not shots.exists():
            return "—"

        html = ""
        for s in shots:
            if s.image:
                html += format_html(
                    '<div style="margin-bottom:8px;">'
                    '<img src="{}" width="180" style="border-radius:6px; border:1px solid #555;"><br>'
                    '<small style="color:#ccc;">{}</small>'
                    '</div>',
                    s.image.url,
                    s.caption or f"Screenshot #{s.legacy_id or s.id}"
                )
        return format_html(html)

    preview_screenshots.short_description = "Verknüpfte Screenshots"
