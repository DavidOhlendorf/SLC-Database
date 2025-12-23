# pages/views.py
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, UpdateView, TemplateView
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.contrib import messages

from accounts.mixins import EditorRequiredMixin

from django.db import transaction
from django.db.models import Prefetch, OuterRef, Exists
from waves.models import WaveQuestion, Wave
from .models import WavePage, WavePageQuestion

from .forms import WavePageBaseForm, WavePageContentForm, PageQuestionLinkFormSet



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

        # Falls keine wave verknüpft ist, nicht filtern
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
    

# Helper: Formset für GET (Initial) oder für POST (bound)
def _build_question_formset_for_page(*, page, allowed_waves, method, post_data=None):
    """
    Baut das PageQuestionLinkFormSet entweder:
    - GET: mit `initial` aus DB (WavePageQuestion + WaveQuestion)
    - POST: gebunden mit post_data (Formset validiert dann gegen allowed_waves)
    """
    allowed_waves = allowed_waves.order_by("cycle", "instrument", "id")

    # POST: gebundenes Formset
    if method == "POST":
        return PageQuestionLinkFormSet(
            post_data,
            prefix="qfs",
            form_kwargs={"allowed_waves": allowed_waves},
        )

    # GET: initial auslesen
    wpq_qs = (
        WavePageQuestion.objects
        .filter(wave_page=page)
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

    initial = [{"question": q, "waves": wave_map.get(q.id, [])} for q in questions]

    return PageQuestionLinkFormSet(
        prefix="qfs",
        initial=initial,
        form_kwargs={"allowed_waves": allowed_waves},
    )


# Edit-Renderer: GET /pages/<pk>/edit/
# - rendert beide Blöcke (Basis + Content/Formset)
class WavePageUpdateView(EditorRequiredMixin, TemplateView):

    template_name = "pages/page_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        pk = self.kwargs["pk"]
        page = WavePage.objects.get(pk=pk)

        allowed_waves = page.waves.all()

        # Gib die Info mit, ob die Seite mit einer gesperrten Befragung verknüpft ist
        # Deaktiviert aktuell den Löschen-Button im Template, wäre aber auch auf 
        # Bearebeitungslogik anwendbar, wenn das gewünscht wäre.
        ctx["delete_blocked"] = allowed_waves.filter(is_locked=True).exists()

        ctx["page"] = page
        ctx["base_form"] = WavePageBaseForm(instance=page)
        ctx["content_form"] = WavePageContentForm(instance=page)
        ctx["question_formset"] = _build_question_formset_for_page(
            page=page,
            allowed_waves=allowed_waves,
            method="GET",
        )

        # active wave aus ?wave= & survey mitgeben, damit zurück-Links funktionieren
        wave_id = self.request.GET.get("wave")
        if wave_id:
            wave_id = self.request.GET.get("wave")
            active_wave = page.waves.filter(pk=wave_id).first() if wave_id else None
            ctx["active_wave"] = active_wave
            ctx["survey"] = active_wave.survey if active_wave else None

        else:
            ctx["active_wave"] = None
            ctx["survey"] = None

        return ctx


# Basis speichern: POST /pages/<pk>/edit/base/
# - speichert nur pagename + waves
# - danach Redirect zurück auf /edit/
class WavePageBaseUpdateView(EditorRequiredMixin, UpdateView):
    model = WavePage
    form_class = WavePageBaseForm
    template_name = "pages/page_form.html"
    context_object_name = "page"

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Seitendaten (Name & Wellen) gespeichert.")
        url = reverse("pages:page-edit", kwargs={"pk": self.object.pk})
        wave = self.request.GET.get("wave")
        if wave:
            url = f"{url}?wave={wave}"
        return redirect(url)

    def form_invalid(self, form):
        page = self.get_object()
        allowed_waves = page.waves.all()

        ctx = {
            "page": page,
            "base_form": form,
            "content_form": WavePageContentForm(instance=page),
            "question_formset": _build_question_formset_for_page(
                page=page,
                allowed_waves=allowed_waves,
                method="GET",
            ),
        }

        # active wave aus ?wave=
        wave_id = self.request.GET.get("wave")
        active_wave = page.waves.filter(pk=wave_id).first() if wave_id else None
        ctx["active_wave"] = active_wave
        ctx["survey"] = active_wave.survey if active_wave else None

        return render(self.request, self.template_name, ctx)



# Content + Fragen speichern: POST /pages/<pk>/edit/content/
# - speichert nur Zusatzfelder
# - validiert/speichert Formset
# - synced WavePageQuestion & WaveQuestion (wie bisher)
# - Redirect zurück auf /edit/
class WavePageContentUpdateView(EditorRequiredMixin, UpdateView):
    model = WavePage
    form_class = WavePageContentForm
    template_name = "pages/page_form.html"
    context_object_name = "page"

    def form_valid(self, form):
        page = self.get_object()

        allowed_waves = page.waves.all().order_by("cycle", "instrument", "id")

        question_formset = _build_question_formset_for_page(
            page=page,
            allowed_waves=allowed_waves,
            method="POST",
            post_data=self.request.POST,
        )

        if not question_formset.is_valid():
            ctx = {
                "page": page,
                "base_form": WavePageBaseForm(instance=page),
                "content_form": form,
                "question_formset": question_formset,
            }

            # active wave aus ?wave=
            wave_id = self.request.GET.get("wave")
            active_wave = page.waves.filter(pk=wave_id).first() if wave_id else None
            ctx["active_wave"] = active_wave
            ctx["survey"] = active_wave.survey if active_wave else None

            return render(self.request, self.template_name, ctx)

        with transaction.atomic():
            self.object = form.save()
            page = self.object

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
            existing_ids = set(
                WavePageQuestion.objects
                .filter(wave_page=page)
                .values_list("question_id", flat=True)
            )

            to_delete = existing_ids - desired_question_ids
            to_add = desired_question_ids - existing_ids

            if to_delete:
                WavePageQuestion.objects.filter(
                    wave_page=page,
                    question_id__in=to_delete
                ).delete()

            if to_add:
                WavePageQuestion.objects.bulk_create([
                    WavePageQuestion(wave_page=page, question_id=qid)
                    for qid in to_add
                ])

            # 4) WaveQuestion sicherstellen (Wave ↔ Question)
            #    Defensive: nur Waves zulassen, die aktuell zur Page gehören
            allowed_wave_ids = set(page.waves.values_list("id", flat=True))

            for qid, wave_ids in selected_waves_by_qid.items():
                wave_ids = set(wave_ids) & allowed_wave_ids
                for wid in wave_ids:
                    WaveQuestion.objects.get_or_create(wave_id=wid, question_id=qid)

        messages.success(self.request, "Seiteninhalte gespeichert.")
        url = reverse("pages:page-edit", kwargs={"pk": page.pk})
        wave = self.request.GET.get("wave")
        if wave:
            url = f"{url}?wave={wave}"
        return redirect(url)

    def form_invalid(self, form):
        page = self.get_object()
        allowed_waves = page.waves.all()

        ctx = {
            "page": page,
            "base_form": WavePageBaseForm(instance=page),
            "content_form": form,
            "question_formset": _build_question_formset_for_page(
                page=page,
                allowed_waves=allowed_waves,
                method="GET",
            ),
        }

        wave_id = self.request.GET.get("wave")
        active_wave = page.waves.filter(pk=wave_id).first() if wave_id else None
        ctx["active_wave"] = active_wave
        ctx["survey"] = active_wave.survey if active_wave else None

        return render(self.request, self.template_name, ctx)
    
# view zum Löschen einer Fragebogenseite
class WavePageDeleteView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        page = get_object_or_404(WavePage, pk=pk)

        # Schritt 3: Sperrlogik
        if page.waves.filter(is_locked=True).exists():
            messages.error(
                request,
                "Diese Seite kann nicht gelöscht werden, weil sie mit einer abgeschlossenen Befragung verknüpft ist."
            )
            url = reverse("pages:page-edit", kwargs={"pk": page.pk})
            wave = request.GET.get("wave")
            if wave:
                url = f"{url}?wave={wave}"
            return redirect(url)

        # Redirect-Ziel vorab bestimmen (nach delete ist M2M weg)
        wave_id = request.GET.get("wave")
        active_wave = page.waves.filter(pk=wave_id).select_related("survey").first() if wave_id else None
        if active_wave is None:
            active_wave = page.waves.select_related("survey").first()

        with transaction.atomic():
            wave_ids = list(page.waves.values_list("id", flat=True))
            question_ids = list(page.page_questions.values_list("question_id", flat=True).distinct())

            # 5) WaveQuestion cleanup (future-proof)
            # "keep" = es gibt eine andere Seite (≠ page), die diese question enthält
            #          UND die zu derselben wave gehört.
            other_usage = WavePageQuestion.objects.filter(
                question_id=OuterRef("question_id"),
                wave_page__waves__id=OuterRef("wave_id"),
            ).exclude(wave_page=page)

            wq_qs = WaveQuestion.objects.filter(
                wave_id__in=wave_ids,
                question_id__in=question_ids,
            ).annotate(
                keep=Exists(other_usage)
            )

            # optional: Zählung für Feedback
            delete_wq_count = wq_qs.filter(keep=False).count()

            # löschen nur, wenn nicht mehr gebraucht
            wq_qs.filter(keep=False).delete()

            # 6) Seite löschen (WavePageQuestion & Screenshots gehen via CASCADE mit)
            page_name = page.pagename
            page.delete()

        # Erfolgsmeldung
        messages.success(
            request,
            f"Seite '{page_name}' wurde gelöscht. ({delete_wq_count} WaveQuestion-Verknüpfungen bereinigt)"
        )

        # Redirect: zurück zur Survey-Detailansicht, falls möglich
        if active_wave and active_wave.survey:
            url = reverse("waves:survey_detail", kwargs={"survey_name": active_wave.survey.name})
            url = f"{url}?wave={active_wave.id}"
            return redirect(url)

        return redirect(reverse("waves:survey_list"))