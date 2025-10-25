from django.shortcuts import render, redirect
from django.db.models import Q
from django.core.paginator import Paginator
from questions.models import Question, Construct
from variables.models import Variable


ALLOWED_TYPES = {"all", "questions", "variables", "constructs"}

RESULTS_PER_PAGE = 20

def search_landing(request):
    return render(request, "search/landing.html")

def paginate_queryset(qs, request, per_page=RESULTS_PER_PAGE):
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj


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
        "tabs": [ 
            ("all", "Alle"),
            ("questions", "Fragen"),
            ("variables", "Variablen"),
            ("constructs", "Konstrukte"),
        ],
    }

    # Questions
    if search_type in {"all", "questions"}:
        qs_questions = (
            Question.objects.filter(
                Q(questiontext__icontains=q) |
                Q(keywords__name__icontains=q)
            )
            .prefetch_related("waves")
            .distinct()
        )

        if search_type == "all":
            ctx["questions"] = qs_questions[:ctx["TOP_N"]]
        else:
            page_obj = paginate_queryset(qs_questions, request)
            ctx["questions_page"] = page_obj
            ctx["questions"] = page_obj.object_list 



        if search_type == "all":
            ctx["questions"] = qs_questions[:ctx["TOP_N"]]
        else:
            page_obj = paginate_queryset(qs_questions, request)
            ctx["questions_page"] = page_obj
            ctx["questions"] = page_obj.object_list 

    # Variables
    if search_type in {"all", "variables"}:
        qs_variables = (
            Variable.objects.filter(
                Q(varname__icontains=q) | Q(varlab__icontains=q)
            )
            .select_related("question")     
            .prefetch_related("waves")
            .distinct()
        )

        if search_type == "all":
            ctx["variables"] = qs_variables[:ctx["TOP_N"]]
        else:
            page_obj = paginate_queryset(qs_variables, request)
            ctx["variables_page"] = page_obj
            ctx["variables"] = page_obj.object_list

    # Constructs
    if search_type in {"all", "constructs"}:
        qs_constructs = (
            Construct.objects.filter(
                Q(level_1__icontains=q) |
                Q(level_2__icontains=q)
            )
            .distinct()
        )

        if search_type == "all":
            ctx["constructs"] = qs_constructs[:ctx["TOP_N"]]
        else:
            page_obj = paginate_queryset(qs_constructs, request)
            ctx["constructs_page"] = page_obj
            ctx["constructs"] = page_obj.object_list

    return render(request, "search/search.html", ctx)