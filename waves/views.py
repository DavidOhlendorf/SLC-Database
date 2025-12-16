from itertools import groupby

from django.views.generic import ListView, TemplateView
from django.http import Http404
from django.db.models import Count

from .models import Wave, WaveQuestion
from pages.models import WavePageQuestion, WavePage


class SurveyListView(ListView):
    template_name = "waves/survey_list.html"
    context_object_name = "surveys"

    def get_queryset(self):
        waves = (
            Wave.objects
            .exclude(surveyyear__isnull=True)
            .exclude(surveyyear__exact="")
            .order_by("-surveyyear", "cycle", "instrument", "id")
        )

        surveys = []
        for surveyyear, group in groupby(waves, key=lambda w: w.surveyyear):
            group_list = list(group)
            start_dates = [w.start_date for w in group_list if w.start_date]
            end_dates = [w.end_date for w in group_list if w.end_date]

            surveys.append({
                "surveyyear": surveyyear,
                "waves": group_list,
                "wave_count": len(group_list),
                "start_min": min(start_dates) if start_dates else None,
                "end_max": max(end_dates) if end_dates else None,
            })

        return surveys

class SurveyDetailView(TemplateView):
    template_name = "waves/survey_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        surveyyear = self.kwargs["surveyyear"]

        waves_qs = (
            Wave.objects
            .filter(surveyyear=surveyyear)
            .order_by("cycle", "instrument", "id")
        )
        if not waves_qs.exists():
            raise Http404("Survey not found")

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

        ctx["surveyyear"] = surveyyear
        ctx["waves"] = waves_qs
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