from .models import UserPreferences
from .release_notes import CURRENT_RELEASE


def user_theme(request):
    """
    Stellt das persönliche Farbschema und bei Bedarf
    die aktuelle Release-Ankündigung bereit.
    """

    default_theme = UserPreferences.Theme.DEEP_OCEAN

    # Nicht angemeldete Benutzer
    if not request.user.is_authenticated:
        return {
            "user_theme": default_theme,
            "release_announcement": None,
        }

    # Persönliche Einstellungen laden
    preferences = (
        UserPreferences.objects
        .filter(user=request.user)
        .values("theme", "last_seen_release")
        .first()
    )

    theme = (
        preferences["theme"]
        if preferences
        else default_theme
    )

    last_seen_release = (
        preferences["last_seen_release"]
        if preferences
        else ""
    )

    # Prüfen, ob das aktuelle Release bereits bestätigt wurde
    show_release = (
        last_seen_release != CURRENT_RELEASE["version"]
    )

    return {
        "user_theme": theme or default_theme,
        "release_announcement": (
            CURRENT_RELEASE if show_release else None
        ),
    }