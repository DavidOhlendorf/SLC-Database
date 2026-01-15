# pages/services/pv_builder.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class PVContext:
    page: object
    questions: list[object]
    vars_by_qid: dict[int, list[str]] | None = None
    active_wave: Optional[object] = None


def build_pv(ctx: PVContext) -> str:
    """
    Baut die Programmiervorlage (PV) als Markdown-freundlichen Plain-Text.
    """

    def s(val) -> str:
        # robust: None -> "", strings trimmen
        return (val or "").strip()

    def line(label: str, value) -> str:
        return f"{label}: {s(value)}\n"

    lines: list[str] = []
    lines.append("## Seitenangaben\n\n")

    p = ctx.page
    # Seitenfelder
    lines.append(line("pn", getattr(p, "pagename", "")))
    lines.append(line("hl", getattr(p, "page_heading", "")))
    lines.append(line("in", getattr(p, "introduction", "")))
    lines.append(line("tc", getattr(p, "transition_control", "")))
    lines.append(line("vc", getattr(p, "visibility_conditions", "")))
    lines.append(line("av", getattr(p, "answer_validations", "")))
    lines.append(line("kh", getattr(p, "correction_notes", "")))
    lines.append(line("fv", getattr(p, "forcing_variables", "")))
    lines.append(line("hv", getattr(p, "helper_variables", "")))
    lines.append(line("sv", getattr(p, "control_variables", "")))
    lines.append(line("fo", getattr(p, "formatting", "")))
    lines.append(line("tr", getattr(p, "transitions", "")))
    lines.append(line("hi", getattr(p, "page_programming_notes", "")))

    lines.append("\n---\n\n## Fragen auf der Seite\n")

    total = len(ctx.questions)
    for i, q in enumerate(ctx.questions, start=1):
        qid = getattr(q, "id", "")
        lines.append(f"\n### Q{qid} ({i}/{total})\n")

        lines.append(line("qt", getattr(q, "question_type", "")))
        lines.append(line("q", getattr(q, "questiontext", "")))
        lines.append(line("is", getattr(q, "instruction", "")))
        lines.append(line("st", getattr(q, "item_stem", "")))
        lines.append(line("mv", getattr(q, "missing_values", "")))
        lines.append(line("ka", getattr(q, "top_categories", "")))

        # Items (JSON)
        items = getattr(q, "items", None) or []
        lines.append("it:\n")

        if items:
            for item in items:
                item = item or {}

                parts = []

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
                    lines.append(f"- {':'.join(parts)}\n")


        # Antwortoptionen (JSON)
        aos = getattr(q, "answer_options", None) or []
        lines.append("ao:\n")

        if aos:
            for ao in aos:
                ao = ao or {}

                parts = []

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
                    lines.append(f"- {':'.join(parts)}\n")

    lines.append("\n---\n\n## Variablen auf der Seite\n")
    vars_by_qid = ctx.vars_by_qid or {}

    any_vars = False
    for q in ctx.questions:
        qid = getattr(q, "id", None)
        if qid is None:
            continue

        varnames = vars_by_qid.get(qid, [])
        if not varnames:
            continue

        any_vars = True

        lines.append(f"\n### Q{qid}:\n")
        for v in varnames:
            lines.append(f"- {v}\n")

    if not any_vars:
        lines.append("\n(keine Variablen gefunden)\n")

    return "".join(lines)
