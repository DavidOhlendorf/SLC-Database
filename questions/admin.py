from django.contrib import admin 
from import_export.admin import ImportExportModelAdmin
from .models import Question
from .resources import QuestionResource
from waves.models import WaveQuestion

class WaveQuestionInline(admin.TabularInline):
    model = WaveQuestion
    extra = 0

@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    list_display = ('questiontext',)
    search_fields = ('questiontext',)
    inlines = [WaveQuestionInline]
