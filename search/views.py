from collections import defaultdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from pages.models import WavePage
from questions.formatting import strip_pv_formatting
from questions.models import Question
from variables.models import Variable
from waves.models import Wave

from .services.questions import (
    build_question_groups,
    search_questions,
    sort_question_groups,
)
from .services.variables import (
    build_variable_groups,
    search_variables,
    sort_variable_groups,
)

ALLOWED_TYPES = {"all", "questions", "variables",}
ALLOWED_SORTS = {"relevance", "alpha"}
RESULTS_PER_PAGE = 20



# Landing-Page für die Suche
def search_landing(request):
    ctx = {
        "page_count": WavePage.objects.count(),
        "question_count": Question.objects.count(),
        "variable_count": Variable.objects.count(),
        "wave_count": Wave.objects.count(),
    }
    return render(request, "search/landing.html", ctx)




# Paginierungs-Hilfsfunktionen
def paginate_list(items, request, per_page=RESULTS_PER_PAGE):
    """
    Paginierung für bereits materialisierte Python-Listen.
    """
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj


def search(request):
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("search:search_landing")

    search_type = (request.GET.get("type") or "all").lower()
    if search_type not in ALLOWED_TYPES:
        search_type = "all"

    sort = (request.GET.get("sort") or "relevance").lower()
    if sort not in ALLOWED_SORTS:
        sort = "relevance"

    # Wellen-Filter
    wave_ids = []
    try:
        wave_ids = [int(x) for x in request.GET.getlist("waves") if x.strip().isdigit()]
    except Exception:
        wave_ids = []
    
    # Für Auswahl + Chips
    all_waves = Wave.objects.select_related("survey").order_by(
        F("survey__year").desc(nulls_last=True),
        "survey__name",
        "cycle",
        "instrument",
        "id",
    )
    selected_waves = list(all_waves.filter(id__in=wave_ids)) if wave_ids else []

    ctx = {
        "q": q,
        "type": search_type,
        "sort": sort,
        "has_query": True,
        "TOP_N": 5,
        "tabs": [
            ("all", "Alle"),
            ("questions", "Fragen"),
            ("variables", "Variablen"),
        ],
        "all_waves": all_waves,
        "selected_waves": selected_waves,
        "selected_wave_ids": [w.id for w in selected_waves],
        "show_relevance": settings.DEBUG, # Debug: show Relevance-Scores
    }

    # Für Facetten: Zähler und Set
    facet_counter = defaultdict(int)
    facet_waves_set = set()



    # =========================
    # QUESTIONS 
    # =========================
    if search_type in {"all", "questions"}:
        questions_found, final_score_map = search_questions(
        q=q,
        wave_ids=wave_ids,
        include_keywords=True,
        )

        question_groups = build_question_groups(
            matched_questions=questions_found,
            score_map=final_score_map,
            wave_ids=wave_ids,
        )
        questions_sorted = sort_question_groups(question_groups, sort)
 
        # Nur konkrete Suchtreffer dürfen die Facettenzahlen bestimmen.
        # Zusätzlich angezeigte Versionen derselben Gruppe werden nicht gezählt.
        matched_question_ids = {
            question.id
            for question in questions_found
        }

        # Eine Versionsgruppe zählt pro Welle höchstens einmal.
        for group in question_groups:
            group_waves = {}

            for question in group["questions"]:
                if question.id not in matched_question_ids:
                    continue

                for wave in question.waves.all():
                    group_waves[wave.id] = wave

            for wave in group_waves.values():
                facet_counter[wave.id] += 1
                facet_waves_set.add(wave)



        if search_type == "all":
            ctx["questions"] = questions_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(questions_sorted, request)
            ctx["questions_page"] = page_obj
            ctx["questions"] = page_obj.object_list

        # Anzahl der Ergebniskarten, nicht Anzahl einzelner Fragenversionen.
        ctx["questions_count"] = len(questions_sorted)
        ctx.setdefault("questions_count", 0)


    # =========================
    # VARIABLES
    # =========================

    if search_type in {"all", "variables"}:

        variables_found, final_var_score_map = search_variables(
            q=q,
            wave_ids=wave_ids,
        )

        variable_groups = build_variable_groups(
            matched_variables=variables_found,
            score_map=final_var_score_map,
            wave_ids=wave_ids,
        )

        variables_sorted = sort_variable_groups(
            variable_groups,
            sort,
        )

        # Nur konkrete Suchtreffer dürfen die Facettenzahlen bestimmen.
        # Zusätzlich angezeigte Varianten derselben Familie werden nicht gezählt.
        matched_variable_ids = {
            variable.id
            for variable in variables_found
        }

        # Eine Variablenfamilie zählt pro Welle höchstens einmal.
        for group in variable_groups:
            group_waves = {}

            for variable in group["variables"]:
                if variable.id not in matched_variable_ids:
                    continue

                for wave in variable.search_all_waves:
                    group_waves[wave.id] = wave

            for wave in group_waves.values():
                facet_counter[wave.id] += 1
                facet_waves_set.add(wave)

        if search_type == "all":
            ctx["variables"] = variables_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(variables_sorted, request)
            ctx["variables_page"] = page_obj
            ctx["variables"] = page_obj.object_list

        # Anzahl der Ergebniskarten, nicht Anzahl einzelner Varianten.
        ctx["variables_count"] = len(variables_sorted)
        ctx.setdefault("variables_count", 0)




    # Facetten-Wellen sortieren nach Anzahl Treffer + Jahr
    facet_waves_sorted = sorted(
        facet_waves_set,
        key=lambda w: (
            (w.survey_id is not None),
            (w.survey.year if w.survey_id and w.survey.year is not None else -1),
            (w.survey.name if w.survey_id else ""),
            w.id,
        ),
        reverse=True
    )


    ctx["facet_waves"] = [
        {
            "wave": w,
            "count": int(facet_counter.get(w.id, 0)),
            "selected": (w.id in ctx["selected_wave_ids"]),
        }
        for w in facet_waves_sorted
    ]

    ctx["all_waves_facets"] = [
        {
            "wave": w,
            "count": int(facet_counter.get(w.id, 0)),
            "selected": (w.id in ctx["selected_wave_ids"]),
        }
        for w in all_waves
    ]


    ctx["facet_counts"] = {w.id: int(facet_counter.get(w.id, 0)) for w in facet_waves_set}


    # Rendern
    return render(request, "search/search.html", ctx)



# API-Endpunkt: "Kleine" Suche nach Fragen für den Frage-Picker im Page-Editor
#  Nur Fragen, keine Keywords, keine Facetten, nur Relevanz-Sortierung, Top 20
@require_GET
def search_questions_api(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": True, "results": []})

    wave_ids = []
    try:
        wave_ids = [int(x) for x in request.GET.getlist("waves") if x.strip().isdigit()]
    except Exception:
        wave_ids = []

    found, score_map = search_questions(
        q=q,
        wave_ids=wave_ids,
        include_keywords=False,
    )

    # API: immer nach Relevanz + Top 20
    found_sorted = sorted(
        found,
        key=lambda obj: score_map.get(obj.id, 0.0),
        reverse=True
    )[:20]

    results = [
        {
            "id": obj.id,
            "label": strip_pv_formatting(obj.questiontext)[:200],
        }
        for obj in found_sorted
    ]
    return JsonResponse({"ok": True, "results": results})
