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
from pages.models import WavePageQuestion, WavePage

from .forms import SurveyCreateForm, WaveFormSet
from accounts.mixin import EditorRequiredMixin


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
                    .filter(waves__in=wlist)
                    .distinct()
                    .prefetch_related("waves")
                    .order_by("pagename")
                )

                wave_ids_set = set(w.id for w in wlist)
                page_wave_tags = {}
                for p in pages_qs:
                    page_wave_tags[p.id] = [w for w in p.waves.all() if w.id in wave_ids_set]

                instrument_groups.append({
                    "instrument": instrument,
                    "waves": wlist,
                    "pages": pages_qs,
                    "page_wave_tags": page_wave_tags,
                    "default_wave_id": wlist[0].id,
                })

            ctx["instrument_groups"] = instrument_groups
            return ctx

        # ------------------------------------------------------------
        # WAVE MODE: (Pages + Frage-Counts pro Page)
        # ------------------------------------------------------------
        pages_qs = (
            active_wave.pages
            .all()
            .order_by("pagename")
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

        return ctx
    

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
    

