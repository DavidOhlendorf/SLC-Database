from django.views.generic import ListView, DetailView
from .models import Wave
from pages.models import WavePage

class SurveyListView(ListView):
    model = Wave
    template_name = "waves/survey_list.html"
    context_object_name = "waves"

    def get_queryset(self):
        return Wave.objects.order_by("-surveyyear", "cycle", "instrument")

class SurveyDetailView(DetailView):
    model = Wave
    template_name = "waves/survey_detail.html"
    context_object_name = "wave"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wave = self.object

        # alle Seiten, die mit dieser Welle verknüpft sind
        pages_qs = (
            wave.pages
            .all()
            .order_by("pagename")
        )

        ctx["pages"] = pages_qs
        return ctx