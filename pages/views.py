# pages/views.py
from collections import defaultdict
import re
from urllib import request
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Variable
from django.template import Variable
from django.views import View
from django.views.generic import DetailView, UpdateView, TemplateView
from django.urls import reverse
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages

from accounts.mixins import EditorRequiredMixin

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, OuterRef, Exists
from pages.utils import cleanup_wavequestions_for_removed_questions, get_new_orphan_question_ids
from waves.models import Survey, WaveQuestion, Wave
from .models import WavePage, WavePageQuestion
from questions.models import Question, QuestionVariableWave
from variables.models import Variable

from .forms import WavePageBaseForm, WavePageContentForm, PageQuestionLinkFormSet

from .services.pv_builder import PVContext, build_pv


# Session-Key für verwaiste Fragen-Review
ORPHAN_REVIEW_SESSION_KEY = "orphan_review"

# Helper: Aktive Wave aus QuerySet bestimmen
def _get_active_wave_from_qs(request, waves_qs, *, default_first=True):
    """
    Bestimmt die aktive Wave über ?wave= aus einem QuerySet von Waves.
    - Wenn ?wave= ungültig oder nicht im QS: fallback auf first() (wenn default_first=True)
    - Gibt None zurück, wenn QS leer ist und default_first=False
    """
    wave_id = request.GET.get("wave")
    active_wave = None

    if wave_id:
        try:
            active_wave = waves_qs.filter(id=int(wave_id)).first()
        except (TypeError, ValueError):
            active_wave = None

    if active_wave is None and default_first:
        active_wave = waves_qs.first()

    return active_wave


# Helper: Frage-IDs aus POST-Daten extrahieren
def _extract_posted_question_ids(post_data, prefix="qfs"):
    ids = set()
    # Felder heißen z.B. qfs-0-question, qfs-1-question, ...
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)-question$")
    for key, val in post_data.items():
        if pattern.match(key) and val:
            try:
                ids.add(int(val))
            except ValueError:
                pass
    return ids


# Helper: Formset für GET (Initial) oder für POST (bound)
def _build_question_formset_for_page(*, page, allowed_waves, method, post_data=None):
    """
    Baut das PageQuestionLinkFormSet entweder:
    - GET: mit `initial` aus DB (WavePageQuestion + WaveQuestion)
    - POST: gebunden mit post_data (Formset validiert dann gegen allowed_waves)
    """
    allowed_waves = allowed_waves.order_by("cycle", "instrument", "id")

    # Basis: Fragen, die bereits auf der Seite sind
    wpq_qs = (
        WavePageQuestion.objects
        .filter(wave_page=page)
        .select_related("question")
        .order_by("id")
    )
    page_questions = [x.question for x in wpq_qs]
    page_question_ids = {q.id for q in page_questions}


    # POST: gebundenes Formset
    if method == "POST":
        posted_ids = _extract_posted_question_ids(post_data, prefix="qfs")
        allowed_ids = page_question_ids | posted_ids

        allowed_questions = Question.objects.filter(id__in=allowed_ids)

        return PageQuestionLinkFormSet(
            post_data,
            prefix="qfs",
            form_kwargs={
                "allowed_waves": allowed_waves,
                "allowed_questions": allowed_questions,
            },
        )

    # GET: initial auslesen
    questions = page_questions
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

    allowed_questions = Question.objects.filter(id__in=page_question_ids)

    return PageQuestionLinkFormSet(
        prefix="qfs",
        initial=initial,
        form_kwargs={
            "allowed_waves": allowed_waves,
            "allowed_questions": allowed_questions,
        },
    )


