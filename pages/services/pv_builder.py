# pages/services/pv_builder.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PVContext:
    page: object
    questions: list[object]
    vars_by_qid: dict[int, list[str]] | None = None
    active_wave: Optional[object] = None


def build_pv(ctx: PVContext) -> str:
    """
    Baut die Programmiervorlage (PV) als einfachen Plain-Text.

    Ausgabeprinzip:
    - pro Seite / Frage ein vollständiger Block
    - Seitenfelder werden bei mehreren Fragen pro Frage wiederholt
    - Variablen werden je Frage als vn: var1 / var2 / ... ausgegeben
    """

    def s(val) -> str:
        return (val or "").strip()

    def line(label: str, value) -> str:
        return f"{label}: {s(value)}\n"

    def qtype_label(q) -> str:
        qt_value = getattr(q, "question_type", "")
        qt_label = ""

        get_disp = getattr(q, "get_question_type_display", None)
        if callable(get_disp):
            qt_label = get_disp()

        if not qt_label:
            qt_label = qt_value

        if qt_value == "other":
            other_txt = s(getattr(q, "question_type_other", ""))
            if other_txt:
                qt_label = f"{qt_label}: {other_txt}"

        return qt_label

    def format_items(items) -> str:
        items = items or []
        item_lines: list[str] = []

        for item in items:
            item = item or {}
            parts: list[str] = []

            uid = item.get("uid")
            if uid:
                parts.append(str(uid))

            var = item.get("variable")
            if var:
                parts[-1] = f"{parts[-1]}({var})" if parts else f"({var})"

            lab = item.get("label")
            if lab:
                parts.append(str(lab))

            if parts:
                item_lines.append(":".join(parts))

        return "\n".join(item_lines)

    def format_answer_options(answer_options) -> str:
        answer_options = answer_options or []
        ao_lines: list[str] = []

        for ao in answer_options:
            ao = ao or {}
            parts: list[str] = []

            uid = ao.get("uid")
            if uid:
                parts.append(str(uid))

            var = ao.get("variable")
            if var:
                parts[-1] = f"{parts[-1]}({var})" if parts else f"({var})"

            val = ao.get("value")
            if val is not None and val != "":
                parts.append(str(val))

            lab = ao.get("label")
            if lab:
                parts.append(str(lab))

            if parts:
                ao_lines.append(":".join(parts))

        return "\n".join(ao_lines)

    p = ctx.page
    vars_by_qid = ctx.vars_by_qid or {}

    # Falls eine Seite ausnahmsweise keine Fragen hat, trotzdem einen Seitenblock ausgeben.
    questions = ctx.questions or [None]

    blocks: list[str] = []

    for q in questions:
        qid = getattr(q, "id", None) if q is not None else None
        varnames = vars_by_qid.get(qid, []) if qid is not None else []
        vn_value = " / ".join(varnames)

        lines: list[str] = []

        if qid is not None:
            lines.append(f"qID {qid}\n")
        else:
            lines.append("qID \n")

        lines.append("***\n")

        lines.append(line("pn", getattr(p, "pagename", "")))
        lines.append(line("tc", getattr(p, "transition_control", "")))
        lines.append(line("vn", vn_value))

        lines.append(line("qt", qtype_label(q) if q is not None else ""))

        lines.append(line("hl", getattr(p, "page_heading", "")))
        lines.append(line("in", getattr(p, "introduction", "")))

        lines.append(line("q", getattr(q, "questiontext", "") if q is not None else ""))
        lines.append(line("is", getattr(q, "instruction", "") if q is not None else ""))

        lines.append("it:\n")
        if q is not None:
            item_text = format_items(getattr(q, "items", None))
            if item_text:
                lines.append(f"{item_text}\n")

        lines.append(line("st", getattr(q, "item_stem", "") if q is not None else ""))

        lines.append("ao:\n")
        if q is not None:
            ao_text = format_answer_options(getattr(q, "answer_options", None))
            if ao_text:
                lines.append(f"{ao_text}\n")

        lines.append(line("mv", getattr(q, "missing_values", "") if q is not None else ""))
        lines.append(line("ka", getattr(q, "top_categories", "") if q is not None else ""))

        lines.append(line("vc", getattr(p, "visibility_conditions", "")))
        lines.append(line("av", getattr(p, "answer_validations", "")))
        lines.append(line("kh", getattr(p, "correction_notes", "")))
        lines.append(line("fv", getattr(p, "forcing_variables", "")))
        lines.append(line("hv", getattr(p, "helper_variables", "")))
        lines.append(line("fo", getattr(p, "formatting", "")))
        lines.append(line("tr", getattr(p, "transitions", "")))
        lines.append(line("hi", getattr(p, "page_programming_notes", "")))

        blocks.append("".join(lines).rstrip())

    return "\n\n---\n\n".join(blocks) + "\n"