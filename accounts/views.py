from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse


def loginpage(request):
    #  eingeloggt? → direkt zur Suche
    if request.user.is_authenticated:
        return redirect("search:search")
    
    if request.session.pop("slc_session_expired", False):
        messages.info(request, "Deine Sitzung ist abgelaufen. Bitte logge dich erneut ein.")


    # next-Parameter aus Querystring oder POST übernehmen
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    # Falls next auf die Logout-URL zeigt wird auf die Startseite umgeleitet
    logout_url = reverse("accounts:logout")
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
    

def logout_view(request):
    logout(request)
    messages.success(request, "Du wurdest erfolgreich abgemeldet.")
    return redirect("login")