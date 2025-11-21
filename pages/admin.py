from django.contrib import admin

from .models import WavePage, WavePageQuestion, WavePageScreenshot


class WavePageQuestionInline(admin.TabularInline):
    model = WavePageQuestion
    extra = 1
    autocomplete_fields = ("question",)


class WavePageScreenshotInline(admin.TabularInline):
    model = WavePageScreenshot
    extra = 1


@admin.register(WavePage)
class WavePageAdmin(admin.ModelAdmin):
    list_display = ("pagename",)
    search_fields = ("pagename",)
    ordering = ("pagename",)
    inlines = [WavePageQuestionInline, WavePageScreenshotInline]

    filter_horizontal = ("waves",)  

@admin.register(WavePageQuestion)
class WavePageQuestionAdmin(admin.ModelAdmin):
    list_display = ("wave_page", "question")
    search_fields = ("wave_page__pagename", "question__questiontext")
    list_select_related = ("wave_page", "question")


@admin.register(WavePageScreenshot)
class WavePageScreenshotAdmin(admin.ModelAdmin):
    list_display = ("wave_page", "language", "device", "image_path")
    list_filter = ("language", "device")
    search_fields = ("wave_page__pagename", "image_path")
    list_select_related = ("wave_page",)
