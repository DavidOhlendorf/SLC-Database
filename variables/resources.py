import json
from import_export import resources, fields
from variables.models import ValLab
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from .models import Variable, ValLab
from questions.models import Question
from waves.models import Wave



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


class VariableResource(resources.ModelResource):
    vallab = fields.Field(
        column_name="vallab_ID",
        attribute="vallab",
        widget=ForeignKeyWidget(ValLab, field="legacy_id"),
    )

    question = fields.Field(
        column_name="questionID",
        attribute="question",
        widget=ForeignKeyWidget(Question, field="legacy_id"),
    )

    waves = fields.Field(
        column_name="waves",
        attribute="waves",
        widget=ManyToManyWidget(Wave, field="legacy_id"),
    )

    class Meta:
        model = Variable
        import_id_fields = ("legacy_id",)
        fields = (
            "legacy_id",
            "varname",
            "varlab",
            "vallab",
            "question",
            "waves",
            "ver",
            "gen",
            "plausi",
            "flag",
            "reason_ver",
            "reason_gen",
            "reason_plausi",
            "reason_flag",
            "comment",
        )
        skip_unchanged = True
        report_skipped = True