# View zum Anzeigen einer Fragebogenseite
class WavePageDetailView(DetailView):
    model = WavePage
    template_name = "pages/detail.html"
    context_object_name = "page"
    
    @property
    def can_edit(self):
        return self.request.user.has_perm("accounts.can_edit_slc")

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

        # Vollständigkeitsinfo ran hängen (nur für Editoren erforderlich)
        if self.can_edit:
            qs = qs.with_completeness()

        return qs
    



    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object
        
        waves_qs = page.waves.all().order_by("cycle", "instrument", "id")

        # active wave aus ?wave=
        active_wave = _get_active_wave_from_qs(self.request, waves_qs, default_first=True)

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
        
        # Gib die Info mit, ob die Seite mit einer gesperrten Befragung verknüpft ist
        page_is_locked = waves_qs.filter(is_locked=True).exists()    

        question_ids = list(
            page_questions_qs.values_list("question_id", flat=True).distinct()
        )

        if self.can_edit and question_ids:
            questions_by_id = {
                q.id: q
                for q in (
                    Question.objects
                    .filter(id__in=question_ids)
                    .with_completeness()
                    .only("id")
                )
            }
            
            for pq in page_questions_qs:
                q = questions_by_id.get(pq.question_id)
                pq.question_is_incomplete = bool(getattr(q, "is_incomplete", False))
        else:
            for pq in page_questions_qs:
                pq.question_is_incomplete = False


        ctx["waves"] = waves_qs
        ctx["active_wave"] = active_wave
        ctx["page_questions_filtered"] = page_questions_qs
        ctx["survey"] = active_wave.survey if active_wave and active_wave.survey_id else None 
        ctx["page_is_locked"] = page_is_locked
        ctx["edit_question_allowed_waves"] = waves_qs.filter(is_locked=False)

        ctx["has_page_header"] = any([
            page.page_heading,
            page.introduction,
        ])

        ctx["has_page_other_fields"] = any([
            page.visibility_conditions,
            page.answer_validations,
            page.correction_notes,
            page.forcing_variables,
            page.helper_variables,
            page.control_variables,
            page.formatting,
            page.page_programming_notes,
        ])

        return ctx
    


# View zur Antzeige der Bearbeitungsoberfläche einer Fragebogenseite
# Edit-Renderer: GET /pages/<pk>/edit/
# - rendert 2 Blöcke (Basis + Content/Formset)
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
        active_wave = _get_active_wave_from_qs(self.request, allowed_waves, default_first=True)

        ctx["active_wave"] = active_wave
        ctx["survey"] = active_wave.survey if active_wave else None

        return ctx


# View zum Speichern der Basisinformationen der Seite (Name und Befragungsgruppen)
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
        active_wave = _get_active_wave_from_qs(self.request, allowed_waves, default_first=True)
        ctx["active_wave"] = active_wave
        ctx["survey"] = active_wave.survey if active_wave else None

        return render(self.request, self.template_name, ctx)



# View zum Speichern der Seiteninhalte und Fragen
# Content + Fragen speichern: POST /pages/<pk>/edit/content/
# - speichert nur Zusatzfelder
# - validiert/speichert Formset
# - synced WavePageQuestion & WaveQuestion
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
            active_wave = _get_active_wave_from_qs(self.request, allowed_waves, default_first=True)
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

            removed_qids = list(to_delete)

            if to_delete:
                WavePageQuestion.objects.filter(wave_page=page, question_id__in=to_delete).delete()

                cleanup_wavequestions_for_removed_questions(
                    page=page,
                    removed_question_ids=removed_qids,
                    wave_ids=list(page.waves.values_list("id", flat=True)),
                )

                orphan_qids = get_new_orphan_question_ids(removed_qids)

                if orphan_qids:
                    return_url = reverse("pages:page-edit", kwargs={"pk": page.pk})
                    wave = self.request.GET.get("wave")
                    if wave:
                        return_url = f"{return_url}?wave={wave}"

                    self.request.session[ORPHAN_REVIEW_SESSION_KEY] = {
                        "question_ids": orphan_qids,
                        "return_url": return_url,
                    }
                    return redirect(reverse("pages:orphan_questions_review"))

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

        # active wave aus ?wave=
        active_wave = _get_active_wave_from_qs(self.request, allowed_waves, default_first=True)
        ctx["active_wave"] = active_wave
        ctx["survey"] = active_wave.survey if active_wave else None

        return render(self.request, self.template_name, ctx)
    

