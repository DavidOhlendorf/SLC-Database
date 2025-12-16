# pages/views.py
from django.views.generic import DetailView
from django.db.models import Prefetch
from waves.models import WaveQuestion


from .models import WavePage, WavePageQuestion, WavePageScreenshot


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
        return ctx