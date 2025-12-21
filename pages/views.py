# pages/views.py
from django.views.generic import DetailView, UpdateView
from django.urls import reverse
from django.contrib import messages

from accounts.mixins import EditorRequiredMixin

from django.db.models import Prefetch
from waves.models import WaveQuestion

from .forms import WavePageForm




from .models import WavePage, WavePageQuestion, WavePageScreenshot

# View zum Anzeigen einer Fragebogenseite
class WavePageDetailView(DetailView):
    model = WavePage
    template_name = "pages/detail.html"
    context_object_name = "page"

    def get_queryset(self):

        qs = (
            WavePage.objects
            .prefetch_related(
                "waves", 
                Prefetch(
                    "page_questions",
                    queryset=WavePageQuestion.objects.select_related("question"),
                ),
                "screenshots", 
            )
        )
        return qs


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object

        waves_qs = page.waves.all().order_by("cycle", "instrument", "id")

        # active wave aus ?wave=
        active_wave = None
        wave_id = self.request.GET.get("wave")
        if wave_id:
            try:
                active_wave = waves_qs.filter(id=int(wave_id)).first()
            except ValueError:
                active_wave = None

        if active_wave is None:
            active_wave = waves_qs.first()

        # Fragen auf der Seite (alle)
        page_questions_qs = (
            page.page_questions
            .select_related("question")
            .all()
        )

        # WICHTIG: Falls keine wave verknüpft ist, nicht filtern
        if active_wave:
            wave_question_ids = WaveQuestion.objects.filter(
                wave=active_wave
            ).values_list("question_id", flat=True)

            page_questions_qs = page_questions_qs.filter(
                question_id__in=wave_question_ids
            )

        ctx["waves"] = waves_qs
        ctx["active_wave"] = active_wave
        ctx["page_questions_filtered"] = page_questions_qs
        ctx["survey"] = active_wave.survey if active_wave and active_wave.survey_id else None

        return ctx
    
# View zum Bearbeiten einer bestehenden Fragebogenseite
class WavePageUpdateView(EditorRequiredMixin, UpdateView):
    model = WavePage
    form_class = WavePageForm
    template_name = "pages/page_form.html"
    context_object_name = "page"

    def get_success_url(self):
        # zurück zur Detailseite; wave-Parameter beibehalten, falls vorhanden
        url = reverse("pages:page-detail", args=[self.object.pk])
        wave_id = self.request.GET.get("wave")
        if wave_id:
            url = f"{url}?wave={wave_id}"
        return url

    def form_valid(self, form):
        messages.success(self.request, "Seite wurde gespeichert.")
        return super().form_valid(form)