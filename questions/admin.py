from django.contrib import admin
from .models import Question, WaveQuestion

class WaveQuestionInline(admin.TabularInline):
    model = WaveQuestion
    extra = 0

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('questiontext',)
    search_fields = ('questiontext',)
    inlines = [WaveQuestionInline]


@admin.register(WaveQuestion)
class WaveQuestionAdmin(admin.ModelAdmin):
    list_display = ('wave', 'question')
    list_filter = ('wave',)
    search_fields = ('question__questiontext', 'wave__name')
