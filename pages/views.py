# pages/views.py
from django.views.generic import DetailView, UpdateView
from django.urls import reverse
from django.contrib import messages

from accounts.mixins import EditorRequiredMixin

from django.db import transaction
from django.db.models import Prefetch
from waves.models import WaveQuestion, Wave

from .forms import WavePageForm, PageQuestionLinkFormSet
from .models import WavePage, WavePageQuestion    


# View zum Anzeigen einer Fragebogenseite
class WavePageDetailView(DetailView):
    model = WavePage
    template_name = "pages/detail.html"
    context_object_name = "page"

    def get_queryset(self):

        qs = (
            WavePage.objects
            .prefetch_related(
                "waves", 
                Prefetch(
                    "page_questions",
                    queryset=WavePageQuestion.objects.select_related("question"),
                ),
                "screenshots", 
            )
        )
        return qs


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object

        waves_qs = page.waves.all().order_by("cycle", "instrument", "id")

        # active wave aus ?wave=
        active_wave = None
        wave_id = self.request.GET.get("wave")
        if wave_id:
            try:
                active_wave = waves_qs.filter(id=int(wave_id)).first()
            except ValueError:
                active_wave = None

        if active_wave is None:
            active_wave = waves_qs.first()

        # Fragen auf der Seite (alle)
        page_questions_qs = (
            page.page_questions
            .select_related("question")
            .all()
        )

        # WICHTIG: Falls keine wave verknüpft ist, nicht filtern
        if active_wave:
            wave_question_ids = WaveQuestion.objects.filter(
                wave=active_wave
            ).values_list("question_id", flat=True)

            page_questions_qs = page_questions_qs.filter(
                question_id__in=wave_question_ids
            )

        ctx["waves"] = waves_qs
        ctx["active_wave"] = active_wave
        ctx["page_questions_filtered"] = page_questions_qs
        ctx["survey"] = active_wave.survey if active_wave and active_wave.survey_id else None

        return ctx
    

# View zum Bearbeiten einer bestehenden Fragebogenseite
class WavePageUpdateView(EditorRequiredMixin, UpdateView):
    model = WavePage
    form_class = WavePageForm
    template_name = "pages/page_form.html"
    context_object_name = "page"

    def get_success_url(self):
        url = reverse("pages:page-detail", args=[self.object.pk])
        wave_id = self.request.GET.get("wave")
        if wave_id:
            url = f"{url}?wave={wave_id}"
        return url

    def _get_allowed_waves_from_post_or_instance(self, form=None):
        """
        Ermittelt die Waves, die im Fragen-Formset auswählbar sein sollen.
        Priorität:
        1) Waves aus dem bereits gebundenen Hauptformular (sauber)
        2) Waves aus POST (Fallback)
        3) Waves aus der DB-Instance (Fallback)
        """
        # 1) Wenn das Hauptformular schon gebunden ist, nimm cleaned_data (falls verfügbar)
        if form is not None and hasattr(form, "cleaned_data"):
            waves = form.cleaned_data.get("waves")
            if waves is not None:
                return waves

        # 2) Fallback: raw POST-Werte (IDs)
        post_ids = self.request.POST.getlist("waves")
        if post_ids:
            return Wave.objects.filter(id__in=post_ids)

        # 3) Fallback: Instance
        return self.object.waves.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        allowed_waves = self.object.waves.all().order_by("cycle", "instrument", "id")

        if self.request.method == "POST":
            bound_form = ctx.get("form")
            allowed_waves = self._get_allowed_waves_from_post_or_instance(bound_form).order_by(
                "cycle", "instrument", "id"
            )

            ctx["question_formset"] = PageQuestionLinkFormSet(
                self.request.POST,
                prefix="qfs",
                form_kwargs={"allowed_waves": allowed_waves},
            )
        else:
            wpq_qs = (
                WavePageQuestion.objects
                .filter(wave_page=self.object)
                .select_related("question")
                .order_by("id")
            )

            questions = [x.question for x in wpq_qs]
            q_ids = [q.id for q in questions]

            wave_map = {}
            if q_ids and allowed_waves.exists():
                wq_qs = (
                    WaveQuestion.objects
                    .filter(question_id__in=q_ids, wave__in=allowed_waves)
                    .select_related("wave")
                )
                for wq in wq_qs:
                    wave_map.setdefault(wq.question_id, []).append(wq.wave)

            initial = []
            for q in questions:
                initial.append({
                    "question": q,
                    "waves": wave_map.get(q.id, []),
                })

            ctx["question_formset"] = PageQuestionLinkFormSet(
                prefix="qfs",
                initial=initial,
                form_kwargs={"allowed_waves": allowed_waves},
            )

        return ctx

    def form_valid(self, form):
        allowed_waves = self._get_allowed_waves_from_post_or_instance(form).order_by(
            "cycle", "instrument", "id"
        )

        question_formset = PageQuestionLinkFormSet(
            self.request.POST,
            prefix="qfs",
            form_kwargs={"allowed_waves": allowed_waves},
        )

        if not question_formset.is_valid():
            ctx = self.get_context_data(form=form)
            ctx["question_formset"] = question_formset
            return self.render_to_response(ctx)

        with transaction.atomic():
            # 1) Page speichern (inkl. waves M2M)
            self.object = form.save()
            page = self.object

            # 2) Zielzustand aus dem Formset lesen
            desired_question_ids = set()
            selected_waves_by_qid = {} 

            for f in question_formset.forms:
                if question_formset.can_delete and question_formset._should_delete_form(f):
                    continue

                cd = getattr(f, "cleaned_data", None) or {}
                q = cd.get("question")
                ws = cd.get("waves")

                # Leere Extra-Zeilen ignorieren
                if not q and (not ws or len(ws) == 0):
                    continue

                qid = q.id
                desired_question_ids.add(qid)
                selected_waves_by_qid[qid] = set(w.id for w in ws)

            # 3) WavePageQuestion sync (Page ↔ Question)
            existing = (
                WavePageQuestion.objects
                .filter(wave_page=page)
                .values_list("question_id", flat=True)
            )
            existing_ids = set(existing)

            to_delete = existing_ids - desired_question_ids
            to_add = desired_question_ids - existing_ids

            if to_delete:
                WavePageQuestion.objects.filter(wave_page=page, question_id__in=to_delete).delete()

            if to_add:
                WavePageQuestion.objects.bulk_create([
                    WavePageQuestion(wave_page=page, question_id=qid) for qid in to_add
                ])

            # 4) WaveQuestion sicherstellen (Wave ↔ Question)
            #    (kein automatisches Löschen in Schritt 1)
            #    Defensive: nur Waves zulassen, die aktuell zur Page gehören
            allowed_wave_ids = set(page.waves.values_list("id", flat=True))

            for qid, wave_ids in selected_waves_by_qid.items():
                wave_ids = set(wave_ids) & allowed_wave_ids
                for wid in wave_ids:
                    WaveQuestion.objects.get_or_create(wave_id=wid, question_id=qid)

        messages.success(self.request, "Seite gespeichert.")
        return super().form_valid(form)