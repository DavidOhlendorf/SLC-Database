from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse, path
from django.shortcuts import render

from .forms import ScreenshotImportForm
from .services.screenshot_import import import_screenshots_from_csv

from .models import WavePage, WavePageQuestion, WavePageScreenshot


# Inline: Fragen auf der Seite
class WavePageQuestionInline(admin.TabularInline):
    model = WavePageQuestion
    extra = 1
    

    verbose_name = "Frage auf Seite"
    verbose_name_plural = (
        "Fragen auf dieser Seite "
        "(Hinweis: Es werden nur Fragen angezeigt,"
        "die mit mind. einer Befragung verknüpft sind, zu der diese Seite gehört.)"
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "question":
            QuestionModel = db_field.remote_field.model

            # Aktuelle WavePage über die object_id der Change-URL bestimmen
            object_id = request.resolver_match.kwargs.get("object_id")

            # Change-View: object_id vorhanden
            if object_id:
                wave_page = WavePage.objects.filter(pk=object_id).first()

                if wave_page is not None:
                    waves = wave_page.waves.all()

                    if waves.exists():
                        kwargs["queryset"] = (
                            QuestionModel.objects.filter(
                                wavequestion__wave__in=waves
                            ).distinct()
                        )
                    else:
                        # Page hat keine Waves → keine Fragen auswählbar
                        kwargs["queryset"] = QuestionModel.objects.none()
                else:
                    # Sicherheitsfallback
                    kwargs["queryset"] = QuestionModel.objects.none()
            else:
                # Add-View (neue Page): keine Fragen auswählbar
                kwargs["queryset"] = QuestionModel.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class WavePageScreenshotInline(admin.TabularInline):
    model = WavePageScreenshot
    extra = 1



@admin.register(WavePage)
class WavePageAdmin(admin.ModelAdmin):
    list_display = ("pagename", "get_waves")
    search_fields = ("pagename",)
    ordering = ("pagename",)

    inlines = [WavePageQuestionInline, WavePageScreenshotInline]

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def add_view(self, request, form_url="", extra_context=None):
        messages.info(
            request,
            (
                "Hinweis: Bitte wählen Sie zuerst die Wellen aus und klicken Sie "
                "auf „Speichern“. Danach können Sie in der nächsten Ansicht "
                "Fragen und Screenshots hinzufügen."
            ),
        )
        return super().add_view(request, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        if "_addanother" in request.POST:
            return super().response_add(request, obj, post_url_continue)

        opts = self.model._meta
        change_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=(obj.pk,),
            current_app=self.admin_site.name,
        )
        return HttpResponseRedirect(change_url)

    def get_waves(self, obj):
        return ", ".join(str(w) for w in obj.waves.all())

    get_waves.short_description = "Befragungen"



@admin.register(WavePageScreenshot)
class WavePageScreenshotAdmin(admin.ModelAdmin):
    list_display = ("wave_page", "language", "device", "image_path")
    search_fields = ("wave_page__pagename", "image_path", "language", "device")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-screenshots/",
                self.admin_site.admin_view(self.import_screenshots_view),
                name="pages_wavepagescreenshot_import",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["screenshot_import_url"] = "import-screenshots/"
        return super().changelist_view(request, extra_context=extra_context)

    def import_screenshots_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Screenshots importieren",
        }

        if request.method == "POST":
            form = ScreenshotImportForm(request.POST, request.FILES)
            if form.is_valid():
                summary = import_screenshots_from_csv(
                    uploaded_file=form.cleaned_data["metadata_file"],
                    screenshot_dir=form.cleaned_data["screenshot_dir"],
                    wave_ids=list(form.cleaned_data["waves"].values_list("id", flat=True)),
                    execute_import=form.cleaned_data["execute_import"],
                    replace_existing=form.cleaned_data["replace_existing"],
                )

                if form.cleaned_data["execute_import"]:
                    messages.success(
                        request,
                        f"Import abgeschlossen: {summary.imported} importiert, "
                        f"{summary.replaced} ersetzt, "
                        f"{summary.skipped_existing} übersprungen, "
                        f"{summary.missing_page} ohne Seite, "
                        f"{summary.missing_file} ohne Datei, "
                        f"{summary.ambiguous_page} mehrdeutig, "
                        f"{summary.invalid_rows} ungültig."
                    )
                else:
                    messages.info(
                        request,
                        f"Vorschau erstellt: {summary.total_rows} Zeilen geprüft."
                    )

                context["form"] = form
                context["summary"] = summary
                return render(request, "admin/pages/screenshot_import.html", context)
        else:
            form = ScreenshotImportForm()

        context["form"] = form
        return render(request, "admin/pages/screenshot_import.html", context)
    


@admin.register(WavePageQuestion)
class WavePageQuestionAdmin(admin.ModelAdmin):
    list_display = ("wave_page", "question")
    search_fields = ("wave_page__pagename", "question__questiontext")
    list_select_related = ("wave_page", "question")