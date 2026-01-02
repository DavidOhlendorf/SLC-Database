from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from .resources import ValLabResource, VariableResource

from django.db.models import Prefetch
from .models import ValLab, Variable, QuestionVariableWave


class QuestionVariableWaveInline(admin.TabularInline):
    model = QuestionVariableWave
    extra = 0
    autocomplete_fields = ("question", "wave")
    fields = ("question", "wave")

@admin.register(Variable)
class VariableAdmin(ImportExportModelAdmin):
    resource_class = VariableResource

    list_display = (
        "varname",
        "varlab",
        "vallab",
        "questions_preview",
        "ver",
        "gen",
        "plausi",
        "flag",
    )

    search_fields = ("varname", "varlab", "comment")
    ordering = ("varname",)

    filter_horizontal = ("waves",)

    inlines = [QuestionVariableWaveInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch(
                "question_variable_wave_links",
                queryset=QuestionVariableWave.objects.select_related("question").only(
                    "id", "variable_id", "question_id", "wave_id",
                    "question__id", "question__questiontext",
                ),
            )
        )
    
    @admin.display(description="Fragen")
    def questions_preview(self, obj):
        links = list(getattr(obj, "question_variable_wave_links").all())
        if not links:
            return "—"

        # unique questions in Reihenfolge des Auftretens
        seen = set()
        qs = []
        for l in links:
            q = l.question
            if q.id not in seen:
                seen.add(q.id)
                qs.append(q)
            if len(qs) >= 5:
                break

        # total unique questions
        total = len({l.question_id for l in links})
        more = total - len(qs)

        txt = ", ".join(str(q) for q in qs)
        return txt + (f" (+{more})" if more > 0 else "")



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
