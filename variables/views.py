from django.views.generic import DetailView

from questions.models import Question
from .models import Variable, QuestionVariableWave
from django.db.models import Prefetch, Q

from django.http import JsonResponse
from django.views import View


class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"
    queryset = (
            Variable.objects
            .select_related("vallab")
            .prefetch_related(
                "waves",  # (Existenz in Waves)
                Prefetch(
                    "question_variable_wave_links",  # Triad-Links: Question-Variable-Wave
                    queryset=(
                        QuestionVariableWave.objects
                        .select_related("question", "wave")
                        .only("id", "question_id", "variable_id", "wave_id",
                            "question__id", "question__questiontext",
                            "wave__id", "wave__cycle", "wave__instrument")
                        .order_by("question_id", "-wave_id")
                    ),
                ),
            )
        )
    

    def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            v = ctx["object"]


             # --- Triad: Verwendung der Variable in Fragen/Waves ---
            links = list(getattr(v, "question_variable_wave_links").all())

            # eindeutige Fragen
            questions = []
            seen_qids = set()
            for link in links:
                q = link.question
                if q.id not in seen_qids:
                    seen_qids.add(q.id)
                    questions.append(q)

            # Mapping: Frage -> Waves, in denen die Variable bei dieser Frage genutzt wird
            waves_by_qid = {}
            for link in links:
                waves_by_qid.setdefault(link.question_id, []).append(link.wave)

            # optional: eindeutige "used waves" (nur aus Triad)
            used_waves = []
            seen_wids = set()
            for link in links:
                w = link.wave
                if w.id not in seen_wids:
                    seen_wids.add(w.id)
                    used_waves.append(w)


            # Fragen: vorbereitet fürs Template
            ctx["triad_links"] = links
            ctx["questions"] = questions
            ctx["questions_count"] = len(questions)
            ctx["single_question"] = questions[0] if len(questions) == 1 else None
            ctx["questions_preview"] = questions[:5]
            ctx["questions_more_count"] = max(len(questions) - 5, 0)

            ctx["waves_by_question_id"] = waves_by_qid
            ctx["used_waves"] = used_waves  # Waves, in denen die Variable irgendwo genutzt wird

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

# AJAX-Endpoint für Variable-Vorschläge
# Liefert schnelle Vorschläge für strukturierte Variablennamen
class VariableSuggestView(View):

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip().lower()

        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = (
            Variable.objects
            .filter(
                Q(varname__istartswith=q) |
                Q(varname__icontains=q)   # optional (Performance noch testen)
            )
            .order_by("varname")
            .only("id", "varname", "varlab")[:30]
        )

        results = []
        for v in qs:
            label = v.varname
            if v.varlab:
                lab = v.varlab.strip()
                if len(lab) > 80:
                    lab = lab[:77] + "…"
                label = f"{v.varname} — {lab}"

            results.append({
                "value": v.id,
                "text": label,
            })

        return JsonResponse(results, safe=False)