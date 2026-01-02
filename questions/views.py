# questions/views.py
from django.views.generic import DetailView
from django.db.models import Prefetch

from .models import Question
from variables.models import QuestionVariableWave, Variable
from waves.models import Wave
from pages.models import WavePage 

class QuestionDetail(DetailView):
    model = Question
    template_name = "questions/detail.html"
    context_object_name = "question"

    def get_queryset(self):
        return (
            Question.objects
            .select_related("construct")  
            .prefetch_related(
                Prefetch(
                    "waves",
                    queryset=Wave.objects.order_by("-id"),
                )
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        question = self.object

        waves = list(question.waves.all().order_by("-id"))
        wave_param = self.request.GET.get("wave")

        active_wave = None
        if waves:
            if wave_param and any(str(w.id) == wave_param for w in waves):
                active_wave = next(w for w in waves if str(w.id) == wave_param)
            else:
                active_wave = waves[0]

        triad_qs = QuestionVariableWave.objects.none()

        if active_wave:
            triad_qs = (
                QuestionVariableWave.objects
                .filter(question=question, wave=active_wave)
                .select_related("variable")
            )
    
            # Eindeutige Variablen für die aktive Welle
            variables = (
                Variable.objects
                .filter(id__in=triad_qs.values_list("variable_id", flat=True))
                .distinct()
                .order_by("varname")
            )

            # Seite der aktiven Welle
            page = (
                WavePage.objects
                .filter(
                    page_questions__question=question,  # Link Question <-> WavePage
                    waves=active_wave,                    # Link WavePage <-> Wave
                )
                .only("id", "pagename")
                .first()
            )
        else:
            variables = Variable.objects.none()
            page = None

        if page:
            screenshots = list(page.screenshots.all())
        else:
            screenshots = []    

        ctx.update({
            "waves": waves,
            "active_wave": active_wave,
            "variables": variables,
            "question_variable_wave_links": triad_qs,
            "page": page, 
            "screenshots": screenshots,
        })
        return ctx