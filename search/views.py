from django.shortcuts import render, redirect
from django.db.models import Q
from questions.models import Question, Construct
from variables.models import Variable


ALLOWED_TYPES = {"all", "questions", "variables", "constructs"}

def search_landing(request):
    return render(request, "search/landing.html")


def search(request):
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("search_landing")

    search_type = (request.GET.get("type") or "all").lower()
    if search_type not in ALLOWED_TYPES:
        search_type = "all"

    ctx = {
    "q": q,
    "type": search_type,
    "has_query": True,
    "TOP_N": 5,
    "tabs": [  # <- hier vorbereiten
        ("all", "Alle"),
        ("questions", "Fragen"),
        ("variables", "Variablen"),
        ("constructs", "Konstrukte"),
    ],
}

    # Questions
    if search_type in {"all", "questions"}:
        qs = (
            Question.objects.filter(
                Q(questiontext__icontains=q) |
                Q(keywords__name__icontains=q)
            )
            .prefetch_related("waves")
            .distinct()
        )
        ctx["questions"] = qs[:ctx["TOP_N"]] if search_type == "all" else qs

    # Variables
    if search_type in {"all", "variables"}:
        qs = (
            Variable.objects.filter(
                Q(varname__icontains=q) | Q(varlab__icontains=q)
            )
            .select_related("question")
            .prefetch_related("waves")
            .distinct()
        )
        ctx["variables"] = qs[:ctx["TOP_N"]] if search_type == "all" else qs

    # Constructs
    if search_type in {"all", "constructs"}:
        qs = (
            Construct.objects.filter(
                Q(level_1__icontains=q) | Q(level_2__icontains=q) 
            )
            .distinct()
        )
        ctx["constructs"] = qs[:ctx["TOP_N"]] if search_type == "all" else qs

    return render(request, "search/search.html", ctx)