from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm

from .models import UserPreferences


class CustomUserCreationForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        label="E-Mail-Adresse",
        help_text="Beim Speichern wird automatisch eine Einladungs-Mail zum Festlegen des Passworts verschickt."
    )

    class Meta:
        model = User
        fields = ("username", "email")

class InvitationPasswordResetForm(DjangoPasswordResetForm):
    """
    Passwort-Reset-Form für Einladungen:
    - Anders als die Standardform filtert sie NICHT nach has_usable_password().
    - Damit können auch an frisch angelegte User mit set_unusable_password()
      Einladungslinks verschickt werden.
    """

    def get_users(self, email):
        UserModel = get_user_model()
        # nur aktive Nutzer, aber NICHT nach has_usable_password() filtern
        return UserModel._default_manager.filter(
            email__iexact=email,
            is_active=True,
        )

class UserPreferencesForm(forms.ModelForm):
    """
    Formular für persönliche Anzeigeeinstellungen.
    Z.B  Auswahl des Farbschemas.
    """

    class Meta:
        model = UserPreferences
        fields = ["theme"]

        widgets = {
            "theme": forms.RadioSelect(
                attrs={"class": "form-check-input"}
            ),
        }