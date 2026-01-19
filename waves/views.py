from itertools import groupby

from django.views.generic import ListView, TemplateView, CreateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.forms import inlineformset_factory
from django.http import Http404
from django.db import transaction
from django.db.models import Count, Min, Max, Prefetch
from django.shortcuts import redirect
from django.contrib import messages

from .models import Survey, Wave, WaveQuestion
from pages.models import WavePageQuestion, WavePage, WavePageWave

from .forms import SurveyCreateForm, WaveFormSet
from pages.forms import WavePageCreateForm

from django.core.exceptions import PermissionDenied
from accounts.mixins import EditorRequiredMixin



class SurveyListView(ListView):
    template_name = "waves/survey_list.html"
    context_object_name = "surveys"

    def get_queryset(self):
        waves_qs = Wave.objects.order_by("cycle", "instrument", "id")

        surveys = (
            Survey.objects
            .annotate(
                wave_count=Count("waves", distinct=True),
                start_min=Min("waves__start_date"),
                end_max=Max("waves__end_date"),
            )
            .prefetch_related(Prefetch("waves", queryset=waves_qs, to_attr="waves_list"))
            .order_by("-year", "name")
        )
        return surveys


class SurveyDetailView(TemplateView):
    template_name = "waves/survey_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        survey_name = self.kwargs["survey_name"]

        survey = Survey.objects.filter(name=survey_name).first()
        if not survey:
            raise Http404("Survey not found")

        waves_qs = (
            Wave.objects
            .filter(survey=survey)
            .order_by("cycle", "instrument", "id")
        )

        ctx["wave_formset"] = WaveFormSet(self.request.POST or None, prefix="waves")
        ctx["survey"] = survey
        ctx["waves"] = waves_qs
         # Formular für "Neue Seite" (Modal)
        ctx["page_create_form"] = WavePageCreateForm(survey=survey)

        if not waves_qs.exists():
            ctx["is_all_mode"] = False
            ctx["active_wave"] = None
            ctx["pages"] = WavePage.objects.none()
            ctx["page_question_counts"] = {}
            return ctx

        wave_param = self.request.GET.get("wave")
        is_all_mode = (wave_param == "all")

        active_wave = None
        if not is_all_mode and wave_param:
            try:
                active_wave = waves_qs.filter(id=int(wave_param)).first()
            except ValueError:
                active_wave = None

        if not is_all_mode and active_wave is None:
            active_wave = waves_qs.first()

        ctx["is_all_mode"] = is_all_mode
        ctx["active_wave"] = active_wave

        # ------------------------------------------------------------
        # ALL MODE: Gesamtübersicht, getrennt nach Instrument
        # ------------------------------------------------------------
        if is_all_mode:
            instrument_groups = []

            waves_sorted = waves_qs.order_by("instrument", "cycle", "id")

            def instrument_key(w):
                return (w.instrument or "Unbekannt")

            for instrument, wgroup in groupby(waves_sorted, key=instrument_key):
                wlist = list(wgroup)
                if not wlist:
                    continue

                pages_qs = (
                    WavePage.objects
                    .with_completeness()
                    .filter(waves__in=wlist)
                    .distinct()
                    .prefetch_related("waves")
                    .order_by("pagename")
                )

                wave_ids_set = set(w.id for w in wlist)
                page_wave_tags = {}
                for p in pages_qs:
                    page_wave_tags[p.id] = [w for w in p.waves.all() if w.id in wave_ids_set]

                # Gesperrte Befragungsgruppen ermitteln
                locked_wave_ids = {w.id for w in wlist if w.is_locked}

                # Prüfen, ob Seite mit gesperrter Befragungsgruppe verknüpft ist und in dict speichern
                page_delete_blocked = {}
                for p in pages_qs:
                    waves_for_page_in_group = page_wave_tags[p.id]
                    page_delete_blocked[p.id] = any(w.id in locked_wave_ids for w in waves_for_page_in_group)


                instrument_groups.append({
                    "instrument": instrument,
                    "waves": wlist,
                    "pages": pages_qs,
                    "page_wave_tags": page_wave_tags,
                    "default_wave_id": wlist[0].id,
                    "page_delete_blocked": page_delete_blocked,
                })

            ctx["instrument_groups"] = instrument_groups
            return ctx

        # ------------------------------------------------------------
        # WAVE MODE: (Pages + Frage-Counts pro Page)
        # ------------------------------------------------------------
        pages_qs = (
            WavePage.objects
            .with_completeness()
            .filter(wave_links__wave=active_wave)
            .order_by("wave_links__sort_order", "pagename")
            .distinct()
        )

        pages_qs = pages_qs.annotate(
            sort_order=Min("wave_links__sort_order")
        )

        wave_question_ids = (
            WaveQuestion.objects
            .filter(wave=active_wave)
            .values_list("question_id", flat=True)
        )

        counts_qs = (
            WavePageQuestion.objects
            .filter(wave_page__in=pages_qs)
            .filter(question_id__in=wave_question_ids)
            .values("wave_page_id")
            .annotate(cnt=Count("id"))
        )
        page_question_counts = {row["wave_page_id"]: row["cnt"] for row in counts_qs}

        ctx["pages"] = pages_qs
        ctx["page_question_counts"] = page_question_counts
        ctx["delete_blocked_global"] = bool(active_wave and active_wave.is_locked)


        return ctx
    
    # POST request for creating a new WavePage
    def post(self, request, *args, **kwargs):

        if request.POST.get("create_page") != "1":
            return redirect(request.path)
        
        if not request.user.has_perm("accounts.can_edit_slc"):
            raise PermissionDenied

        survey_name = self.kwargs["survey_name"]
        survey = Survey.objects.filter(name=survey_name).first()
        if not survey:
            raise Http404("Survey not found")

        form = WavePageCreateForm(request.POST, survey=survey)

        if form.is_valid():
            page = WavePage.objects.create(
                pagename=form.cleaned_data["pagename"]
            )
            
            selected_waves = form.cleaned_data["waves"]
            
            for w in selected_waves:
                next_pos = (
                    WavePageWave.objects
                    .filter(wave=w)
                    .aggregate(m=Max("sort_order"))["m"] or 0
                ) + 1
                WavePageWave.objects.create(wave=w, page=page, sort_order=next_pos)

            # Redirect auf Page-Detail; wave-Parameter auf erste ausgewählte Wave setzen
            first_wave = form.cleaned_data["waves"].first()
            url = reverse("pages:page-edit", args=[page.id])
            if first_wave:
                url = f"{url}?wave={first_wave.id}"

            messages.success(request, f"Seite „{page.pagename}“ wurde angelegt.")
            return redirect(url)

        # Fehler: Seite erneut anzeigen + Modal automatisch öffnen
        ctx = self.get_context_data(**kwargs)
        ctx["page_create_form"] = form
        ctx["page_modal_open"] = True
        return self.render_to_response(ctx)
    

