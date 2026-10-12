from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView


from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse, reverse_lazy

from .forms import UserPreferencesForm
from .models import UserPreferences




# ---------------------------------------------------------
# Login
# ---------------------------------------------------------
def loginpage(request):
    #  eingeloggt? → direkt zur Suche
    if request.user.is_authenticated:
        return redirect("search:search")
    
    if request.session.pop("slc_session_expired", False):
        messages.info(request, "Deine Sitzung ist abgelaufen. Bitte logge dich erneut ein.")


    # next-Parameter aus Querystring oder POST übernehmen
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    # Falls next auf die Logout-URL zeigt wird auf die Startseite umgeleitet
    logout_url = reverse("logout")
    if next_url.startswith(logout_url):
        next_url = ""


    if request.method == "POST":
        username = request.POST.get("user")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Sicherstellen, dass next_url "sicher" ist
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            else:
                # Fallback: Standard-Ziel (search)
                return redirect("search:search")
        else:
            messages.error(request, "Benutzername oder Passwort falsch")

    return render(request, "accounts/login.html", {"next": next_url})
    
# ---------------------------------------------------------
# Logout
# ---------------------------------------------------------
def logout_view(request):
    logout(request)
    messages.success(request, "Du wurdest erfolgreich abgemeldet.")
    return redirect("login")



# ---------------------------------------------------------
# Persönlicher Bereich
# ---------------------------------------------------------

class AccountOverviewView(LoginRequiredMixin, TemplateView):
    """
    Übersichtsseite des persönlichen Bereichs.
    """
    template_name = "accounts/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        preferences = UserPreferences.objects.filter(
            user=self.request.user
        ).first()

        context["current_theme"] = (
            preferences.get_theme_display()
            if preferences
            else UserPreferences.Theme.DEEP_OCEAN.label
        )

        return context


class AccountAppearanceView(LoginRequiredMixin, FormView):
    """
    Persönliche Darstellungseinstellungen.
    Aktuell: Auswahl und Speicherung des Farbschemas.
    """
    template_name = "accounts/appearance.html"
    form_class = UserPreferencesForm
    success_url = reverse_lazy("account_appearance")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        # Bestehende Einstellungen laden oder eine neue,
        # noch nicht gespeicherte Instanz vorbereiten.
        preferences = (
            UserPreferences.objects.filter(
                user=self.request.user
            ).first()
            or UserPreferences(user=self.request.user)
        )

        kwargs["instance"] = preferences

        return kwargs

    def form_valid(self, form):
        form.save()

        messages.success(
            self.request,
            "Farbschema erfolgreich gespeichert."
        )

        return super().form_valid(form)


class AccountSecurityView(LoginRequiredMixin, TemplateView):
    """
    Kontoinformationen und Zugang zur Passwortänderung.
    Benutzername und E-Mail-Adresse sind nur lesbar.
    """
    template_name = "accounts/security.html"