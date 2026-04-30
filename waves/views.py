from collections import defaultdict
from itertools import groupby
import json

from django.views import View
from django.views.generic import ListView, TemplateView, CreateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.http import Http404, JsonResponse, FileResponse
from django.db import transaction
from django.db.models import Count, Min, Max, Prefetch
from django.db.models.functions import Substr
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from .models import Survey, Wave, WaveModule, WaveQuestion, WaveDocument
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
            .prefetch_related("documents")
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
        ctx["wave_documents"] = list(active_wave.documents.all()) if active_wave else []


        # ------------------------------------------------------------
        # ALL MODE: Gesamtübersicht, getrennt nach Instrument
        # ------------------------------------------------------------
        if is_all_mode:
            available_instruments = list(
                waves_qs
                .order_by("instrument")
                .values_list("instrument", flat=True)
                .distinct()
            )

            active_instrument = self.request.GET.get("instrument")

            if active_instrument not in available_instruments:
                active_instrument = available_instruments[0] if available_instruments else None

            instrument_waves = list(
                waves_qs
                .filter(instrument=active_instrument)
                .order_by("cycle", "id")
            )

            instrument_wave_ids = [w.id for w in instrument_waves]

            def normalize_module_name(name):
                return (name or "").strip().lower()

            def merge_ordered_sequences(sequences):
                """
                Erstellt eine gemeinsame Reihenfolge aus mehreren Wave-spezifischen
                Reihenfolgen.

                Beispiel:
                Wave 1: A B C D E
                Wave 2: A D E F G
                Ergebnis: A B C D E F G

                Bei echten Widersprüchen, z. B. A B C vs. A C B,
                wird ein stabiler Fallback genutzt und conflict=True zurückgegeben.
                """
                from collections import defaultdict, deque

                nodes = []
                node_set = set()
                first_seen_index = {}
                first_seen_counter = 0

                graph = defaultdict(set)
                indegree = defaultdict(int)

                # Nodes + Reihenfolge des ersten Auftretens erfassen
                for seq in sequences:
                    for node in seq:
                        if node not in node_set:
                            node_set.add(node)
                            nodes.append(node)
                            first_seen_index[node] = first_seen_counter
                            first_seen_counter += 1
                        indegree[node] = indegree[node]

                # Kanten aus direkter Nachbarschaft bilden:
                # A B C ergibt A < B und B < C
                for seq in sequences:
                    for left, right in zip(seq, seq[1:]):
                        if right not in graph[left]:
                            graph[left].add(right)
                            indegree[right] += 1

                queue = deque(
                    sorted(
                        [node for node in nodes if indegree[node] == 0],
                        key=lambda node: first_seen_index[node],
                    )
                )

                result = []

                while queue:
                    node = queue.popleft()
                    result.append(node)

                    for child in sorted(graph[node], key=lambda n: first_seen_index[n]):
                        indegree[child] -= 1
                        if indegree[child] == 0:
                            queue.append(child)

                    queue = deque(sorted(queue, key=lambda n: first_seen_index[n]))

                conflict = len(result) != len(nodes)

                if not conflict:
                    return result, False

                # Fallback bei widersprüchlichen Sequenzen:
                # stabile Einfüge-Logik, damit trotzdem eine brauchbare Ansicht entsteht
                fallback = []

                for seq in sequences:
                    for item in seq:
                        if item not in fallback:
                            fallback.append(item)

                        current_index = fallback.index(item)

                        predecessors = seq[:seq.index(item)]
                        for pred in predecessors:
                            if pred not in fallback:
                                fallback.insert(current_index, pred)
                                current_index += 1
                            else:
                                pred_index = fallback.index(pred)
                                current_index = fallback.index(item)

                                if pred_index > current_index:
                                    fallback.pop(pred_index)
                                    current_index = fallback.index(item)
                                    fallback.insert(current_index, pred)

                return fallback, True

            def find_relative_order_conflicts(sequences):
                """
                Prüft, ob Elemente in verschiedenen Sequenzen relativ unterschiedlich
                sortiert sind.

                Fehlende Elemente sind erlaubt:
                Sequenz 1: A B C D
                Sequenz 2: A B D
                => kein Konflikt

                Echte Umstellung:
                Sequenz 1: A B C D
                Sequenz 2: B C D A
                => Konflikt für die beteiligten Elemente
                """
                conflict_ids = set()

                relevant_sequences = [
                    seq
                    for seq in sequences
                    if len(seq) > 1
                ]

                for i, seq_a in enumerate(relevant_sequences):
                    pos_a = {item_id: idx for idx, item_id in enumerate(seq_a)}

                    for seq_b in relevant_sequences[i + 1:]:
                        pos_b = {item_id: idx for idx, item_id in enumerate(seq_b)}
                        common_item_ids = list(set(pos_a) & set(pos_b))

                        if len(common_item_ids) < 2:
                            continue

                        for idx, item_id_1 in enumerate(common_item_ids):
                            for item_id_2 in common_item_ids[idx + 1:]:
                                order_a = pos_a[item_id_1] < pos_a[item_id_2]
                                order_b = pos_b[item_id_1] < pos_b[item_id_2]

                                if order_a != order_b:
                                    conflict_ids.add(item_id_1)
                                    conflict_ids.add(item_id_2)

                return conflict_ids

            # Modul-Sequenzen pro Wave erfassen
            module_sequences = []

            for wave in instrument_waves:
                sequence = []

                modules_for_wave = (
                    WaveModule.objects
                    .filter(wave=wave)
                    .order_by("sort_order", "id")
                )

                for module in modules_for_wave:
                    sequence.append(("module", normalize_module_name(module.name)))

                module_sequences.append(sequence)

            merged_module_order, module_order_has_cycle_conflict = merge_ordered_sequences(module_sequences)

            # Modul-Warnungen nur bei echter relativer Reihenfolge-Abweichung,
            # nicht bei fehlenden Modulen.
            module_order_conflict_keys = find_relative_order_conflicts(module_sequences)
            module_order_has_conflicts = bool(module_order_conflict_keys) or module_order_has_cycle_conflict

            module_order_index = {
                key: idx
                for idx, key in enumerate(merged_module_order)
            }

            page_links_qs = (
                WavePageWave.objects
                .filter(wave_id__in=instrument_wave_ids)
                .select_related("wave", "module")
                .prefetch_related(
                    Prefetch("page", queryset=WavePage.objects.with_completeness())
                )
                .order_by(
                    "module__sort_order",
                    "module__name",
                    "sort_order",
                    "page__pagename",
                    "wave__cycle",
                    "wave__id",
                )
            )

            page_ids = list(
                page_links_qs
                .values_list("page_id", flat=True)
                .distinct()
            )

            instrument_question_ids = (
                WaveQuestion.objects
                .filter(wave_id__in=instrument_wave_ids)
                .values_list("question_id", flat=True)
                .distinct()
            )

            counts_qs = (
                WavePageQuestion.objects
                .filter(wave_page_id__in=page_ids)
                .filter(question_id__in=instrument_question_ids)
                .values("wave_page_id")
                .annotate(cnt=Count("id"))
            )

            page_question_counts = {row["wave_page_id"]: row["cnt"] for row in counts_qs}
            page_question_snippets = defaultdict(list)

            snippets_qs = (
                WavePageQuestion.objects
                .filter(wave_page_id__in=page_ids)
                .filter(question_id__in=instrument_question_ids)
                .annotate(snippet=Substr("question__questiontext", 1, 100))
                .values_list("wave_page_id", "snippet")
                .order_by("wave_page_id", "id")
            )

            for pid, snip in snippets_qs:
                snip = (snip or "").replace("\n", " ").strip()
                if snip:
                    page_question_snippets[pid].append(snip)

            # Aggregation: gleichnamige Module innerhalb eines Instruments zusammenführen
            blocks_by_key = {}

            for link in page_links_qs:
                if link.module_id:
                    module_name = link.module.name
                    module_key = ("module", normalize_module_name(module_name))
                    module_sort = link.module.sort_order
                    module_label = module_name
                    is_unassigned = False
                else:
                    module_key = ("unassigned", "")
                    module_sort = 0
                    module_label = "Ohne Modul"
                    is_unassigned = True

                if module_key not in blocks_by_key:
                    blocks_by_key[module_key] = {
                        "key": module_key,
                        "name": module_label,
                        "is_unassigned": is_unassigned,
                        "module_positions": [],
                        "pages_by_id": {},
                        "page_sequences_by_wave": defaultdict(list),
                    }

                block = blocks_by_key[module_key]
                block["module_positions"].append(module_sort)
                block["page_sequences_by_wave"][link.wave_id].append(link.page_id)

                page_entry = block["pages_by_id"].setdefault(
                    link.page_id,
                    {
                        "page": link.page,
                        "waves": [],
                        "positions": [],
                        "min_sort_order": link.sort_order,
                        "sort_order_varies": False,
                        "position_tooltip": "",
                        "delete_blocked": False,
                    },
                )

                page_entry["waves"].append(link.wave)
                page_entry["positions"].append((link.wave, link.sort_order))
                page_entry["min_sort_order"] = min(page_entry["min_sort_order"], link.sort_order)
                
                if link.wave.is_locked:
                    page_entry["delete_blocked"] = True

            all_mode_module_blocks = []

            for block in blocks_by_key.values():
                module_positions = block["module_positions"] or [0]

                pages = list(block["pages_by_id"].values())

                page_order_conflict_ids = find_relative_order_conflicts(
                    block["page_sequences_by_wave"].values()
                )

                for page_entry in pages:
                    page_entry["sort_order_varies"] = page_entry["page"].id in page_order_conflict_ids

                    if page_entry["sort_order_varies"]:
                        page_entry["position_tooltip"] = (
                            "Die relative Reihenfolge dieser Seite unterscheidet sich zwischen Gruppen."
                        )
                    else:
                        page_entry["position_tooltip"] = ""

                    page_entry["waves"] = sorted(
                        page_entry["waves"],
                        key=lambda w: (w.cycle, w.id),
                    )

                pages.sort(
                    key=lambda p: (
                        p["min_sort_order"],
                        p["page"].pagename.lower(),
                        p["page"].id,
                    )
                )

                module_has_relative_order_conflict = block["key"] in module_order_conflict_keys

                all_mode_module_blocks.append({
                    "key": block["key"],
                    "name": block["name"],
                    "is_unassigned": block["is_unassigned"],
                    "pages": pages,
                    "min_module_sort_order": min(module_positions),
                    "module_sort_varies": module_has_relative_order_conflict,
                    "module_position_tooltip": (
                        "Die relative Reihenfolge dieses Moduls unterscheidet sich zwischen Gruppen."
                        if module_has_relative_order_conflict
                        else ""
                    ),
                })

            all_mode_module_blocks.sort(
                key=lambda b: (
                    1 if b["is_unassigned"] else 0,
                    module_order_index.get(b["key"], 9999),
                    b["name"].lower(),
                )
            )

            ctx["available_instruments"] = available_instruments
            ctx["active_instrument"] = active_instrument
            ctx["instrument_waves"] = instrument_waves
            ctx["all_mode_module_blocks"] = all_mode_module_blocks
            ctx["module_order_has_conflicts"] = module_order_has_conflicts
            ctx["page_question_counts"] = page_question_counts
            ctx["page_question_snippets"] = page_question_snippets

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

        # Dictionaries für Seitenkontext: Anzahl Fragen + Anfang Fragetext
        page_question_counts = {row["wave_page_id"]: row["cnt"] for row in counts_qs}
        page_question_snippets = defaultdict(list)

        snippets_qs = (
            WavePageQuestion.objects
            .filter(wave_page_id__in=page_ids)
            .filter(question_id__in=wave_question_ids)
            .annotate(snippet=Substr("question__questiontext", 1, 100))
            .values_list("wave_page_id", "snippet")
            .order_by("wave_page_id", "id")
        )

        for pid, snip in snippets_qs:
            snip = (snip or "").replace("\n", " ").strip()
            if snip:
                page_question_snippets[pid].append(snip)

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
        ctx["page_question_snippets"] = page_question_snippets
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


# View zum Anzeigen des PDF-Dokuments einer WaveDocument-Instanz
class WaveDocumentPdfView(View):
    def get(self, request, pk):
        document = get_object_or_404(WaveDocument, pk=pk)

        if not document.pdf_file:
            raise Http404("Kein PDF hinterlegt.")

        response = FileResponse(
            document.pdf_file.open("rb"),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'inline; filename="{document.pdf_file.name.split("/")[-1]}"'
        return response
    

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
