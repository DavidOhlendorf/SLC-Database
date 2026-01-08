# questions/views.py

from urllib import request
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from urllib.parse import quote
from django.http import Http404, JsonResponse

from django.views import View
from django.views.generic import DetailView, UpdateView

from accounts.mixins import EditorRequiredMixin

from django.db.models import Prefetch, Q
from django.db import transaction

from .models import Question, Keyword
from variables.models import Variable, QuestionVariableWave
from waves.models import Wave, WaveQuestion
from pages.models import WavePage, WavePageQuestion

from .forms import QuestionEditForm, AnswerOptionFormSet, ItemFormSet, AttachWavePageForm, QuestionVariableLinkFormSet

from .utils import create_question_for_page


# ---- Allgemeine Helper-Funktionen ---------------------------------------

# Helper: Baut das QuestionVariableLinkFormSet
def _build_question_variable_formset(*, question, question_waves, method, post_data=None):
    """
    Baut das QuestionVariableLinkFormSet:
    - GET: initial aus Triad (QuestionVariableWave)
    - POST: gebundenes Formset
    """
    question_waves = question_waves.order_by("cycle", "instrument", "id")

    if method == "POST":
        return QuestionVariableLinkFormSet(
            post_data,
            prefix="vfs",
            form_kwargs={"question_waves": question_waves},
        )

    # GET: initial aus Triad
    links = (
        QuestionVariableWave.objects
        .filter(question=question, wave__in=question_waves)
        .select_related("variable", "wave")
        .order_by("variable_id", "wave_id")
    )

    wave_map = {}  # variable_id -> [wave, ...]
    var_ids = []
    for l in links:
        wave_map.setdefault(l.variable_id, []).append(l.wave)

    var_ids = list(wave_map.keys())
    variables = list(
        Variable.objects
        .filter(id__in=var_ids)
        .order_by("varname")
    )

    initial = [{"variable": v, "waves": wave_map.get(v.id, [])} for v in variables]

    return QuestionVariableLinkFormSet(
        prefix="vfs",
        initial=initial,
        form_kwargs={"question_waves": question_waves},
    )


# ---- VIEWS ------------------------------------------------------------


# View für Detailanzeige einer Frage
class QuestionDetail(DetailView):
    model = Question
    template_name = "questions/detail.html"
    context_object_name = "question"

    @property
    def can_edit(self):
        return self.request.user.has_perm("accounts.can_edit_slc")

    def get_queryset(self):
        qs = (
            Question.objects
            .select_related("construct")  
            .prefetch_related(
                Prefetch(
                    "waves",
                    queryset=Wave.objects.order_by("-id"),
                )
            )
        )

        # Vollständigkeitsinfo ran hängen (nur für Editoren erforderlich)
        if self.can_edit:
            qs = qs.with_completeness()

        return qs



    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        question = self.object

        waves = list(question.waves.all().order_by("-id"))
        wave_param = self.request.GET.get("wave")

        active_wave = None
        if waves:
            if wave_param and any(str(w.id) == wave_param for w in waves):
                active_wave = next(w for w in waves if str(w.id) == wave_param)
            else:
                active_wave = waves[0]

        triad_qs = QuestionVariableWave.objects.none()

        if active_wave:
            triad_qs = (
                QuestionVariableWave.objects
                .filter(question=question, wave=active_wave)
                .select_related("variable")
            )
    
            # Eindeutige Variablen für die aktive Welle

            variables = (
                Variable.objects
                .filter(id__in=triad_qs.values_list("variable_id", flat=True))
                .distinct()
                .order_by("varname")
            )

            # Vollständigkeitsinfo ran hängen (nur für Editoren erforderlich)
            if self.can_edit:
                variables = variables.with_completeness()

            # Seite der aktiven Welle
            page = (
                WavePage.objects
                .filter(
                    page_questions__question=question,
                    waves=active_wave,
                )
                .only("id", "pagename")
                .first()
            )
        else:
            variables = Variable.objects.none()
            page = None

        if page:
            screenshots = list(page.screenshots.all())
        else:
            screenshots = []
 

        ctx.update({
            "waves": waves,
            "active_wave": active_wave,
            "variables": variables,
            "question_variable_wave_links": triad_qs,
            "page": page, 
            "screenshots": screenshots,
        })
        return ctx
    
