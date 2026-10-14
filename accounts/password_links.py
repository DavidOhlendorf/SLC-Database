# accounts/password_links.py

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def create_password_setup_link(request, user):
    """
    Erzeugt einen Passwort-Setzen-/Reset-Link für einen Benutzer.

    Verwendet Djangos integrierten PasswordResetTokenGenerator.

    Funktioniert sowohl für:
    - neue Benutzer mit unbenutzbarem Passwort (Einladung)
    - bestehende Benutzer mit Passwort (Reset)

    Der Link wird nicht gespeichert oder per E-Mail verschickt.
    """

    # Nur bereits gespeicherte Benutzer zulassen.
    if user.pk is None:
        raise ValueError("Der Benutzer muss zuerst gespeichert werden.")

    # Für deaktivierte Benutzer keine Links erzeugen.
    if not user.is_active:
        raise ValueError(
            "Für deaktivierte Benutzer kann kein Link erzeugt werden."
        )

    # Benutzer-ID für die URL kodieren.
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    # Django-Token erzeugen.
    token = default_token_generator.make_token(user)

    # Relative URL zur bestehenden Passwortvergabe.
    path = reverse(
        "accounts:password_reset_confirm",
        kwargs={
            "uidb64": uid,
            "token": token,
        },
    )

    # Host über Djangos ALLOWED_HOSTS-Prüfung ermitteln.
    host = request.get_host()

    # In Produktion ausschließlich HTTPS-Links erzeugen.
    # In der lokalen Entwicklung auch HTTP ermöglichen.
    if settings.DEBUG:
        scheme = "https" if request.is_secure() else "http"
    else:
        scheme = "https"

    return f"{scheme}://{host}{path}"