# View zum Löschen einer Fragebogenseite
class WavePageDeleteView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        page = get_object_or_404(WavePage, pk=pk)

        # Schritt 1: Sperrlogik
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

        # Schritt 2: Rückweg bestimmen
        # Redirect-Ziel vorab bestimmen (nach delete ist M2M weg)
        wave_id = request.GET.get("wave")
        active_wave = page.waves.filter(pk=wave_id).select_related("survey").first() if wave_id else None
        if active_wave is None:
            active_wave = page.waves.select_related("survey").first()

        # return_url vorab festlegen (für Orphan-Review)
        if active_wave and active_wave.survey:
            return_url = reverse("waves:survey_detail", kwargs={"survey_name": active_wave.survey.name})
            return_url = f"{return_url}?wave={active_wave.id}"
        else:
            return_url = reverse("waves:survey_list")

        # Schritt 3: WaveQuestion-Cleanup & Seite löschen
        # Fragen, die auf der Seite waren, werden aus der Befragung entfernt, sofern sie auf keiner anderen Seite in der Befragung mehr vorkommen.
        with transaction.atomic():
            wave_ids = list(page.waves.values_list("id", flat=True))
            question_ids = list(page.page_questions.values_list("question_id", flat=True).distinct())

            # WaveQuestion-Cleanup
            cleanup_wavequestions_for_removed_questions(
                page=page,
                removed_question_ids=question_ids,
                wave_ids=wave_ids,
            )

            # Seite löschen
            page_name = page.pagename
            page.delete()

            # Schritt 4: Variablen bereinigen
            WaveVarThrough = Variable._meta.get_field("waves").remote_field.through

            for wid in wave_ids:
                # Fragen, die in dieser Wave nach dem Löschen noch irgendwo auf Pages vorkommen
                remaining_qids_in_wave = set(
                    WavePageQuestion.objects.filter(
                        wave_page__waves__id=wid
                    ).values_list("question_id", flat=True).distinct()
                )

                # Fragen der gelöschten Seite, die jetzt in dieser Befragung nirgends mehr vorkommen
                removed_qids_from_wave = set(question_ids) - remaining_qids_in_wave
                if not removed_qids_from_wave:
                    continue

                # Triad-Zeilen, die genau zu diesen "aus der Befragung gefallenen" Questions gehören
                triad_qs = QuestionVariableWave.objects.filter(
                    wave_id=wid,
                    question_id__in=removed_qids_from_wave,
                )

                # Variablen-Kandidaten: die Variablen, die an den gelöschten Triad-Zeilen hingen
                affected_var_ids = set(
                    triad_qs.values_list("variable_id", flat=True).distinct()
                )

                # a) Triad löschen (Q aus Wave => Triad für diese Q+Wave muss weg)
                triad_qs.delete()

                if not affected_var_ids:
                    continue

                # b) Welche dieser Variablen sind in der Befragung noch über verbleibende Fragen verknüpft?
                still_used_var_ids = set(
                    QuestionVariableWave.objects.filter(
                        wave_id=wid,
                        question_id__in=remaining_qids_in_wave,
                        variable_id__in=affected_var_ids,
                    ).values_list("variable_id", flat=True).distinct()
                )

                to_remove_var_ids = affected_var_ids - still_used_var_ids
                if not to_remove_var_ids:
                    continue

                # Failsafe: technische Variablen nicht anfassen
                non_technical_to_remove = Variable.objects.filter(
                    id__in=to_remove_var_ids,
                    is_technical=False,
                ).values_list("id", flat=True)

                # c) WaveVar bereinigen
                WaveVarThrough.objects.filter(
                    wave_id=wid,
                    variable_id__in=non_technical_to_remove,
                ).delete()


        #  Schritt 5: nach der Transaktion: Frage-Orphans bestimmen (b)
        orphan_qids = get_new_orphan_question_ids(question_ids)
        if orphan_qids:
            request.session[ORPHAN_REVIEW_SESSION_KEY] = {
                "question_ids": orphan_qids,
                "return_url": return_url,   
            }
            return redirect(reverse("pages:orphan_questions_review"))

        # Erfolgsmeldung
        messages.success(
            request,
            f"Seite '{page_name}' wurde gelöscht."
        )

        # Redirect: zurück zur Survey-Detailansicht, falls möglich
        return redirect(return_url)
    


