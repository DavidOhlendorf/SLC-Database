# variables/views.py

from django.conf import settings
from django.core.paginator import Paginator

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse

from accounts.mixins import EditorRequiredMixin

from django.views import View
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView
from django.views.decorators.http import require_GET, require_POST

from waves.models import Wave, WaveQuestion

from .models import Variable, QuestionVariableWave
from questions.models import Question
from django.db.models import Prefetch, Q, F
from django.db import transaction

from .forms import VariableForm

from .versioning import parse_variable_name, variable_family_sort_key, VariableNameSchemaError

from search.services.variables import (
    build_variable_groups,
    search_variables,
    sort_variable_groups,
)

# ---- VIEWS -----------------------------------------

# ---- VIEW FÜR VARIABLENLISTE -----------------------------------------
class VariableListView(View):
    template_name = "variables/list.html"
    results_per_page = 20

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()

        wave_ids = [
            int(value)
            for value in request.GET.getlist("waves")
            if value.strip().isdigit()
        ]

        all_waves = Wave.objects.select_related("survey").order_by(
            F("survey__year").desc(nulls_last=True),
            "survey__name",
            "cycle",
            "instrument",
            "id",
        )
        selected_waves = list(
            all_waves.filter(id__in=wave_ids)
        )

        if q:
            # Mit Suchbegriff wird der
            # Suchservice der globalen Variablensuche verwendet.
            matched_variables, score_map = search_variables(
                q=q,
                wave_ids=wave_ids,
            )
            default_sort = "relevance"

        else:
            # Ohne Suchbegriff dient die Seite als Variablenkatalog.
            variables_queryset = Variable.objects.all()

            if wave_ids:
                variables_queryset = variables_queryset.filter(
                    waves__id__in=wave_ids
                )

            matched_variables = list(
                variables_queryset
                .only(
                    "id",
                    "varname",
                    "varlab",
                )
                .distinct()
            )

            score_map = {
                variable.id: 0.0
                for variable in matched_variables
            }

            default_sort = "alpha"

        sort = (
            request.GET.get("sort")
            or default_sort
        ).lower()

        if sort not in {"relevance", "alpha"}:
            sort = default_sort

        # Ohne Suchbegriff existiert keine Relevanzsortierung.
        if not q:
            sort = "alpha"

        variable_groups = build_variable_groups(
            matched_variables=matched_variables,
            score_map=score_map,
            wave_ids=wave_ids,
        )

        variable_groups = sort_variable_groups(
            variable_groups,
            sort,
        )

        # Anzahl aller konkreten Variablen in den angezeigten Familien.
        variables_in_results_count = sum(
            len(group["variables"])
            for group in variable_groups
        )

        paginator = Paginator(
            variable_groups,
            self.results_per_page,
        )
        page_obj = paginator.get_page(
            request.GET.get("page")
        )

        context = {
            "q": q,
            "sort": sort,
            "variables": page_obj.object_list,
            "variables_page": page_obj,
            "variables_count": len(variable_groups),
            "variables_in_results_count": variables_in_results_count,
            "all_waves": all_waves,
            "selected_waves": selected_waves,
            "selected_wave_ids": [
                wave.id
                for wave in selected_waves
            ],
            "show_relevance": settings.DEBUG and bool(q),
        }

        return render(
            request,
            self.template_name,
            context,
        )




