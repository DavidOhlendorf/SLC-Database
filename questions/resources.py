from import_export import resources, fields
from import_export.widgets import ManyToManyWidget, ForeignKeyWidget
from .models import Question, Keyword, ConstructPaper, Construct, QuestionScreenshot

class ConstructPaperResource(resources.ModelResource):
    class Meta:
        model = ConstructPaper
        fields = ("id", "legacy_id", "title", "filepath",)
        import_id_fields = ("legacy_id",)


class ConstructResource(resources.ModelResource):
    constructpaper = fields.Field(
        column_name="constructpaper_legacy_id",
        attribute="constructpaper",
        widget=ForeignKeyWidget(ConstructPaper, "legacy_id"),
    )

    class Meta:
        model = Construct
        fields = ("id","legacy_id","level_1","level_2","constructpaper",)
        import_id_fields = ("legacy_id",)

class KeywordResource(resources.ModelResource):
    class Meta:
        model = Keyword
        fields = ("id", "legacy_id", "name",)
        import_id_fields = ("legacy_id",)


class QuestionResource(resources.ModelResource):

    construct = fields.Field(
        column_name="construct_legacy_id",
        attribute="construct",
        widget=ForeignKeyWidget(Construct, "legacy_id"),
    )

    keywords = fields.Field(
        column_name="keywords",
        attribute="keywords",
        widget=ManyToManyWidget(Keyword, field="legacy_id")  
    )

    class Meta:
        model = Question
        fields = ("id", "legacy_id", "questiontext","construct", "keywords",)
        import_id_fields = ("legacy_id",)


class QuestionScreenshotResource(resources.ModelResource):
    legacy_id = fields.Field(column_name='screenshotID', attribute='legacy_id')
    image = fields.Field(column_name='filepath', attribute='image')
    caption = fields.Field(column_name='caption', attribute='caption')

    class Meta:
        model = QuestionScreenshot
        fields = ('id', 'legacy_id', 'image', 'caption', 'created_at')
        import_id_fields = ['legacy_id']
