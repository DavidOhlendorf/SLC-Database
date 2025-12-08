from django.views.generic import ListView
from waves.models import Wave

class QuestionnaireWaveListView(ListView):
    model = Wave
    template_name = "pages/questionnaire_list.html"
    context_object_name = "waves"

    def get_queryset(self):
        return Wave.objects.order_by("-surveyyear", "cycle", "instrument")
