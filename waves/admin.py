from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Survey, Wave, WaveQuestion, WaveDocument
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


class WaveDocumentInline(admin.TabularInline):
    model = WaveDocument
    extra = 1
    fields = ("title", "pdf_file", "sort_order", "uploaded_at")
    readonly_fields = ("uploaded_at",)


@admin.register(Wave)
class WaveAdmin(ImportExportModelAdmin):
    resource_class = WaveResource
    list_display = ("survey", "cycle", "instrument", "start_date", "end_date", "is_locked", "document_count")
    list_filter = ("survey", "instrument", "is_locked")
    search_fields = ("cycle", "survey__name",)
    inlines = [WaveDocumentInline]

    @admin.display(description="Dokumente")
    def document_count(self, obj):
        return obj.documents.count()


@admin.register(WaveQuestion)
class WaveQuestionAdmin(ImportExportModelAdmin):
    resource_class = WaveQuestionResource
    list_display = ("wave", "question")
    list_filter = ("wave",)
    search_fields = ("question__questiontext", "wave__cycle")