# View zum Anlegen einer neuen Frage 
class QuestionCreateFromPageView(EditorRequiredMixin, View):

    http_method_names = ["post"]

    def post(self, request, page_id, *args, **kwargs):

        page = get_object_or_404(WavePage, pk=page_id)

        # Harte Sperre: wenn Seite an locked-wave hängt → kein Neuanlegen
        if page.waves.filter(is_locked=True).exists():
            messages.error(
                request,
                "Auf dieser Seite können keine neuen Fragen angelegt werden, "
                "weil sie mit einer abgeschlossenen Befragung verknüpft ist."
            )
            url = reverse("pages:page-detail", kwargs={"pk": page.pk})
            wave = request.GET.get("wave")
            if wave:
                url = f"{url}?wave={wave}"
            return redirect(url)

        # Erlaubte Waves: nur Waves der Seite, die NICHT locked sind
        allowed_waves_qs = page.waves.filter(is_locked=False)

        # vom Modal: waves=<id>&waves=<id>...
        selected_ids = request.POST.getlist("waves") or request.POST.getlist("wave_ids")

        # defensive: nur IDs zulassen, die in allowed_waves liegen
        selected_waves = list(allowed_waves_qs.filter(id__in=selected_ids))

        if not selected_waves:
            messages.error(request, "Bitte wähle mindestens eine Befragungsgruppe aus.")
            return redirect(request.META.get("HTTP_REFERER", "/"))


        # Frage anlegen und verknüpfen mit Helferfunktion
        result = create_question_for_page(
                page=page,
                questiontext="",  # ANPASSEN FALLS WIR DEN QT HIER MITGEBEN WOLLEN
                wave_ids=[w.id for w in selected_waves],
            )
        q = result.question

        # Redirect auf Edit-View
        base = reverse("questions:question_edit", kwargs={"pk": q.pk})

        # page ist Pflicht für die Edit-View
        params = f"page={page.pk}"

        # optional: aktive wave für UI mitgeben
        wave = request.GET.get("wave")
        if wave and any(str(w.id) == str(wave) for w in selected_waves):
            params += f"&wave={wave}"
        else:
            params += f"&wave={selected_waves[0].id}"

        return redirect(f"{base}?{params}")
    

