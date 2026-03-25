from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .forms import WaveDocumentInlineForm
from django.urls import reverse
from django.utils.html import format_html

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
    form = WaveDocumentInlineForm
    extra = 1
    fields = ("title", "pdf_file", "open_pdf_link", "sort_order", "uploaded_at")
    readonly_fields = ("open_pdf_link", "uploaded_at")

    @admin.display(description="PDF öffnen")
    def open_pdf_link(self, obj):
        if obj and obj.pk:
            url = reverse("waves:wave_document_pdf", args=[obj.pk])
            return format_html('<a href="{}" target="_blank">PDF öffnen</a>', url)
        return "-"
    

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

