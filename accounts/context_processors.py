from .models import UserPreferences


def user_theme(request):
    """
    Stellt das persönliche Farbschema in allen Templates bereit.

    Nicht eingeloggte Benutzer und Benutzer ohne gespeicherte
    Einstellungen erhalten das Standard-Theme.
    """

    default_theme = UserPreferences.Theme.DEEP_OCEAN

    if not request.user.is_authenticated:
        return {"user_theme": default_theme}

    theme = (
        UserPreferences.objects
        .filter(user=request.user)
        .values_list("theme", flat=True)
        .first()
    )

    return {
        "user_theme": theme or default_theme
    }