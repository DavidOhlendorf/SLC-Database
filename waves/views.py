from itertools import groupby
import json

from django.views import View
from django.views.generic import ListView, TemplateView, CreateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.forms import inlineformset_factory
from django.http import Http404, JsonResponse
from django.db import transaction
from django.db.models import Count, Min, Max, Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from .models import Survey, Wave, WaveModule, WaveQuestion
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
        modules_qs = WaveModule.objects.filter(wave=active_wave).order_by("sort_order", "id")

        page_links_qs = (
            WavePageWave.objects
            .filter(wave=active_wave)
            .select_related("module")  # module direkt
            .prefetch_related(
                Prefetch("page", queryset=WavePage.objects.with_completeness())
            )
            .order_by("sort_order", "page__pagename")
        )

        # Frage-Counts pro Seite (weiter wie bisher, aber über page_ids)
        wave_question_ids = (
            WaveQuestion.objects
            .filter(wave=active_wave)
            .values_list("question_id", flat=True)
        )

        page_ids = list(page_links_qs.values_list("page_id", flat=True))

        counts_qs = (
            WavePageQuestion.objects
            .filter(wave_page_id__in=page_ids)
            .filter(question_id__in=wave_question_ids)
            .values("wave_page_id")
            .annotate(cnt=Count("id"))
        )
        page_question_counts = {row["wave_page_id"]: row["cnt"] for row in counts_qs}

        # Gruppierung fürs Template: Liste von Blöcken 
        module_blocks = [{"module": m, "links": []} for m in modules_qs]
        blocks_by_id = {b["module"].id: b for b in module_blocks}
        unassigned_links = []

        for link in page_links_qs:
            if link.module_id and link.module_id in blocks_by_id:
                blocks_by_id[link.module_id]["links"].append(link)
            else:
                unassigned_links.append(link)

        ctx["modules"] = modules_qs
        ctx["module_blocks"] = module_blocks
        ctx["unassigned_links"] = unassigned_links
        ctx["page_question_counts"] = page_question_counts
        ctx["delete_blocked_global"] = bool(active_wave and active_wave.is_locked)
        return ctx
    
    # POST request for creating a new WavePage
    def post(self, request, *args, **kwargs):

        if request.POST.get("create_page") != "1":
            return redirect(request.get_full_path())
        
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
    

# API View for reordering WavePages within a Wave    
class WavePagesReorderApiView(View):
    http_method_names = ["post"]

    def post(self, request, wave_id, *args, **kwargs):
        if not request.user.has_perm("accounts.can_edit_slc"):
            raise PermissionDenied

        wave = get_object_or_404(Wave, pk=wave_id)

        if wave.is_locked:
            return JsonResponse({"ok": False, "error": "Befragung ist gesperrt."}, status=403)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "Ungültiges JSON."}, status=400)

        containers = payload.get("containers")
        if not isinstance(containers, list) or not containers:
            return JsonResponse({"ok": False, "error": "containers fehlt/leer."}, status=400)

        all_page_ids = []
        module_ids = set()

        # validate containers
        for c in containers:
            if not isinstance(c, dict):
                return JsonResponse({"ok": False, "error": "containers Format ungültig."}, status=400)

            mids = c.get("module_id", None)
            pids = c.get("page_ids", [])

            if mids is not None:
                if not isinstance(mids, int):
                    return JsonResponse({"ok": False, "error": "module_id ungültig."}, status=400)
                module_ids.add(mids)

            if not isinstance(pids, list):
                return JsonResponse({"ok": False, "error": "page_ids ungültig."}, status=400)

            try:
                pids = [int(x) for x in pids]
            except (TypeError, ValueError):
                return JsonResponse({"ok": False, "error": "page_ids enthält ungültige IDs."}, status=400)

            all_page_ids.extend(pids)

        if not all_page_ids:
            return JsonResponse({"ok": False, "error": "Keine Seiten übergeben."}, status=400)

        if len(set(all_page_ids)) != len(all_page_ids):
            return JsonResponse({"ok": False, "error": "page_ids enthält Duplikate."}, status=400)

        # pages gehören zur wave?
        existing_links = set(
            WavePageWave.objects.filter(wave=wave, page_id__in=all_page_ids)
            .values_list("page_id", flat=True)
        )
        if len(existing_links) != len(all_page_ids):
            return JsonResponse({"ok": False, "error": "Mindestens eine Seite gehört nicht zu dieser Befragung."}, status=400)

        # module_ids gehören zur wave?
        if module_ids:
            existing_modules = set(
                WaveModule.objects.filter(wave=wave, id__in=module_ids).values_list("id", flat=True)
            )
            if existing_modules != module_ids:
                return JsonResponse({"ok": False, "error": "Mindestens ein Modul gehört nicht zu dieser Befragung."}, status=400)

        # Update: module + globale Sortierung speichern
        with transaction.atomic():
            links = list(WavePageWave.objects.filter(wave=wave, page_id__in=all_page_ids))
            link_by_page = {l.page_id: l for l in links}

            idx = 0
            for c in containers:
                mids = c.get("module_id", None)
                pids = [int(x) for x in c.get("page_ids", [])]
                for pid in pids:
                    idx += 1
                    l = link_by_page[pid]
                    l.sort_order = idx
                    l.module_id = mids

            WavePageWave.objects.bulk_update(links, ["sort_order", "module"])

        return JsonResponse({"ok": True})


    

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
    

