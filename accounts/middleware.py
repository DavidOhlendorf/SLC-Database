# accounts/middleware.py

from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse


class LoginRequiredMiddleware:
    """
    Erzwingt Login für alle Views, die NICHT auf einer Whitelist stehen.

    Logik:
    - Authentifizierte Nutzer dürfen alle Seiten sehen
    - Unauthentifizierte Nutzer:
        * dürfen nur Whitelist-Views (z. B. login) + admin + debug + static/media in DEBUG
        * alles andere wird auf LOGIN_URL mit ?next=... umgeleitet.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # View-Namen, die ohne Login erreichbar sein dürfen
        self.whitelisted_view_names = {
            "login",                    # Login-Seite
            "password_reset",           # Formular "Passwort vergessen?"
            "password_reset_done",      # "Mail wurde verschickt"
            "password_reset_confirm",   # Link aus der Mail (Token-Seite)
            "password_reset_complete",  # "Passwort geändert"
            # hier können weitere View-Namen ergänzt werden
        }

    def __call__(self, request):
        path = request.path

        # 1) Admin und Debug-Toolbar nie blockieren
        if path.startswith("/admin/") or path.startswith("/__debug__/"):
            return self.get_response(request)

        # 2) Static/Media-Dateien im DEBUG-Modus durchlassen
        if settings.DEBUG:
            if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
                return self.get_response(request)
            if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
                return self.get_response(request)

        # 3) Wenn der Nutzer eingeloggt ist → nichts zu tun
        if request.user.is_authenticated:
            return self.get_response(request)

        # 4) Unangemeldet: Prüfen, ob die View auf der Whitelist steht
        try:
            match = resolve(path)
        except Exception:
            # Für nicht auflösbare Pfade (404 etc.): Anfrage normal weiterreichen
            return self.get_response(request)

        if match.url_name in self.whitelisted_view_names:
            return self.get_response(request)

        # 5) Ansonsten: auf Login umleiten, next=aktueller Pfad
        login_url = reverse(settings.LOGIN_URL)
        full_path = request.get_full_path()

        # Hat der Browser ein Session-Cookie, obwohl der User jetzt anonym ist?
        session_cookie_name = settings.SESSION_COOKIE_NAME
        has_session_cookie = session_cookie_name in request.COOKIES

        if has_session_cookie:
            # Flag in der (neuen) Session setzen:
            request.session["slc_session_expired"] = True

        return redirect(f"{login_url}?next={quote(full_path)}")