# View zum Bearbeiten einer Frage    
class QuestionUpdateView(EditorRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionEditForm
    template_name = "questions/question_form.html"
    context_object_name = "question"

    AO_PREFIX = "ao"
    ITEM_PREFIX = "it"

    # ---- helpers -------------------------------------------------

    # Helper: Edit-View hängt an Seitenkontext.
    # - Wenn ?page=<id> übergeben wird: muss zur Frage passen (sonst 404)
    # - Wenn ?page fehlt: nimm erste verknüpfte Seite (Fragen sind über Seiten hinweg identisch)
    # - Wenn gar keine Seite existiert: return None (Orphan)
    def _get_page_from_request(self, question: Question) -> WavePage | None:
        page_id = self.request.GET.get("page")

        # 1) expliziter Kontext: streng validieren
        if page_id:
            page = get_object_or_404(WavePage, pk=page_id)
            if not WavePageQuestion.objects.filter(wave_page=page, question=question).exists():
                raise Http404("Diese Frage ist nicht mit der angegebenen Seite verknüpft.")
            return page

        # 2) kein Kontext: erste verknüpfte Seite nehmen
        return (
            WavePage.objects
            .filter(page_questions__question=question)
            .order_by("id")
            .first()
        )
    
    # Helper: Redirect zur Attach-View mit Erhalt der ursprünglichen URL
    def _redirect_to_attach(self, request, question):
        attach = reverse("questions:question_attach_page", kwargs={"pk": question.pk})

        # Zurück zur ursprünglich gewünschten URL (inkl. Querystring)
        next_url = request.get_full_path()
        params = f"next={quote(next_url, safe='')}"

        # wave nur durchreichen, wenn sie existiert und nicht locked ist
        wave = request.GET.get("wave")
        if wave and Wave.objects.filter(pk=wave, is_locked=False).exists():
            params += f"&wave={wave}"

        return redirect(f"{attach}?{params}")




    # Helper: Hägt page/wave an URL an
    def _preserve_querystring(self, base_url: str) -> str:
        page = self.request.GET.get("page")

        if not page:
            # Fallback: erste verknüpfte Seite bestimmen (damit URL stabil ist)
            q = getattr(self, "object", None) or self.get_object()
            p = self._get_page_from_request(q)
            if p:
                page = str(p.pk)

        wave = self.request.GET.get("wave")
        if wave and not Wave.objects.filter(pk=wave, is_locked=False).exists():
            wave = None  # locked/invalid nicht durchreichen

        params = []
        if page:
            params.append(f"page={page}")
        if wave:
            params.append(f"wave={wave}")

        if not params:
            return base_url
        return base_url + "?" + "&".join(params)

    

    # Helper: Lädt Initialdaten aus JSON-Listen
    def _json_initial(self, rows: list[dict] | None, fields: list[str]) -> list[dict]:
        rows = rows or []
        initial = []
        for row in rows:
            row = row or {}
            initial.append({f: (row.get(f) or "") for f in fields})
        return initial
    

    # Helper: Wandelt das Formset in JSON-Liste um
    def _formset_to_json(self, formset, fields: list[str]) -> list[dict]:
        out = []
        for cd in formset.cleaned_data:
            # gelöschte Zeilen raus
            if cd.get("DELETE"):
                continue 

            cleaned = {f: (cd.get(f) or "").strip() for f in fields}

            # komplett leere Zeile → ignorieren
            if all(v == "" for v in cleaned.values()):
                continue

            out.append(cleaned)  # Keys vollständig, optionale Felder als ""
        return out

    # Lade Initialdaten für AO- und Item-Formsets
    def _ao_initial(self, question: Question) -> list[dict]:
        return self._json_initial(question.answer_options, ["uid", "variable", "value", "label"])

    def _it_initial(self, question: Question) -> list[dict]:
        return self._json_initial(question.items, ["uid", "variable", "label"])

    # Wandle Formsets von AO und Items in JSON-Listen um
    def _ao_to_json(self, formset) -> list[dict]:
        return self._formset_to_json(formset, ["uid", "variable", "value", "label"])

    def _it_to_json(self, formset) -> list[dict]:
        return self._formset_to_json(formset, ["uid", "variable", "label"])
    

    # Helper: Prüft, ob ein Formset sichtbare Errors hat
    def _formset_has_visible_errors(self, formset) -> bool:
        """
        True, wenn es in einem nicht-gelöschten Form Errors gibt.
        (DELETE-Forms werden für die UI ignoriert.)
        """
        for f in formset.forms:
            # DELETE kommt bei ungültigen Forms evtl. nicht in cleaned_data,
            # daher aus raw POST lesen:
            is_deleted = f.data.get(f"{f.prefix}-DELETE") in ("on", "true", "True", "1")
            if is_deleted:
                continue
            if f.errors:
                return True
        return False




    # ---- View-Methoden -------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        question = getattr(self, "object", None) or self.get_object()

        ctx["page"] = self._get_page_from_request(question)
        ctx["active_wave_id"] = self.request.GET.get("wave")

        # Löschrechte: keine, wenn irgendeine verknüpfte Befragung locked ist
        ctx["can_delete"] = not self.object.waves.filter(is_locked=True).exists()


        if "answeroption_formset" not in ctx:
            if self.request.method == "POST":
                ctx["answeroption_formset"] = AnswerOptionFormSet(
                    self.request.POST,
                    prefix=self.AO_PREFIX,
                )
            else:
                ctx["answeroption_formset"] = AnswerOptionFormSet(
                    initial=self._ao_initial(question),
                    prefix=self.AO_PREFIX,
                )
        
        if "item_formset" not in ctx:
            if self.request.method == "POST":
                ctx["item_formset"] = ItemFormSet(self.request.POST, prefix=self.ITEM_PREFIX)
            else:
                ctx["item_formset"] = ItemFormSet(initial=self._it_initial(question), prefix=self.ITEM_PREFIX)


        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        page = self._get_page_from_request(self.object)
        if page is None:
            messages.error(
                request,
                "Diese Frage ist aktuell keiner Seite zugeordnet. Bitte ordne sie zuerst einer Seite zu."
            )
            return self._redirect_to_attach(request, self.object)



        form = self.get_form()
        ao_formset = AnswerOptionFormSet(request.POST, prefix=self.AO_PREFIX)
        it_formset = ItemFormSet(request.POST, prefix=self.ITEM_PREFIX)

        if form.is_valid() and ao_formset.is_valid() and it_formset.is_valid():
            return self._forms_valid(form, ao_formset, it_formset)

        return self._forms_invalid(form, ao_formset, it_formset)


    def _forms_valid(self, form, ao_formset, it_formset):
        # Hauptobjekt speichern
        self.object = form.save(commit=False)

        # JSON aus Formsets
        self.object.answer_options = self._ao_to_json(ao_formset)
        self.object.items = self._it_to_json(it_formset)

        self.object.save()
        form.save_m2m() # für Keywords

        messages.success(self.request, "Frage gespeichert.")
        return redirect(self.get_success_url())


    def _forms_invalid(self, form, ao_formset, it_formset):
        ctx = self.get_context_data(form=form)
        ctx["answeroption_formset"] = ao_formset
        ctx["item_formset"] = it_formset

        # Flags für sichtbare Errors in Formsets
        ctx["ao_has_visible_errors"] = self._formset_has_visible_errors(ao_formset)
        ctx["it_has_visible_errors"] = self._formset_has_visible_errors(it_formset)

        return self.render_to_response(ctx)
    

    def get_success_url(self):
        url = reverse("questions:question_edit", kwargs={"pk": self.object.pk})
        return self._preserve_querystring(url)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        page = self._get_page_from_request(self.object)

        # Orphan: keine Seitenverknüpfung → Attach-View
        if page is None:
            messages.error(
                request,
                "Diese Frage ist aktuell keiner Seite zugeordnet. Bitte ordne sie zuerst einer Seite zu."
            )
            return self._redirect_to_attach(request, self.object)
        return super().get(request, *args, **kwargs)



    


# Views für Keyword-Suche und -Anlage
class KeywordSearchView(EditorRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()

        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = (
            Keyword.objects
            .filter(name__icontains=q)
            .order_by("name")[:15]
        )

        data = [{"value": kw.id, "text": kw.name} for kw in qs]
        return JsonResponse(data, safe=False)


# View zum Anlegen eines neuen Keywords
class KeywordCreateView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        name = (request.POST.get("name") or "").strip()

        if len(name) < 2:
            return JsonResponse({"error": "Keyword zu kurz."}, status=400)

        # case-insensitive
        existing = Keyword.objects.filter(name__iexact=name).first()
        if existing:
            return JsonResponse({"value": existing.id, "text": existing.name})

        kw = Keyword.objects.create(name=name)
        return JsonResponse({"value": kw.id, "text": kw.name})
    


# View zum Anhängen einer Frage an eine Seite
class QuestionAttachPageView(EditorRequiredMixin, View):
    template_name = "questions/question_attach_page.html"
    http_method_names = ["get", "post"]

    def get(self, request, pk, *args, **kwargs):
        question = get_object_or_404(Question, pk=pk)

        next_url = request.GET.get("next", "")
        # Wenn Nutzer schon wave im Query hat, preselect
        wave_id = request.GET.get("wave")
        selected_wave = None
        if wave_id:
            selected_wave = Wave.objects.filter(pk=wave_id, is_locked=False).first()

        form = AttachWavePageForm(selected_wave=selected_wave, initial={"wave": selected_wave} if selected_wave else None)

        return render(request, self.template_name, {
            "question": question,
            "form": form,
            "next": next_url,
        })

    def post(self, request, pk, *args, **kwargs):
        question = get_object_or_404(Question, pk=pk)

        next_url = request.POST.get("next", "")
        if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = ""

        # Phase 1: Wave wurde gewählt → Formular neu rendern mit Pages dieser Wave
        wave_id = request.POST.get("wave") or None
        selected_wave = None
        if wave_id:
            selected_wave = Wave.objects.filter(pk=wave_id, is_locked=False).first()

        form = AttachWavePageForm(request.POST, selected_wave=selected_wave)

        # Wenn wave_page fehlt, interpretieren wir das als "nur Wave gewählt" (Reload)
        if selected_wave and not request.POST.get("wave_page"):
            return render(request, self.template_name, {
                "question": question,
                "form": form,
                "next": next_url,
            })

        if not form.is_valid():
            return render(request, self.template_name, {
                "question": question,
                "form": form,
                "next": next_url,
            })

        wave = form.cleaned_data["wave"]           # garantiert unlocked
        page = form.cleaned_data["wave_page"]      # Seite dieser wave, und keine locked-wave enthalten

        with transaction.atomic():
            WavePageQuestion.objects.get_or_create(wave_page=page, question=question)
            WaveQuestion.objects.get_or_create(wave=wave, question=question)

        messages.success(request, f"Seite '{page}' wurde zugeordnet.")

        # Danach zurück zur Edit-View, deterministisch mit wave+page
        target = next_url or reverse("questions:question_edit", kwargs={"pk": question.pk})
        sep = "&" if "?" in target else "?"
        return redirect(f"{target}{sep}page={page.pk}&wave={wave.pk}")
    

# View zum Löschen einer Frage
class QuestionDeleteView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    @transaction.atomic
    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk)

        # Schutz: keine Löschung, wenn irgendeine verknüpfte Befragung locked ist
        if question.waves.filter(is_locked=True).exists():
            messages.error(
                request,
                "Diese Frage ist mit mindestens einer gesperrten Befragung verknüpft und kann nicht gelöscht werden.",
            )
            return redirect("questions:question_edit", pk=question.pk)

        question.delete()
        messages.success(request, "Frage wurde gelöscht.")
        return redirect("waves:survey_list")
    
# AJAX-View zum Anlegen einer Frage auf einer Seite
# Rückgabe JSON mit Erfolg oder Fehler
class QuestionQuickCreateForPageAjaxView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, page_id, *args, **kwargs):
        page = get_object_or_404(WavePage, pk=page_id)

        # Harte Sperre: wenn Seite locked → kein Neuanlegen
        if page.waves.filter(is_locked=True).exists():
            return JsonResponse({
                "ok": False,
                "error": "Auf dieser Seite können keine neuen Fragen angelegt werden, weil sie mit einer abgeschlossenen Befragung verknüpft ist."
            }, status=400)

        allowed_waves_qs = page.waves.filter(is_locked=False)
        allowed_ids = set(allowed_waves_qs.values_list("id", flat=True))

        questiontext = (request.POST.get("questiontext") or "").strip()
        wave_ids_raw = request.POST.getlist("wave_ids")

        if not questiontext:
            return JsonResponse({"ok": False, "error": "Bitte gib einen Fragetext ein."}, status=400)

        if not wave_ids_raw:
            return JsonResponse({"ok": False, "error": "Bitte wähle mindestens eine Befragungsgruppe aus."}, status=400)

        try:
            wave_ids = [int(x) for x in wave_ids_raw]
        except ValueError:
            return JsonResponse({"ok": False, "error": "Ungültige Wave-Auswahl."}, status=400)

        if not set(wave_ids).issubset(allowed_ids):
            return JsonResponse({
                "ok": False,
                "error": "Mindestens eine ausgewählte Befragungsgruppe ist nicht zulässig (ggf. locked)."
            }, status=400)

        result = create_question_for_page(
            page=page,
            questiontext=questiontext,
            wave_ids=wave_ids,
        )

        q = result.question

        return JsonResponse({
            "ok": True,
            "question": {
                "id": q.id,
                "label": q.questiontext[:200],
            },
        })
    
