import re

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
    TrigramWordSimilarity,
)
from django.db.models import F, Prefetch, Q
from django.db.models.functions import Lower

from questions.models import Keyword
from variables.models import QuestionVariableWave, Variable
from variables.versioning import (
    VariableNameSchemaError,
    parse_variable_name,
    variable_family_sort_key,
)
from waves.models import Wave


# Sucht Variablen anhand von Variablenlabel, Variablenname und den Schlagwörtern der zugehörigen Fragen.
# Rückgabe:
#     matched_variables: konkrete Variablentreffer
#     score_map: Relevanzwert je Variablen-ID
def search_variables(q: str, wave_ids=None):

    q = (q or "").strip()
    if not q:
        return [], {}

    q_lower = q.lower()
    wave_ids = list(wave_ids or [])

    # Basis-QuerySet mit optionalem Wellenfilter
    base_qs_v = Variable.objects.all()

    if wave_ids:
        base_qs_v = base_qs_v.filter(waves__id__in=wave_ids)

    # 1. Volltextsuche im Variablenlabel
    ts_query_v = SearchQuery(
        q,
        config="german",
        search_type="websearch",
    )

    ts_rows_v = (
        base_qs_v
        .annotate(
            sv=SearchVector(
                "varlab",
                weight="A",
                config="german",
            )
        )
        .filter(sv=ts_query_v)
        .annotate(
            ts_rank=SearchRank(
                F("sv"),
                ts_query_v,
                normalization=32,
            )
        )
        .values("id", "ts_rank")
    )

    ts_map_v = {
        row["id"]: float(row["ts_rank"] or 0.0)
        for row in ts_rows_v
    }

    # 2. Trigram-Suche im Variablenlabel
    tg_rows_v = (
        base_qs_v
        .annotate(
            sim=TrigramWordSimilarity(
                q_lower,
                "varlab",
            )
        )
        .filter(sim__gt=0.6)
        .values("id", "sim")
    )

    tg_map_v = {
        row["id"]: float(row["sim"] or 0.0)
        for row in tg_rows_v
    }

    # 3. Wortgrenzen-Treffer im Variablenlabel
    word_boundary = rf"\m{re.escape(q_lower)}\M"

    wb_ids_v = set(
        base_qs_v
        .annotate(vl=Lower("varlab"))
        .filter(vl__iregex=word_boundary)
        .values_list("id", flat=True)
    )

    # 4. Präfixtreffer im Variablennamen
    vn_rows = (
        base_qs_v
        .annotate(vn=Lower("varname"))
        .filter(vn__startswith=q_lower)
        .values_list("id", "vn")
    )

    vn_map = {}

    for variable_id, varname in vn_rows:
        score = 1.05 if varname == q_lower else 1.0

        vn_map[variable_id] = max(
            vn_map.get(variable_id, 0.0),
            score,
        )

    # 5. Schlagwörter der zugehörigen Fragen
    kw_rows_v = (
        Keyword.objects
        .annotate(nl=Lower("name"))
        .annotate(
            sim=TrigramSimilarity(
                F("nl"),
                q_lower,
            )
        )
        .filter(
            Q(nl__istartswith=q_lower)
            | Q(sim__gt=0.6)
        )
        .values("id", "sim")[:15]
    )

    kw_id_to_score_v = {
        row["id"]: float(row["sim"] or 0.0)
        for row in kw_rows_v
    }

    if kw_id_to_score_v:
        var_kw_link_queryset = QuestionVariableWave.objects.filter(
            variable__in=base_qs_v,
            question__keywords__in=list(
                kw_id_to_score_v.keys()
            ),
        )

        # Bei aktivem Wellenfilter muss auch die konkrete
        # Frage-Variable-Welle-Verknüpfung zur ausgewählten Welle gehören.
        if wave_ids:
            var_kw_link_queryset = var_kw_link_queryset.filter(
                wave_id__in=wave_ids
            )

        var_kw_links = (
            var_kw_link_queryset
            .values(
                "variable_id",
                "question__keywords__id",
            )
            .distinct()
        )
    else:
        var_kw_links = []


    kw_map_v = {}

    for row in var_kw_links:
        variable_id = row["variable_id"]
        keyword_id = row["question__keywords__id"]
        keyword_score = kw_id_to_score_v.get(keyword_id, 0.0)

        kw_map_v[variable_id] = max(
            kw_map_v.get(variable_id, 0.0),
            keyword_score,
        )

    # 6. Gesamtwert je Variable
    candidate_ids_v = (
        set(ts_map_v)
        | set(tg_map_v)
        | wb_ids_v
        | set(vn_map)
        | set(kw_map_v)
    )

    final_var_score_map = {}

    for variable_id in candidate_ids_v:
        ts_score = ts_map_v.get(variable_id, 0.0)
        tg_score = tg_map_v.get(variable_id, 0.0) * 0.6
        wb_score = 0.95 if variable_id in wb_ids_v else 0.0
        vn_score = vn_map.get(variable_id, 0.0)

        text_score = max(
            ts_score,
            tg_score,
            wb_score,
            vn_score,
        )

        keyword_score = kw_map_v.get(variable_id, 0.0) * 0.8
        both_match = text_score > 0.0 and keyword_score > 0.0

        if text_score > 0.0:
            relevance = text_score + 0.15 * keyword_score
        else:
            relevance = 0.10 * keyword_score

        if both_match:
            relevance = min(1.2, relevance + 0.15)

        final_var_score_map[variable_id] = relevance

    matched_variables = list(
        base_qs_v
        .filter(id__in=final_var_score_map.keys())
        .only("id", "varname", "varlab")
        .distinct()
    )

    return matched_variables, final_var_score_map



