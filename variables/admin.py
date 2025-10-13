from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from .resources import ValLabResource

from .models import ValLab


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
