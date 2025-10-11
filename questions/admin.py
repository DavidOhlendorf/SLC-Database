from django.contrib import admin 
from import_export.admin import ImportExportModelAdmin
from .models import Question, Keyword, Construct, ConstructPaper, QuestionScreenshot
from .resources import QuestionResource, KeywordResource, ConstructResource, ConstructPaperResource, QuestionScreenshotResource
from waves.models import WaveQuestion
from django.utils.html import format_html

class WaveQuestionInline(admin.TabularInline):
    model = WaveQuestion
    extra = 0

@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    list_display = ("id", "legacy_id", "questiontext",)
    search_fields = ('questiontext',)
    inlines = [WaveQuestionInline]


@admin.register(Keyword)
class KeywordAdmin(ImportExportModelAdmin):
    resource_class = KeywordResource
    list_display = ("id", "legacy_id", "name")
    search_fields = ("name",)


@admin.register(Construct)
class ConstructAdmin(ImportExportModelAdmin):
    resource_class = ConstructResource
    list_display = ("id", "legacy_id", "level_1", "level_2", "constructpaper")
    search_fields = ("level_1","level_2",)

@admin.register(ConstructPaper)
class ConstructPaperAdmin(ImportExportModelAdmin):
    resource_class = ConstructPaperResource
    list_display = ("id", "legacy_id", "title", "filepath")
    search_fields = ("title",)

@admin.register(QuestionScreenshot)
class QuestionScreenshotAdmin(ImportExportModelAdmin):
    resource_class = QuestionScreenshotResource
    list_display = ("id", "legacy_id", "preview", "caption", "created_at")
    search_fields = ("caption",)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="90" style="border-radius:4px;" />', obj.image.url)
        return "—"
    preview.short_description = "Vorschau"