# View zur Überprüfung verwaister Fragen
class OrphanQuestionsReviewView(EditorRequiredMixin, View):
    template_name = "pages/orphan_questions_review.html"
    http_method_names = ["get", "post"]

    def get(self, request, *args, **kwargs):
        payload = request.session.get(ORPHAN_REVIEW_SESSION_KEY)
        if not payload:
            messages.info(request, "Keine verwaisten Fragen zur Bereinigung vorhanden.")
            return redirect("waves:survey_list")

        qids = payload.get("question_ids", [])
        return_url = payload.get("return_url", "")

        questions = (
            Question.objects
            .filter(id__in=qids)
            .only("id", "questiontext")
            .order_by("id")
        )

        return render(request, self.template_name, {
            "questions": questions,
            "return_url": return_url,
        })

    def post(self, request, *args, **kwargs):
        payload = request.session.get(ORPHAN_REVIEW_SESSION_KEY)
        if not payload:
            messages.info(request, "Keine verwaisten Fragen zur Bereinigung vorhanden.")
            return redirect("waves:survey_list")

        action = request.POST.get("action")  # "delete" | "keep"
        qids = payload.get("question_ids", [])
        return_url = payload.get("return_url", "")

        # Return-URL absichern
        if return_url and not url_has_allowed_host_and_scheme(return_url, allowed_hosts={request.get_host()}):
            return_url = ""

        if action == "delete":
            num_deleted, _ = Question.objects.filter(id__in=qids).delete()
            messages.success(request, f"{num_deleted} verwaiste Frage(n) wurden gelöscht.")
        else:
            messages.info(request, f"{len(qids)} verwaiste Frage(n) wurden behalten.")

        request.session.pop(ORPHAN_REVIEW_SESSION_KEY, None)
        return redirect(return_url or "waves:survey_list")


# View zum Anzeigen der PV einer Seite (für Zofar)
class WavePagePVView(EditorRequiredMixin, DetailView):
    model = WavePage
    template_name = "pages/pv.html"
    context_object_name = "page"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object

        wave_id = self.request.GET.get("wave")
        active_wave = get_object_or_404(Wave, pk=wave_id) if wave_id else None

        # Fragen der Seite
        links = page.page_questions.select_related("question").all()
        questions = [l.question for l in links]
        q_ids = [q.id for q in questions]

        # Variablen der Fragen
        vars_by_qid = {q.id: [] for q in questions}

        if q_ids:
            qvw = (QuestionVariableWave.objects.filter(question_id__in=q_ids))
            if active_wave:
                qvw = qvw.filter(wave=active_wave)
         
        rows = (
            qvw.values_list("question_id", "variable__varname")
            .distinct()
            .order_by("question_id", "variable__varname")
        )

        tmp = defaultdict(list)
        for qid, varname in rows:
            tmp[qid].append(varname)

        vars_by_qid = dict(tmp)

        pv_text = build_pv(PVContext(
            page=page,
            questions=questions,
            vars_by_qid=vars_by_qid,
            active_wave=active_wave,
        ))

        ctx["active_wave"] = active_wave
        ctx["pv_text"] = pv_text
        return ctx