# ----- Detail-View für die Anzeige einer Variable -----------------
class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"
    context_object_name = "variable"

    @property
    def can_edit(self):
        return self.request.user.has_perm("accounts.can_edit_slc")

    def get_queryset(self):
        wave_queryset = Wave.objects.select_related("survey").order_by(
            F("survey__year").desc(nulls_last=True),
            F("start_date").desc(nulls_last=True),
            "cycle",
            "instrument",
            "id",
        )

        qs = (
            Variable.objects
            .select_related("vallab")
            .prefetch_related(
                Prefetch(
                    "waves",
                    queryset=wave_queryset,
                ),
                Prefetch(
                    "question_variable_wave_links",
                    queryset=(
                        QuestionVariableWave.objects
                        .select_related(
                            "question",
                            "wave",
                            "wave__survey",
                        )
                        .order_by(
                            "question_id",
                            F("wave__survey__year").desc(nulls_last=True),
                            F("wave__start_date").desc(nulls_last=True),
                            "wave__cycle",
                            "wave__instrument",
                            "wave_id",
                        )
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
        variable = self.object

        links = list(
            variable.question_variable_wave_links.all()
        )
        direct_waves = list(variable.waves.all())


        # ---------------------------------------------------------
        # Variablenfamilie
        # ---------------------------------------------------------

        family_key = None
        family_variables = []

        try:
            parsed_variable = parse_variable_name(
                variable.varname
            )
            family_key = parsed_variable.family_key

            family_candidates = Variable.objects.filter(
                Q(varname__iexact=family_key)
                | Q(varname__istartswith=f"{family_key}_")
            ).only(
                "id",
                "varname",
                "varlab",
            )

            for candidate in family_candidates:
                try:
                    parsed_candidate = parse_variable_name(
                        candidate.varname
                    )
                except VariableNameSchemaError:
                    continue

                # Ein bloß ähnlicher Präfix reicht nicht aus.
                if parsed_candidate.family_key == family_key:
                    family_variables.append(candidate)

            family_variables.sort(
                key=lambda candidate: (
                    variable_family_sort_key(candidate.varname),
                    candidate.id,
                )
            )

        except VariableNameSchemaError:
            # Historische Variablennamen außerhalb des Schemas
            # bleiben nutzbar, erhalten aber keine
            # abgeleitete Familiennavigation.
            pass


        # ---------------------------------------------------------
        # Zugehörige Fragen
        # ---------------------------------------------------------

        question_ids = {
            link.question_id
            for link in links
        }

        questions_qs = (
            Question.objects
            .filter(id__in=question_ids)
            .order_by("id")
        )

        if self.can_edit:
            questions_qs = questions_qs.with_completeness()

        questions = list(questions_qs)


        # ---------------------------------------------------------
        # Gesperrte Fragen
        # ---------------------------------------------------------

        locked_question_ids = set()

        if self.can_edit and question_ids:
            locked_question_ids = set(
                WaveQuestion.objects.filter(
                    question_id__in=question_ids,
                    wave__is_locked=True,
                ).values_list(
                    "question_id",
                    flat=True,
                )
            )


        # ---------------------------------------------------------
        # Verwendungskontext:
        # Frage -> konkrete Befragungen
        # ---------------------------------------------------------

        wave_maps_by_qid = {}

        for link in links:
            wave_maps_by_qid.setdefault(
                link.question_id,
                {},
            )[link.wave_id] = link.wave

        waves_by_qid = {
            question_id: list(wave_map.values())
            for question_id, wave_map
            in wave_maps_by_qid.items()
        }

        question_contexts = [
            {
                "question": question,
                "waves": waves_by_qid.get(
                    question.id,
                    [],
                ),
                "is_locked": (
                    question.id in locked_question_ids
                ),
            }
            for question in questions
        ]


        # ---------------------------------------------------------
        # Wellen ohne konkrete Fragenzuordnung
        # ---------------------------------------------------------

        used_wave_ids = {
            link.wave_id
            for link in links
        }

        unassigned_waves = [
            wave
            for wave in direct_waves
            if wave.id not in used_wave_ids
        ]


        # ---------------------------------------------------------
        # Sperrstatus der Variable
        # ---------------------------------------------------------

        locked_via_triad = (
            QuestionVariableWave.objects
            .filter(
                variable=variable,
                wave__is_locked=True,
            )
            .exists()
        )

        locked_via_m2m = (
            variable.waves
            .filter(is_locked=True)
            .exists()
        )


        # ---------------------------------------------------------
        # Value-Label
        # ---------------------------------------------------------

        vallab = variable.vallab

        vallab_values = (
            sorted(
                vallab.values,
                key=lambda item: item.get("order", 0),
            )
            if (
                vallab
                and isinstance(vallab.values, list)
            )
            else []
        )


        # ---------------------------------------------------------
        # Eigenschaften
        # ---------------------------------------------------------

        flags = [
            {
                "key": "ver",
                "label": "Versioniert",
                "active": variable.ver,
                "reason": variable.reason_ver,
            },
            {
                "key": "gen",
                "label": "Generiert",
                "active": variable.gen,
                "reason": variable.reason_gen,
            },
            {
                "key": "plausi",
                "label": "Plausibilisiert",
                "active": variable.plausi,
                "reason": variable.reason_plausi,
            },
            {
                "key": "flag",
                "label": "Flag",
                "active": variable.flag,
                "reason": variable.reason_flag,
            },
        ]

        flags_active = [
            flag
            for flag in flags
            if flag["active"]
        ]


        # ---------------------------------------------------------
        # Rücksprung-URL
        # ---------------------------------------------------------

        back = self.request.GET.get("back")

        if back and not url_has_allowed_host_and_scheme(
            back,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            back = None

        back_url = (
            back
            or self.request.META.get("HTTP_REFERER")
            or reverse("search:search_landing")
        )


        # ---------------------------------------------------------
        # Kontext
        # ---------------------------------------------------------

        ctx["family_key"] = family_key
        ctx["family_variables"] = family_variables
        ctx["show_family_navigation"] = (
            len(family_variables) > 1
        )

        ctx["question_contexts"] = question_contexts
        ctx["unassigned_waves"] = unassigned_waves

        ctx["vallab_values"] = vallab_values
        ctx["flags_active"] = flags_active
        ctx["has_properties"] = bool(
            flags_active
            or variable.is_technical
            or variable.comment
        )

        ctx["variable_is_locked"] = (
            locked_via_triad
            or locked_via_m2m
        )

        ctx["back_url"] = back_url

        return ctx


# View für das Erstellen und Bearbeiten von Variablen
class VariableUpdateView(EditorRequiredMixin, UpdateView):
    model = Variable
    form_class = VariableForm
    template_name = "variables/variable_form.html"
    context_object_name = "variable"


    # dispatch-Methode überschreiben, um Sperre bei locked Waves zu implementieren
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        locked_via_triad = QuestionVariableWave.objects.filter(
            variable=self.object,
            wave__is_locked=True,
        ).exists()

        locked_via_m2m = self.object.waves.filter(is_locked=True).exists()

        if locked_via_triad or locked_via_m2m:
            messages.error(
                request,
                "Diese Variable ist Teil einer abgeschlossenen Befragung und kann hier nicht bearbeitet werden."
            )
            return redirect(reverse("variables:variable_detail", kwargs={"pk": self.object.pk}))

        return super().dispatch(request, *args, **kwargs)

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