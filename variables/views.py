# variables/views.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse

from accounts.mixins import EditorRequiredMixin

from django.views import View
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView
from django.views.decorators.http import require_GET, require_POST

from .models import Variable, QuestionVariableWave
from questions.models import Question
from django.db.models import Prefetch, Q
from django.db import transaction

from .forms import VariableForm




# Detail-View für die Anzeige einer Variable
class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"
    context_object_name = "variable"

    @property
    def can_edit(self):
        return self.request.user.has_perm("accounts.can_edit_slc")

    def get_queryset(self):
        qs = (
            Variable.objects
            .select_related("vallab")
            .prefetch_related(
                "waves",
                Prefetch(
                    "question_variable_wave_links",
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

        # Vollständigkeit nur für Editoren
        if self.can_edit:
            qs = qs.with_completeness()

        return qs
    

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = self.object

        links = list(v.question_variable_wave_links.all())

        # --- Frage-IDs aus den Triad-Links ---
        question_ids = {link.question_id for link in links}  # set => Reihenfolge egal

        questions_qs = Question.objects.filter(id__in=question_ids).order_by("id")
        if self.can_edit:
            questions_qs = questions_qs.with_completeness()

        questions = list(questions_qs)

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

        # Rücksprung-URL
        back = self.request.GET.get("back")
        if back and not url_has_allowed_host_and_scheme(back, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            back = None

        ctx["back_url"] = back or self.request.META.get("HTTP_REFERER") or reverse("search:search_landing")

        return ctx
    

# View für das Erstellen und Bearbeiten von Variablen
class VariableUpdateView(EditorRequiredMixin, UpdateView):
    model = Variable
    form_class = VariableForm
    template_name = "variables/variable_form.html"
    context_object_name = "variable"

    # Erweiterung des Formulars um Daten-Attribute für die JS-Validierung
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["varname"].widget.attrs.update({
            "data-check-url": reverse("variables:variable_varname_check"),
            "data-initial-value": (self.object.varname or ""),
        })
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["back_url"] = self.request.GET.get("back", "")
        ctx["varname_check_url"] = reverse("variables:variable_varname_check")
        ctx["can_delete"] = not QuestionVariableWave.objects.filter(variable=self.object, wave__is_locked=True).exists()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Variable gespeichert.")
        return super().form_valid(form)

    def get_success_url(self):
        back = self.request.GET.get("back") or self.request.POST.get("back_url") or ""
        if back and url_has_allowed_host_and_scheme(back, allowed_hosts={self.request.get_host()}):
            return back
        return self.object.get_absolute_url()
    

# View zum Löschen einer Variable
@method_decorator(require_POST, name="dispatch")
class VariableDeleteView(EditorRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        v = get_object_or_404(Variable, pk=pk)

        # prüfe in triadischem Modell, ob die Variable in einer locked Wave verwendet wird
        locked_via_triad = QuestionVariableWave.objects.filter(
            variable=v,
            wave__is_locked=True,
        ).exists()

        # prüfe in M2M, ob die Variable in einer locked Wave verknüpft ist
        locked_via_m2m = v.waves.filter(is_locked=True).exists()

        # Verhinderung der Löschung, wenn in einer locked Wave verwendet (doppelt sicher über beide Relationen)
        if locked_via_triad or locked_via_m2m:
            messages.error(
                request,
                "Diese Variable kann nicht gelöscht werden, weil sie mit mindestens einer abgeschlossenen Befragung verknüpft ist."
            )
            return redirect(v.get_absolute_url())

        # Rücksprungziel
        # an welchen Fragen hängt die Variable?
        qids = list(
            QuestionVariableWave.objects
            .filter(variable=v)
            .values_list("question_id", flat=True)
            .distinct()
        )

        # wenn nur eine Frage, dann dahin zurück, sonst zur Übrsicht
        redirect_url = None
        if len(qids) == 1:
            redirect_url = reverse("questions:question_detail", kwargs={"pk": qids[0]})
        else:
            redirect_url = reverse("waves:survey_list")

        varname = v.varname 

        v.delete()

        messages.success(request, f"Variable '{varname}' wurde gelöscht.")
        return redirect(redirect_url)



# AJAX-Endpoint für Variablen-Vorschläge
# Liefert schnelle Vorschläge für den Variablen-Connector
class VariableSuggestView(View):

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip().lower()

        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = (
            Variable.objects
            .filter(is_technical=False) # technische Variablen für den var-connector ausschließen
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
    
    
# AJAX-Endpoint: Prüft, ob ein Variablenname bereits existiert (case-insensitive)
@method_decorator(require_GET, name="dispatch")
class VariableVarnameCheckView(View):

    def get(self, request, *args, **kwargs):
        q_raw = (request.GET.get("q") or "").strip()
        q = q_raw.lower()

        if len(q) < 2:
            return JsonResponse({
                "query": q_raw,
                "normalized": q,
                "is_valid_length": False,
                "exists_exact": False,
                "suggestions": [],
            })

        exists_exact = Variable.objects.filter(varname__iexact=q).exists()

        suggestions_qs = (
            Variable.objects
            .filter(varname__istartswith=q)
            .order_by("varname")
            .values_list("varname", flat=True)[:12]
        )

        return JsonResponse({
            "query": q_raw,
            "normalized": q,
            "is_valid_length": True,
            "exists_exact": exists_exact,
            "suggestions": list(suggestions_qs),
        })


# AJAX: Quickcreate für neue Variable (nur varname, ohne Verknüpfung mit Befragungen / Questions)
# Minimalvariante für den Question-Variable-Connector
@method_decorator(require_POST, name="dispatch")
class VariableQuickCreateView(View):

    def post(self, request, *args, **kwargs):
        varname = (request.POST.get("varname") or "").strip()

        if len(varname) <2:
            return JsonResponse({"ok": False, "error": "Der Variablenname muss mindestens 2 Zeichen haben."}, status=400)
        
        if Variable.objects.filter(varname__iexact=varname).exists():
            return JsonResponse({"ok": False, "error": "Dieser Variablenname ist bereits vergeben."}, status=409)

        v = Variable.objects.create(
            varname=varname,
            is_technical=False,
        )

        return JsonResponse({
            "ok": True,
            "id": v.id,
            "varname": v.varname,
            "text": v.varname,
        })
    


# AJAX: Quickcreate für neue Variable + Verknüpfung mit einer Question + Waves
# Variante für den Start aus der Question-Detail-View
@method_decorator(require_POST, name="dispatch")
class VariableQuickCreateForQuestionView(EditorRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        varname = (request.POST.get("varname") or "").strip()
        mode = (request.POST.get("mode") or "later").strip()
        question_id = request.POST.get("question_id")
        wave_ids_raw = request.POST.getlist("wave_ids")

        if len(varname) < 2:
            return JsonResponse({"ok": False, "error": "Der Variablenname muss mindestens 2 Zeichen haben."}, status=400)

        if Variable.objects.filter(varname__iexact=varname).exists():
            return JsonResponse({"ok": False, "error": "Dieser Variablenname ist bereits vergeben."}, status=409)

        if not question_id:
            return JsonResponse({"ok": False, "error": "question_id fehlt."}, status=400)

        question = get_object_or_404(Question, pk=question_id)

        if not wave_ids_raw:
            return JsonResponse({"ok": False, "error": "Bitte wähle mindestens eine Befragungsgruppe aus."}, status=400)

        try:
            wave_ids = [int(x) for x in wave_ids_raw]
        except ValueError:
            return JsonResponse({"ok": False, "error": "Ungültige Gruppen-Auswahl."}, status=400)

        # nur Waves der Frage, die NICHT locked sind
        allowed_waves_qs = question.waves.filter(is_locked=False)
        allowed_ids = set(allowed_waves_qs.values_list("id", flat=True))

        if not set(wave_ids).issubset(allowed_ids):
            return JsonResponse(
                {"ok": False, "error": "Mindestens eine ausgewählte Befragungsgruppe ist nicht zulässig (ggf. locked)."},
                status=400
            )

        with transaction.atomic():
            v = Variable.objects.create(varname=varname, is_technical=False)

            # Triadisches Modell Question-Variable-Wave
            QuestionVariableWave.objects.bulk_create(
                [QuestionVariableWave(question=question, variable=v, wave_id=w) for w in wave_ids],
                ignore_conflicts=True,
            )

            # M2M Variable-Waves
            WavesThrough = Variable._meta.get_field("waves").remote_field.through
            WavesThrough.objects.bulk_create(
                [WavesThrough(variable_id=v.id, wave_id=w) for w in wave_ids],
                ignore_conflicts=True,
            )

        # Redirect-URL je nach Modus ("complete"--> editform mit back-Parameter vs. "later"--> Question-Detail), 
        if mode == "complete":
            back = reverse("questions:question_detail", kwargs={"pk": question.id})
            redirect_url = f"{reverse('variables:variable_edit', kwargs={'pk': v.id})}?back={back}"
        else:
            redirect_url = reverse("questions:question_detail", kwargs={"pk": question.id})

        return JsonResponse({
            "ok": True,
            "variable": {"id": v.id, "varname": v.varname},
            "redirect_url": redirect_url,
        })