class WaveModulesManageView(View):
    http_method_names = ["post"]

    def post(self, request, wave_id, *args, **kwargs):
        if not request.user.has_perm("accounts.can_edit_slc"):
            raise PermissionDenied

        wave = get_object_or_404(Wave, pk=wave_id)

        if wave.is_locked:
            messages.error(request, "Module können nicht bearbeitet werden, weil die Befragung gesperrt ist.")
            return redirect(f"{reverse('waves:survey_detail', kwargs={'survey_name': wave.survey.name})}?wave={wave.id}")

        delete_ids = [int(x) for x in request.POST.getlist("delete_ids") if x.isdigit()]

        order_raw = (request.POST.get("module_order") or "").strip()
        order_keys = [k for k in order_raw.split(",") if k]

        with transaction.atomic():
            # 1) aktuelle Module laden (vor deletes)
            modules_qs = WaveModule.objects.filter(wave=wave)
            modules_by_id = {m.id: m for m in modules_qs}

            # 2) deletes
            if delete_ids:
                WaveModule.objects.filter(wave=wave, id__in=delete_ids).delete()

            # 3) updates (bestehende Namen)
            #    + Name-Duplikate sauber prüfen (case-insensitive)
            seen = set()
            remaining_ids = set(
                WaveModule.objects.filter(wave=wave).values_list("id", flat=True)
            )

            # existing name updates
            for mid in list(remaining_ids):
                val = (request.POST.get(f"name_{mid}") or "").strip()
                if not val:
                    continue
                low = val.lower()
                if low in seen:
                    messages.error(request, "Speichern nicht möglich: Modulnamen müssen innerhalb der Wave eindeutig sein.")
                    return redirect(f"{reverse('waves:survey_detail', kwargs={'survey_name': wave.survey.name})}?wave={wave.id}")
                seen.add(low)
                WaveModule.objects.filter(wave=wave, id=mid).update(name=val)

            # 4) creates (neue Module anhand order_keys: new-*)
            #    Wir erzeugen neue Module nur, wenn sie im order vorkommen und ein Name existiert.
            new_key_to_id = {}
            max_sort = WaveModule.objects.filter(wave=wave).aggregate(m=Max("sort_order"))["m"] or 0
            temp_base = max_sort + 1000
            temp_i = 0

            for key in order_keys:
                if not key.startswith("new-"):
                    continue
                name = (request.POST.get(f"new_name_{key}") or "").strip()
                if not name:
                    continue
                low = name.lower()
                if low in seen:
                    messages.error(request, "Speichern nicht möglich: Modulnamen müssen innerhalb der Wave eindeutig sein.")
                    return redirect(f"{reverse('waves:survey_detail', kwargs={'survey_name': wave.survey.name})}?wave={wave.id}")
                seen.add(low)

                temp_i += 1
                m = WaveModule.objects.create(
                    wave=wave,
                    name=name,
                    sort_order=temp_base + temp_i,  # temporär eindeutig
                )
                new_key_to_id[key] = m.id

            # 5) finale Reihenfolge der IDs bestimmen
            existing_ids_now = list(WaveModule.objects.filter(wave=wave).values_list("id", flat=True))
            existing_set = set(existing_ids_now)

            final_ids = []
            for key in order_keys:
                if key.startswith("new-"):
                    mid = new_key_to_id.get(key)
                    if mid:
                        final_ids.append(mid)
                else:
                    if key.isdigit():
                        mid = int(key)
                        if mid in existing_set:
                            final_ids.append(mid)

            # falls irgendein Modul nicht in order_keys stand (z.B. weil order leer): hinten dran
            missing = [mid for mid in existing_ids_now if mid not in final_ids]
            final_ids.extend(missing)

            # 6) sort_order constraint-sicher setzen (2 Phasen)
            max_sort2 = WaveModule.objects.filter(wave=wave).aggregate(m=Max("sort_order"))["m"] or 0
            temp_base2 = max_sort2 + 2000

            # Phase A: alle auf einzigartige temporäre Werte
            for idx, mid in enumerate(final_ids, start=1):
                WaveModule.objects.filter(wave=wave, id=mid).update(sort_order=temp_base2 + idx)

            # Phase B: final 1..n
            for idx, mid in enumerate(final_ids, start=1):
                WaveModule.objects.filter(wave=wave, id=mid).update(sort_order=idx)

        messages.success(request, "Module gespeichert.")
        return redirect(f"{reverse('waves:survey_detail', kwargs={'survey_name': wave.survey.name})}?wave={wave.id}")
