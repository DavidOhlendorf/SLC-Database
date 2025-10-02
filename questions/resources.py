from import_export import resources, fields
from import_export.widgets import ManyToManyWidget
from .models import Question, Keyword

class KeywordResource(resources.ModelResource):
    class Meta:
        model = Keyword
        fields = ("id", "legacy_id", "name",)
        import_id_fields = ("legacy_id",)


class QuestionResource(resources.ModelResource):
    keywords = fields.Field(
        column_name="keywords",
        attribute="keywords",
        widget=ManyToManyWidget(Keyword, field="legacy_id")  
    )

    class Meta:
        model = Question
        fields = ("id", "legacy_id", "questiontext", "keywords",)
        import_id_fields = ("legacy_id",)
