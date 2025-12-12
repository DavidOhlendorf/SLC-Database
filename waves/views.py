from itertools import groupby

from django.views.generic import ListView, TemplateView
from django.http import Http404
from django.db.models import Count

from .models import Wave, WaveQuestion
from pages.models import WavePageQuestion


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

        active_wave = None
        wave_id = self.request.GET.get("wave")
        if wave_id:
            try:
                wave_id_int = int(wave_id)
                active_wave = waves_qs.filter(id=wave_id_int).first()
            except ValueError:
                active_wave = None

        if active_wave is None:
            active_wave = waves_qs.first()

        pages_qs = active_wave.pages.all().order_by("pagename")

        # --- Frage-Counts pro Page (nur für active_wave) ---
        wave_question_ids = WaveQuestion.objects.filter(
            wave=active_wave
        ).values_list("question_id", flat=True)

        counts_qs = (
            WavePageQuestion.objects
            .filter(wave_page__in=pages_qs)
            .filter(question_id__in=wave_question_ids)
            .values("wave_page_id")
            .annotate(cnt=Count("id"))
        )

        page_question_counts = {row["wave_page_id"]: row["cnt"] for row in counts_qs}

        ctx["surveyyear"] = surveyyear
        ctx["waves"] = waves_qs
        ctx["active_wave"] = active_wave
        ctx["pages"] = pages_qs
        ctx["page_question_counts"] = page_question_counts

        return ctx