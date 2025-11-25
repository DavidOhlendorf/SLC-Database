from django.views.generic import DetailView
from .models import Variable


class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"
    queryset = (Variable.objects
                .select_related("vallab", "question")
                .prefetch_related("waves"))

    def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            v = ctx["object"]

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
