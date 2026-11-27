from django import forms

from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .forms import WaveDocumentInlineForm
from django.urls import reverse
from django.utils.html import format_html

from .models import Survey, Wave, WaveQuestion, WaveDocument, WaveModule
from .resources import WaveResource


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
class WaveQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "wave",
        "question",
        "legacy_screenshot_id",
    )
    list_filter = ("wave",)
    search_fields = (
        "question__questiontext",
        "wave__cycle",
    )

    readonly_fields = (
        "wave",
        "question",
        "legacy_screenshot_id",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class WaveModuleAdminForm(forms.ModelForm):

    class Meta:
        model = WaveModule
        fields = "__all__"

    def clean_questionnaire_part(self):
        part = self.cleaned_data["questionnaire_part"]

        if self.instance.pk:
            incompatible_links = (
                self.instance.page_links
                .exclude(page__questionnaire_part=part)
            )

            if incompatible_links.exists():
                raise forms.ValidationError(
                    "Der Fragebogenteil kann nicht geändert werden, "
                    "da dieses Modul Seiten eines anderen "
                    "Fragebogenteils enthält. Bitte entferne "
                    "zunächst die entsprechenden Seitenzuordnungen."
                )

        return part


@admin.register(WaveModule)
class WaveModuleAdmin(admin.ModelAdmin):
    form = WaveModuleAdminForm

    list_display = (
        "name",
        "questionnaire_part",
        "wave",
        "sort_order",
    )

    list_filter = (
        "questionnaire_part",
        "wave__survey",
        "wave__instrument",
    )

    search_fields = (
        "name",
        "wave__survey__name",
        "wave__cycle",
    )

    list_select_related = (
        "wave",
        "wave__survey",
    )

    ordering = (
        "wave",
        "sort_order",
    )

    readonly_fields = (
        "wave",
        "name",
        "sort_order",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
        