# variables/resources.py
import json
from import_export import resources, fields
from variables.models import ValLab


class ValLabResource(resources.ModelResource):
    legacy_id = fields.Field(attribute="legacy_id", column_name="legacy_id")
    vallabname = fields.Field(attribute="vallabname", column_name="vallabname")
    values = fields.Field(attribute="values", column_name="values")

    class Meta:
        model = ValLab
        import_id_fields = ["legacy_id"]
        fields = ("legacy_id", "vallabname", "values")
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        
        raw = row.get("values", "")
        if raw in (None, "", "[]"):
            row["values"] = []
            return

        if isinstance(raw, list):
            return
        try:
            row["values"] = json.loads(str(raw))
        except Exception as e:

            raise ValueError(f"Ungültiges JSON in 'values': {raw!r}. Fehler: {e}")
