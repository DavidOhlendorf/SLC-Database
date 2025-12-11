# pages/views.py
from django.views.generic import DetailView
from django.db.models import Prefetch

from .models import WavePage, WavePageQuestion, WavePageScreenshot


class WavePageDetailView(DetailView):
    model = WavePage
    template_name = "pages/detail.html"
    context_object_name = "page"

    def get_queryset(self):
        """
        Holt die Seite inkl. verknüpfter Wellen, Fragen und Screenshots.
        """
        qs = (
            WavePage.objects
            .prefetch_related(
                "waves",  # M2M zu Wave
                Prefetch(
                    "page_questions",  # related_name aus WavePageQuestion
                    queryset=WavePageQuestion.objects.select_related("question"),
                ),
                "screenshots",  # related_name aus WavePageScreenshot
            )
        )
        return qs
