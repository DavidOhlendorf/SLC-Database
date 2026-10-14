
# accounts/middleware.py

from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse


class LoginRequiredMiddleware:
    """
    Erzwingt Login für alle Views, die nicht auf der
    Whitelist stehen.

    Ausnahmen:
    - Login
    - Passwort setzen / zurücksetzen über gültigen Link
    - Passwort-Reset abgeschlossen
    - Django-Admin (eigene Zugriffskontrolle)
    - Debug und statische Dateien in der Entwicklung
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Ohne Anmeldung erreichbare Views
        self.whitelisted_view_names = {
            "login",
            "password_reset_confirm",
            "password_reset_complete",
        }

    def __call__(self, request):
        path = request.path

        # 1) Admin und Debug-Toolbar nicht blockieren
        # Django-Admin hat eine eigene Zugangskontrolle
        if path.startswith("/admin/"):
            return self.get_response(request)

        # Debug-Toolbar ausschließlich in der Entwicklung
        if settings.DEBUG and path.startswith("/__debug__/"):
            return self.get_response(request)

        # 2) Static/Media in DEBUG durchlassen
        if settings.DEBUG:
            if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
                return self.get_response(request)

            if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
                return self.get_response(request)

        # 3) Angemeldete Benutzer durchlassen
        if request.user.is_authenticated:
            return self.get_response(request)

        # 4) Anonyme Benutzer: View prüfen
        try:
            match = resolve(path)
        except Exception:
            # Nicht auflösbare Pfade normal weiterreichen
            return self.get_response(request)

        if match.url_name in self.whitelisted_view_names:
            return self.get_response(request)

        # 5) Sonst zur Anmeldung umleiten
        login_url = reverse(settings.LOGIN_URL)
        full_path = request.get_full_path()

        session_cookie_name = settings.SESSION_COOKIE_NAME
        has_session_cookie = session_cookie_name in request.COOKIES

        if has_session_cookie:
            request.session["slc_session_expired"] = True

        return redirect(
            f"{login_url}?next={quote(full_path)}"
        )