# View zum Zuweisen von Variablen zu einer Frage in bestimmten Waves
class QuestionVariableAssignView(EditorRequiredMixin, View):
    template_name = "questions/question_variables_form.html"
    http_method_names = ["get", "post"]

    def get(self, request, pk, *args, **kwargs):
        question = get_object_or_404(Question, pk=pk)

        waves_qs = question.waves.all().order_by("cycle", "instrument", "id")
        locked_wave_ids = list(waves_qs.filter(is_locked=True).values_list("id", flat=True))

        # active wave (nur UI)
        active_wave = None
        wave_param = request.GET.get("wave")
        if waves_qs.exists():
            if wave_param and waves_qs.filter(id=wave_param).exists():
                active_wave = waves_qs.get(id=wave_param)
            else:
                active_wave = waves_qs.order_by("-id").first()

        formset = _build_question_variable_formset(
            question=question,
            question_waves=waves_qs,
            method="GET",
        )

        return render(request, self.template_name, {
            "question": question,
            "waves": waves_qs,
            "locked_wave_ids": locked_wave_ids,
            "active_wave": active_wave,
            "formset": formset,
            "question_is_locked": waves_qs.filter(is_locked=True).exists(),
            "back_url": request.GET.get("back", ""),
        })

    def post(self, request, pk, *args, **kwargs):
        question = get_object_or_404(Question, pk=pk)

        waves_qs = question.waves.all().order_by("cycle", "instrument", "id")
        locked_wave_ids = list(waves_qs.filter(is_locked=True).values_list("id", flat=True))

        formset = _build_question_variable_formset(
            question=question,
            question_waves=waves_qs,
            method="POST",
            post_data=request.POST,
        )

        if not formset.is_valid():
            return render(request, self.template_name, {
                "question": question,
                "waves": waves_qs,
                "locked_wave_ids": locked_wave_ids,
                "active_wave": None,
                "formset": formset,
                "question_is_locked": False,
                "back_url": request.POST.get("back_url", ""),
            })

        # Zielmenge (desired triples) bauen
        desired = set()  # (variable_id, wave_id)
        used_var_ids = set()
        used_wave_ids = set()

        for cd in formset.cleaned_data:
            if not cd or cd.get("DELETE"):
                continue
            var = cd.get("variable")
            if not var:
                continue
            wlist = cd.get("waves") or []
            for w in wlist:
                desired.add((var.id, w.id))
                used_var_ids.add(var.id)
                used_wave_ids.add(w.id)

        existing_qs = QuestionVariableWave.objects.filter(question=question)
        existing = set(existing_qs.values_list("variable_id", "wave_id"))

        to_add = desired - existing
        to_remove = existing - desired

        with transaction.atomic():
            # delete QuestionVariableWave-Einträge
            if to_remove:
                q = Q()
                for v_id, w_id in to_remove:
                    q |= Q(variable_id=v_id, wave_id=w_id)
                QuestionVariableWave.objects.filter(question=question).filter(q).delete()

            # create QuestionVariableWave-Einträge & Konsistenz QuestionVariableWave ⇒ WaveVar
            if to_add:
                QuestionVariableWave.objects.bulk_create(
                    [QuestionVariableWave(question=question, variable_id=v, wave_id=w) for v, w in to_add],
                    ignore_conflicts=True,
                )

                WavesThrough = Variable._meta.get_field("waves").remote_field.through
                through_rows = [WavesThrough(variable_id=v, wave_id=w) for v, w in to_add]
                WavesThrough.objects.bulk_create(through_rows, ignore_conflicts=True)


            if to_remove:
                candidate_pairs = set(to_remove)

                # Welche Variablen-Befragungs-Paare existieren weiterhin QuestionVariableWave (über alle Fragen)?
                q = Q()
                for v_id, w_id in candidate_pairs:
                    q |= Q(variable_id=v_id, wave_id=w_id)

                still_used_pairs = set(
                    QuestionVariableWave.objects
                    .filter(q)
                    .values_list("variable_id", "wave_id")
                )

                # Nur die Paare, die nirgendwo mehr im QuestionVariableWave vorkommen, aus WaveVar entfernen
                cleanup_pairs = candidate_pairs - still_used_pairs
                if cleanup_pairs:
                    WavesThrough = Variable._meta.get_field("waves").remote_field.through
                    q = Q()
                    for v_id, w_id in cleanup_pairs:
                        q |= Q(variable_id=v_id, wave_id=w_id)
                    WavesThrough.objects.filter(q).delete()


        messages.success(request, "Variablen-Zuordnung wurde gespeichert.")
        back = request.POST.get("back_url") or ""
        if back:
            return redirect(back)

        url = reverse("questions:question_detail", kwargs={"pk": question.pk})
        wave = request.GET.get("wave")
        if wave:
            url = f"{url}?wave={wave}"
        return redirect(url)