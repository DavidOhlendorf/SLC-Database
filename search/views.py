from django.shortcuts import render, redirect
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.postgres.search import TrigramSimilarity
from questions.models import Question, Construct, Keyword
from variables.models import Variable

ALLOWED_TYPES = {"all", "questions", "variables", "constructs"}
RESULTS_PER_PAGE = 20

def search_landing(request):
    return render(request, "search/landing.html")


def paginate_list(items, request, per_page=RESULTS_PER_PAGE):
    """
    Paginierung für bereits materialisierte Python-Listen.
    Das brauchen wir für die Fragen, weil wir sie nach Merge sortieren.
    """
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj


def paginate_queryset(qs, request, per_page=RESULTS_PER_PAGE):
    """
    Alte Variante: klassische Paginierung für QuerySets.
    Nutzen wir weiterhin für Variables und Constructs.
    """
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

    # =========================
    # QUESTIONS 
    # =========================
    if search_type in {"all", "questions"}:

        # --- 1. Kandidaten über Fragetext
        text_candidates_qs = (
            Question.objects
            .annotate(
                sim_text=TrigramSimilarity("questiontext", q),
            )
            .filter(
                Q(questiontext__icontains=q) |
                Q(sim_text__gt=0.2)
            )
            .values("id", "sim_text")
            .order_by("-sim_text")[:200]
        )
        text_candidates = list(text_candidates_qs)

        # Map: questionID -> score aus Fragetext
        text_score_map = {}
        for row in text_candidates:
            qid = row["id"]
            score = row["sim_text"] or 0
            text_score_map[qid] = score


        # --- 2. Kandidaten über Keywords (ohne sofort alle Fragen zu joinen)
        # Schritt 2a: relevante Keywords finden
        kw_candidates_qs = (
            Keyword.objects
            .annotate(
                sim_kw=TrigramSimilarity("name", q),
            )
            .filter(
                Q(name__icontains=q) |
                Q(sim_kw__gt=0.2)
            )
            .values("id", "sim_kw")
            .order_by("-sim_kw")[:200]
        )
        kw_candidates = list(kw_candidates_qs)

        kw_id_to_score = {}

        for row in kw_candidates:
            kwid = row["id"]
            score = row["sim_kw"] or 0
            kw_id_to_score[kwid] = score

        kw_ids = list(kw_id_to_score.keys())

        # Schritt 2b: Welche Fragen hängen an diesen Keyword-IDs?
        question_kw_links = (
            Question.objects
            .filter(keywords__in=kw_ids)
            .values("id", "keywords__id")
            .distinct()
        )

        kw_score_map_for_question = {}
        for row in question_kw_links:
            qid = row["id"]
            kwid = row["keywords__id"]
            score = kw_id_to_score.get(kwid, 0)
            if qid not in kw_score_map_for_question or score > kw_score_map_for_question[qid]:
                kw_score_map_for_question[qid] = score

        # --- 3. Scores mergen:
        # für jede Frage: nimm den besten Score aus Text-Similarity oder Keyword-Similarity
        final_score_map = {}

        for qid, score in text_score_map.items():
            final_score_map[qid] = score

        for qid, score in kw_score_map_for_question.items():
            if qid not in final_score_map or score > final_score_map[qid]:
                final_score_map[qid] = score


        # --- 4. Tatsächliche Question-Objekte holen und in sortierter Reihenfolge anordnen
        questions_found = list(
            Question.objects
            .filter(id__in=final_score_map.keys())
            .prefetch_related("waves")
            .distinct()
        )

        # Sortiere Ergebnis nach Relevanz
        questions_sorted = sorted(
            questions_found,
            key=lambda obj: final_score_map[obj.id],
            reverse=True
)

        # Score zum Debuggen mit anhängen (optional im Template anzeigen)
        for obj in questions_sorted:
            obj.relevance = final_score_map.get(obj.id, 0)

        if search_type == "all":
            ctx["questions"] = questions_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(questions_sorted, request)
            ctx["questions_page"] = page_obj
            ctx["questions"] = page_obj.object_list


    # =========================
    # VARIABLES
    # =========================
    if search_type in {"all", "variables"}:

        # --- 1. Kandidaten über varname / varlab -----------------
        # Wir holen (a) fuzzy-Score auf varlab
        # und (b) merken uns, ob varname hart getroffen hat.
        var_candidates_qs = (
            Variable.objects
            .annotate(
                sim_varlab=TrigramSimilarity("varlab", q),
            )
            .filter(
                Q(varname__icontains=q) |                     # exakter/teilweiser Stringmatch im technischen Namen
                Q(varlab__icontains=q) |                      # normaler Text-Suchtreffer im Label
                Q(sim_varlab__gt=0.2)                         # fuzzy im Label
            )
            .values(
                "id",
                "varname",
                "sim_varlab",
            )[:200]
        )
        var_candidates = list(var_candidates_qs)

        # Map: varID -> Score aus varlab/varname
        var_text_score_map = {}
        for row in var_candidates:
            vid = row["id"]
            sim_label = row["sim_varlab"] or 0

            # Basisscore: fuzzy varlab
            score = sim_label

            # Bonus falls der Suchstring im Variablennamen steckt
            # (das macht Treffer wie "dem123" extrem dominant)
            if row["varname"] and q.lower() in row["varname"].lower():
                score = max(score, 1.0)

            var_text_score_map[vid] = score


        # --- 2. Kandidaten über Keywords (indirekt via Question) ---
        # 2a. Relevante Keywords finden
        kw_candidates_qs_vars = (
            Keyword.objects
            .annotate(
                sim_kw=TrigramSimilarity("name", q),
            )
            .filter(
                Q(name__icontains=q) |
                Q(sim_kw__gt=0.2)
            )
            .values("id", "sim_kw")
            .order_by("-sim_kw")[:200]
        )
        kw_candidates_vars = list(kw_candidates_qs_vars)

        kw_id_to_score_vars = {}
        for row in kw_candidates_vars:
            kwid = row["id"]
            kw_score = row["sim_kw"] or 0
            kw_id_to_score_vars[kwid] = kw_score

        kw_ids_vars = list(kw_id_to_score_vars.keys())

        # 2b. Welche Variablen hängen an Fragen, die diese Keywords haben?
        # Wir gehen: Variable -> question -> keywords
        var_kw_links = (
            Variable.objects
            .filter(question__keywords__in=kw_ids_vars)
            .values("id", "question__keywords__id")
            .distinct()
        )

        kw_score_map_for_var = {}
        for row in var_kw_links:
            vid = row["id"]
            kwid = row["question__keywords__id"]
            score = kw_id_to_score_vars.get(kwid, 0)
            if vid not in kw_score_map_for_var or score > kw_score_map_for_var[vid]:
                kw_score_map_for_var[vid] = score


        # --- 3. Scores mergen (max aus Texttreffer vs. Keywordtreffer) ---
        final_var_score_map = {}

        # zuerst Scores aus varname/varlab
        for vid, score in var_text_score_map.items():
            final_var_score_map[vid] = score

        # dann Keyword-Scores reinmergen, wenn höher
        for vid, score in kw_score_map_for_var.items():
            if vid not in final_var_score_map or score > final_var_score_map[vid]:
                final_var_score_map[vid] = score


        # Falls gar nichts gefunden wurde (kann passieren), leeres Handling
        found_var_ids = list(final_var_score_map.keys())

        variables_found = list(
            Variable.objects
            .filter(id__in=found_var_ids)
            .select_related("question")   # FK -> Question
            .prefetch_related("waves")    # M2M/ManyToMany zu waves
            .distinct()
        )

        # 4. Nach Relevanz sortieren (höchster Score zuerst)
        variables_sorted = sorted(
            variables_found,
            key=lambda obj: final_var_score_map.get(obj.id, 0),
            reverse=True
        )

        # Debug-Score anhängen (kannst du im Template ausgeben, wenn du willst)
        for obj in variables_sorted:
            obj.relevance = final_var_score_map.get(obj.id, 0)

        if search_type == "all":
            ctx["variables"] = variables_sorted[:ctx["TOP_N"]]
        else:
            page_obj = paginate_list(variables_sorted, request)
            ctx["variables_page"] = page_obj
            ctx["variables"] = page_obj.object_list
       

  
    # =========================
    # CONSTRUCTS
    # =========================
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
