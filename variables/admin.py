from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from .resources import ValLabResource, VariableResource

from django.db.models import Prefetch
from .models import ValLab, Variable, QuestionVariable


class QuestionVariableInline(admin.TabularInline):
    model = QuestionVariable
    extra = 0
    autocomplete_fields = ("question",)

@admin.register(Variable)
class VariableAdmin(ImportExportModelAdmin):
    resource_class = VariableResource

    list_display = (
        "varname",
        "varlab",
        "vallab",
        "ver",
        "gen",
        "plausi",
        "flag",
    )

    search_fields = ("varname", "varlab", "comment")
    ordering = ("varname",)

    filter_horizontal = ("waves",)

    inlines = [QuestionVariableInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Prefetch für schnelle Anzeige in list_display
        return qs.prefetch_related(
            Prefetch(
                "questions",
                queryset=Variable.questions.rel.model.objects.only("id"),
            )
        )
    
    @admin.display(description="Fragen")
    def questions_preview(self, obj):
        qs = list(obj.questions.all()[:5])
        if not qs:
            return "—"
        more = obj.questions.count() - len(qs)
        txt = ", ".join(str(q) for q in qs)
        return f"{txt}" + (f" (+{more})" if more > 0 else "")


@admin.register(ValLab)
class ValLabAdmin(ImportExportModelAdmin, admin.ModelAdmin):

    resource_class = ValLabResource

    list_display = ("vallabname", "legacy_id", "values_count", "updated_at")
    search_fields = ("vallabname", "legacy_id")
    ordering = ("vallabname",)
    list_per_page = 25

    readonly_fields = ("values_preview", "created_at", "updated_at")
    fields = ("vallabname","legacy_id","values","values_preview","created_at","updated_at",)

    def values_count(self, obj):
        try:
            return len(obj.values or [])
        except Exception:
            return "-"
    values_count.short_description = "Anzahl Werte"

    def values_preview(self, obj):
        import json
        try:
            pretty = json.dumps(obj.values or [], ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(obj.values)
        return format_html(
            '<pre style="white-space: pre-wrap; font-family: monospace; '
            'border:1px solid #ddd; padding:8px; border-radius:6px; background:#fafafa;">{}</pre>',
            mark_safe(pretty)
        )
    values_preview.short_description = "Werte (Vorschau)"
