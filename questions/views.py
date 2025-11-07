# questions/views.py
from django.views.generic import DetailView
from django.db.models import Prefetch
from .models import Question
from variables.models import Variable
from waves.models import Wave

class QuestionDetail(DetailView):
    model = Question
    template_name = "questions/detail.html"
    context_object_name = "question"

    def get_queryset(self):
        return (
            Question.objects
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

        waves = list(question.waves.all())
        wave_param = self.request.GET.get("wave")

        active_wave = None
        if waves:
            if wave_param and any(str(w.id) == wave_param for w in waves):
                active_wave = next(w for w in waves if str(w.id) == wave_param)
            else:
                active_wave = waves[0]

        if active_wave:
            variables = (
                Variable.objects
                .filter(question=question, waves=active_wave)
                .only("id", "varname", "varlab")
                .order_by("varname")
            )
        else:
            variables = Variable.objects.none()

        ctx.update({
            "waves": waves,
            "active_wave": active_wave,
            "variables": variables,
        })
        return ctx
