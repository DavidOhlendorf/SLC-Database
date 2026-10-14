"""Formatting helpers for the text markers used in program templates."""

from collections.abc import Iterator

from django.utils.html import escape
from django.utils.safestring import mark_safe

_MARKERS = ("!!", "**", "++", "##")
_WRAPPERS = {
    "!!": ("<strong>", "</strong>"),
    "**": ("<em>", "</em>"),
    "++": ("<u>", "</u>"),
    "##": ('<span class="pv-hyperlink-text">', "</span>"),
}


def _marker_at(value: str, index: int) -> str | None:
    for marker in _MARKERS:
        if value.startswith(marker, index):
            return marker
    return None


def _is_supported_content(content: str) -> bool:
    """Only render simple, non-empty, single-line and non-nested sections."""
    if not content or "\n" in content or "\r" in content:
        return False
    return not any(marker in content for marker in _MARKERS)


def _segments(value: str) -> Iterator[tuple[str | None, str]]:
    """Yield plain or formatted segments without interpreting nested markers."""
    cursor = 0
    plain_start = 0

    while cursor < len(value):
        marker = _marker_at(value, cursor)
        if marker is None:
            cursor += 1
            continue

        if plain_start < cursor:
            yield None, value[plain_start:cursor]

        content_start = cursor + len(marker)
        closing_index = value.find(marker, content_start)

        if closing_index == -1:
            # An unclosed marker remains visible and parsing continues afterwards.
            yield None, marker
            cursor = content_start
            plain_start = cursor
            continue

        content = value[content_start:closing_index]
        segment_end = closing_index + len(marker)

        if _is_supported_content(content):
            yield marker, content
        else:
            yield None, value[cursor:segment_end]

        cursor = segment_end
        plain_start = cursor

    if plain_start < len(value):
        yield None, value[plain_start:]


def render_pv_formatting(value: object) -> str:
    """Render supported PV markers as a small, safe HTML subset."""
    text = "" if value is None else str(value)
    rendered: list[str] = []

    for marker, content in _segments(text):
        safe_content = str(escape(content))
        if marker is None:
            rendered.append(safe_content)
            continue

        opening_tag, closing_tag = _WRAPPERS[marker]
        rendered.append(f"{opening_tag}{safe_content}{closing_tag}")

    return mark_safe("".join(rendered))


def strip_pv_formatting(value: object) -> str:
    """Remove only valid PV marker pairs while leaving malformed syntax visible."""
    text = "" if value is None else str(value)
    return "".join(content for _marker, content in _segments(text))
