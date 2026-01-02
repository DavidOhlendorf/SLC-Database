from django.views.generic import DetailView

from questions.models import Question
from .models import Variable
from django.db.models import Prefetch


class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"
    queryset = (
        Variable.objects
        .select_related("vallab")
        .prefetch_related("waves")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=Question.objects.only("id", "questiontext").order_by("id"),
            )
        )
    )
    

    def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            v = ctx["object"]

            # Fragen: vorbereitet fürs Template
            qs = list(v.questions.all())
            ctx["questions"] = qs
            ctx["questions_count"] = len(qs)
            ctx["single_question"] = qs[0] if len(qs) == 1 else None
            ctx["questions_preview"] = qs[:5]
            ctx["questions_more_count"] = max(len(qs) - 5, 0)

            vallab = v.vallab
            ctx["vallab_values"] = (
                sorted(vallab.values, key=lambda x: x.get("order", 0))
                if (vallab and isinstance(vallab.values, list)) else []
            )

            flags = [
                {"key": "ver",    "label": "versioniert",     "active": v.ver,    "reason": v.reason_ver},
                {"key": "gen",    "label": "generiert",       "active": v.gen,    "reason": v.reason_gen},
                {"key": "plausi", "label": "plausibilisiert", "active": v.plausi, "reason": v.reason_plausi},
                {"key": "flag",   "label": "flag",            "active": v.flag,   "reason": v.reason_flag},
            ]
            ctx["flags_active"] = [f for f in flags if f["active"]]
            ctx["back_url"] = self.request.GET.get("back")

            return ctx
