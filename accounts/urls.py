from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import  logout_view, AccountOverviewView, AccountAppearanceView, AccountSecurityView

app_name = "accounts"


urlpatterns = [

    # --------------------------------------------------
    # Persönlicher Bereich
    # --------------------------------------------------

    path("", AccountOverviewView.as_view(), name="account_overview"),
    path("appearance/", AccountAppearanceView.as_view(), name="account_appearance"),
    path("security/", AccountSecurityView.as_view(), name="account_security"),

    # Logout
    path("logout/", logout_view, name="logout"),

    # --------------------------------------------------
    # Passwort ändern (angemeldeter Benutzer)
    # --------------------------------------------------

    path(
        "security/password/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change_form.html",
            success_url=reverse_lazy("accounts:password_change_done"),
        ),
        name="password_change",
    ),

    path(
        "security/password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),

    # --------------------------------------------------
    # Passwort festlegen / zurücksetzen
    # Über administrativ erzeugte Links
    # --------------------------------------------------

    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),

    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
