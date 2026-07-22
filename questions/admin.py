from django.contrib import admin 
from import_export.admin import ImportExportModelAdmin

from django.db.models import Count

from .models import Question, Keyword, Construct, ConstructPaper, QuestionVersionGroup
from .resources import QuestionResource, KeywordResource, ConstructResource, ConstructPaperResource
from waves.models import WaveQuestion

class WaveQuestionInline(admin.TabularInline):
    model = WaveQuestion
    extra = 0

@admin.register(QuestionVersionGroup)
class QuestionVersionGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "question_count", "created_at")
    search_fields = ("name", "note")
    readonly_fields = ("created_at",)
    ordering = ("name", "id")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _question_count=Count("questions")
        )

    @admin.display(description="Fragen", ordering="_question_count")
    def question_count(self, obj):
        return obj._question_count



@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    list_display = (
        "id",
        "legacy_id",
        "questiontext",
        "version_group",
        "version_number",
    )
    search_fields = (
        "questiontext",
        "version_group__name",
    )
    list_filter = ("version_group",)
    list_select_related = ("version_group",)
    autocomplete_fields = ("version_group",)
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