# Gruppiert Variablen nach ihrem family_key.
# Variablen, die nicht dem Namensschema entsprechen, werden als einzelne Gruppen behandelt.
def build_variable_groups(matched_variables, score_map, wave_ids=None):

    matched_variables = list(matched_variables)
    wave_ids = list(wave_ids or [])

    if not matched_variables:
        return []

    matched_family_keys = set()
    matched_singleton_ids = set()

    for variable in matched_variables:
        try:
            parsed = parse_variable_name(variable.varname)
            matched_family_keys.add(parsed.family_key)
        except VariableNameSchemaError:
            matched_singleton_ids.add(variable.id)

    # Zunächst alle möglichen Mitglieder der gefundenen Familien laden.
    display_filter = Q(id__in=matched_singleton_ids)

    for family_key in matched_family_keys:
        display_filter |= (
            Q(varname__iexact=family_key)
            | Q(varname__istartswith=f"{family_key}_")
        )

    display_qs = Variable.objects.filter(display_filter)

    # Bei aktivem Wellenfilter nur Varianten anzeigen, die in mindestens
    # einer der gewählten Wellen vorkommen.
    if wave_ids:
        display_qs = display_qs.filter(waves__id__in=wave_ids)

    wave_order = Wave.objects.select_related("survey").order_by(
        F("survey__year").desc(nulls_last=True),
        F("start_date").desc(nulls_last=True),
        "cycle",
        "instrument",
        "id",
    )

    displayed_wave_order = wave_order

    if wave_ids:
        displayed_wave_order = displayed_wave_order.filter(id__in=wave_ids)

    displayed_variables = list(
        display_qs
        .only(
            "id",
            "varname",
            "varlab",
            "ver",
            "gen",
            "plausi",
            "flag",
            "reason_ver",
            "reason_gen",
            "reason_plausi",
            "reason_flag",
        )
        .prefetch_related(
            Prefetch(
                "waves",
                queryset=wave_order,
                to_attr="search_all_waves",
            ),
            Prefetch(
                "waves",
                queryset=displayed_wave_order,
                to_attr="search_display_waves",
            ),
        )
        .distinct()
    )

    grouped = {}

    for variable in displayed_variables:
        variable.relevance = score_map.get(variable.id, 0.0)

        try:
            parsed = parse_variable_name(variable.varname)

            group_key = ("family", parsed.family_key)
            family_name = parsed.family_key
            is_family = True

        except VariableNameSchemaError:
            # Ein nicht schema-konformer Name darf nicht allein deshalb
            # erscheinen, weil er zufällig mit einem Familiennamen beginnt.
            # Er bleibt nur sichtbar, wenn er selbst ein Suchtreffer war.
            if variable.id not in matched_singleton_ids:
                continue

            group_key = ("variable", variable.id)
            family_name = ""
            is_family = False

        if group_key not in grouped:
            grouped[group_key] = {
                "key": group_key,
                "name": family_name,
                "is_family": is_family,
                "variables": [],
                "relevance": 0.0,
                "sort_label": family_name.lower(),
            }

        grouped[group_key]["variables"].append(variable)

    result = []

    for group in grouped.values():
        # Der beste konkrete Suchtreffer steht oben.
        group["variables"].sort(
            key=lambda variable: (
                -score_map.get(variable.id, 0.0),
                variable_family_sort_key(variable.varname),
                variable.id,
            )
        )

        group["primary_variable"] = group["variables"][0]

        # Die übrigen Varianten werden fachlich sortiert:
        # Basis/Ableitungen, v1/Ableitungen, v2/Ableitungen usw.
        group["other_variables"] = sorted(
            group["variables"][1:],
            key=lambda variable: (
                variable_family_sort_key(variable.varname),
                variable.id,
            ),
        )

        group["relevance"] = max(
            (
                score_map.get(variable.id, 0.0)
                for variable in group["variables"]
            ),
            default=0.0,
        )

        if not group["sort_label"]:
            group["sort_label"] = (
                group["primary_variable"].varname
                or group["primary_variable"].varlab
                or ""
            ).lower()

        result.append(group)

    return result


# Sortiert die Variablen-Gruppen nach Relevanz oder alphabetisch.
def sort_variable_groups(variable_groups, sort):

    if sort == "alpha":
        return sorted(
            variable_groups,
            key=lambda group: (
                group["sort_label"],
                group["key"],
            ),
        )

    return sorted(
        variable_groups,
        key=lambda group: (
            -group["relevance"],
            group["sort_label"],
            group["key"],
        ),
    )