# API-View: Liste der Surveys für Modal zum Duplizieren von Seiten
class SurveyListApiView(EditorRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        unlocked_waves = Wave.objects.filter(
            survey_id=OuterRef("pk"),
            is_locked=False,
        )

        surveys = (
            Survey.objects
            .annotate(has_unlocked_waves=Exists(unlocked_waves))
            .filter(has_unlocked_waves=True)
            .order_by("-year", "name")
        )

        data = [{"id": s.id, "name": s.name, "year": s.year} for s in surveys]
        return JsonResponse({"surveys": data})


# API-View: Befragungsgruppen zu einem Survey für Modal zum Duplizieren von Seiten
class WavesBySurveyApiView(EditorRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, survey_id, *args, **kwargs):
        waves = (
            Wave.objects
            .filter(survey_id=survey_id)
            .order_by("cycle", "instrument", "id")
        )
        data = [
            {
                "id": w.id,
                "label": f"{w.cycle} – {w.instrument}",
                "is_locked": bool(w.is_locked),
            }
            for w in waves
        ]
        return JsonResponse({"waves": data})


# API-View: Live-Prüfung, ob ein Seitenname in einem Survey schon existiert
class CheckPageNameApiView(EditorRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        survey_id = request.GET.get("survey_id")
        pagename = (request.GET.get("pagename") or "").strip()

        if not survey_id or not pagename:
            return JsonResponse({"ok": False, "reason": "Fehlende Parameter."}, status=400)

        # Name darf im Ziel-Survey nicht schon existieren
        # (konkret: existiert eine Seite mit diesem Namen, die an irgendeiner Gruppe dieses Surveys hängt?)
        exists = (
            WavePage.objects
            .filter(pagename=pagename, waves__survey_id=survey_id)
            .distinct()
            .exists()
        )
        return JsonResponse({"ok": not exists})


# View zum Duplizieren einer Seite in andere Befragungen
class WavePageCopyView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        source_page = get_object_or_404(WavePage, pk=pk)


        # --- Nutzereingaben lesen
        target_survey_id = request.POST.get("target_survey_id")
        target_wave_ids = request.POST.getlist("target_wave_ids")
        new_pagename = (request.POST.get("new_pagename") or "").strip()

        include_questions = request.POST.get("include_questions") == "1"
        include_variables = request.POST.get("include_variables") == "1"

        if include_variables and not include_questions:
            include_variables = False


        # --- Validierung
        def err(msg, status=400):
            return JsonResponse({"ok": False, "error": msg}, status=status)
        
        if not target_survey_id:
            return err("Bitte eine Ziel-Befragung auswählen.")
        if not target_wave_ids:
            return err("Bitte mindestens eine Gruppe auswählen.")
        if not new_pagename:
            return err("Bitte einen neuen Seitennamen angeben.")

        # target-Befragungsgruppen sauber bestimmen (Gruppe muss zum ausgewählten Survey gehören)
        # (IDs normalisieren, damit count/vergleich stabil bleibt)
        try:
            target_wave_ids_int = sorted({int(x) for x in target_wave_ids})
        except ValueError:
            return err("Ungültige Gruppenauswahl.")

        target_waves_qs = Wave.objects.filter(id__in=target_wave_ids_int, survey_id=target_survey_id)
        target_waves = list(target_waves_qs.order_by("cycle", "instrument", "id"))

        if len(target_waves) != len(target_wave_ids_int):
            return err("Ungültige Gruppen (gehören nicht zur gewählten Befragung).")

        if any(w.is_locked for w in target_waves):
            return err("Mindestens eine ausgewählte Gruppe ist gesperrt. Kopieren nicht möglich.", status=403)

        name_exists = (
            WavePage.objects
            .filter(pagename=new_pagename, waves__survey_id=target_survey_id)
            .distinct()
            .exists()
        )
        if name_exists:
            return err("Dieser Seitenname existiert in der Ziel-Befragung bereits.")
        


        # --- 1) Seite duplizieren (Inhalte kopieren)
        new_page = WavePage.objects.create(
            pagename=new_pagename,
            page_heading=source_page.page_heading,
            introduction=source_page.introduction,
            transition_control=source_page.transition_control,
            visibility_conditions=source_page.visibility_conditions,
            answer_validations=source_page.answer_validations,
            correction_notes=source_page.correction_notes,
            forcing_variables=source_page.forcing_variables,
            helper_variables=source_page.helper_variables,
            control_variables=source_page.control_variables,
            formatting=source_page.formatting,
            transitions=source_page.transitions,
            page_programming_notes=source_page.page_programming_notes,
        )

        try:
            new_page.waves.set(target_waves)
        except IntegrityError:
            return err(
            "Kopieren nicht möglich: Ziel verletzt Datenbank-Regeln "
            "(Seitenname im Survey bereits vorhanden oder Survey-Zuordnung nicht eindeutig)."
            )

        # Bestimme alle Fragen auf der Quell-Seite
        qids: list[int] = []
        if include_questions or include_variables:
            qids = list(
                WavePageQuestion.objects.filter(wave_page=source_page)
                .values_list("question_id", flat=True)
            )

        # aktuell: ohne Fragen auch keine Vars
        # --> evtl. später anpassen, wenn es technische Vars auf Seiten geben sollte, die unabhängig von Fragen sind
        if not qids:
            include_variables = False



        # --- 2) Fragen übernehmen
        if include_questions:
            # Links Seite->Fragen kopieren
            WavePageQuestion.objects.bulk_create(
                [WavePageQuestion(wave_page=new_page, question_id=qid) for qid in qids],
                ignore_conflicts=True,
            )

            # Links Frage->Gruppe kopieren
            WaveQuestion.objects.bulk_create(
                [WaveQuestion(wave_id=w.id, question_id=qid) for w in target_waves for qid in qids],
                ignore_conflicts=True,
            )


        # --- 3) Variablen übernehmen
        # Quell-Survey bestimmen. Es werden nur Variablen kopiert, die im Quell-Survey an den Seitenfragen hängen.
        if include_variables:

            source_survey_ids = list(
                source_page.waves.values_list("survey_id", flat=True).distinct()
            )
        
            if not source_survey_ids:
                return err("Quelle konnte nicht bestimmt werden (Seite hat keine Waves).")
            if len(source_survey_ids) > 1:
                return err("Quelle ist nicht eindeutig (Seite hängt an mehreren Befragungen).")
            source_survey_id = source_survey_ids[0]

            # Alle Gruppen des Quell-Surveys bestimmen
            source_wave_ids = list(
                Wave.objects.filter(survey_id=source_survey_id).values_list("id", flat=True)
            )

            # Alle (question, variable)-Paare, die irgendwo im Quell-Survey an den Seitenfragen hängen
            qv_pairs = list(
                QuestionVariableWave.objects.filter(
                    question_id__in=qids,
                    wave_id__in=source_wave_ids
                )
                .values_list("question_id", "variable_id")
                .distinct()
            )

            if qv_pairs:
                target_wave_ids_for_pairs = [w.id for w in target_waves]

                # 3a) Triaden für alle Ziel-Waves setzen
                qvw_rows = [
                    QuestionVariableWave(question_id=qid, variable_id=vid, wave_id=wid)
                    for (qid, vid) in qv_pairs
                    for wid in target_wave_ids_for_pairs
                ]
                QuestionVariableWave.objects.bulk_create(qvw_rows, ignore_conflicts=True)

                # 3b) Direktes Variable↔Wave M2M setzen
                var_ids = sorted({vid for (_, vid) in qv_pairs})

                through = Variable.waves.through
                m2m_rows = [
                    through(variable_id=vid, wave_id=wid)
                    for vid in var_ids
                    for wid in target_wave_ids_for_pairs
                ]
                through.objects.bulk_create(m2m_rows, ignore_conflicts=True)

        
        return JsonResponse({"ok": True, "new_page_id": new_page.pk})
