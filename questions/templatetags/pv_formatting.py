"""Template filters for PV text formatting."""

from django import template

from questions.formatting import render_pv_formatting, strip_pv_formatting

register = template.Library()


@register.filter(name="pv_format")
def pv_format(value: object) -> str:
    return render_pv_formatting(value)


@register.filter(name="pv_plain")
def pv_plain(value: object) -> str:
    return strip_pv_formatting(value)
