from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Question, WaveQuestion
from .resources import QuestionResource, WaveQuestionResource

class WaveQuestionInline(admin.TabularInline):
    model = WaveQuestion
    extra = 0

@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    list_display = ('questiontext',)
    search_fields = ('questiontext',)
    inlines = [WaveQuestionInline]


@admin.register(WaveQuestion)
class WaveQuestionAdmin(ImportExportModelAdmin):
    resource_class = WaveQuestionResource
    list_display = ('wave', 'question')
    list_filter = ('wave',)
    search_fields = ('question__questiontext', 'wave__name')