class SurveyCreateView(EditorRequiredMixin, CreateView):
    model = Survey
    form_class = SurveyCreateForm
    template_name = "waves/survey_form.html"
    success_url = reverse_lazy("waves:survey_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if "wave_formset" not in ctx:
            ctx["wave_formset"] = WaveFormSet()

        return ctx
    
    # wenn das Hauptformular fehlerhaft ist, wird das Formset neu gerendert
    def form_invalid(self, form):
        wave_formset = WaveFormSet(self.request.POST)
        return self.render_to_response(
            self.get_context_data(form=form, wave_formset=wave_formset)
        )

    @transaction.atomic
    def form_valid(self, form):
        ctx = self.get_context_data()
        wave_formset = WaveFormSet(self.request.POST)

        if not wave_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    wave_formset=wave_formset,
                )
            )

        self.object = form.save()
        wave_formset.instance = self.object
        wave_formset.save()

        return super().form_valid(form)
    

class SurveyUpdateView(EditorRequiredMixin, UpdateView):
    model = Survey
    form_class = SurveyCreateForm
    template_name = "waves/survey_form.html"
    success_url = reverse_lazy("waves:survey_list")

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # gesamte Befragung löschen (inkl. Gruppen, sofern alle löschbar)
        if request.POST.get("delete_survey") == "1":
            survey = self.object

            waves = list(survey.waves.all())

            # Prüfen: alle Waves müssen löschbar sein
            blocked = [w for w in waves if not w.can_be_deleted]

            if blocked:
                messages.error(
                    request,
                    "Diese Befragung kann nicht gelöscht werden, weil mindestens eine Gruppe gesperrt ist "
                    "oder bereits Seiten/Fragen enthält. "
                )
                return redirect(request.path)

            # Wenn alles ok: erst Gruppen löschen, dann Survey löschen
            Wave.objects.filter(survey=survey).delete()
            survey.delete()

            messages.success(request, "Befragung wurde gelöscht.")
            return redirect(self.success_url)
        
        #Default: normales Update
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        survey = self.object

        if "wave_formset" not in ctx:
            if self.request.method == "POST":
                ctx["wave_formset"] = WaveFormSet(self.request.POST, instance=survey)
            else:
                ctx["wave_formset"] = WaveFormSet(instance=survey)

        ctx["is_edit_mode"] = True
        return ctx
    
    # wenn das Hauptformular fehlerhaft ist, wird das Formset neu gerendert
    def form_invalid(self, form):
        survey = self.object
        wave_formset = WaveFormSet(self.request.POST, instance=survey)

        return self.render_to_response(
            self.get_context_data(
                form=form,
                wave_formset=wave_formset,
            )
        )

    @transaction.atomic
    def form_valid(self, form):
        survey = form.save(commit=False)

        wave_formset = WaveFormSet(self.request.POST, instance=survey)

        if not wave_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, wave_formset=wave_formset)
            )

        self.object = survey
        self.object.save()

        wave_formset.save()

        return super().form_valid(form)
    

