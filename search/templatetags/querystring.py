from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def url_with(context, **updates):
    """
    Baut einen Querystring aus request.GET und überschreibt/entfernt Keys.
    Beispiel: {% url 'search' %}{% url_with type='variables' page=None %}
    """
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for k, v in updates.items():
        if v is None:
            params.pop(k, None)
        elif isinstance(v, (list, tuple)):
            params.setlist(k, [str(x) for x in v])
        else:
            params[k] = v
    qs = params.urlencode()
    return ("?" + qs) if qs else ""
