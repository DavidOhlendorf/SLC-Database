
from django import forms
from django.contrib.auth.models import User

from .models import UserPreferences


class CustomUserCreationForm(forms.ModelForm):
    """
    Benutzeranlage im Django-Admin.

    Neue Benutzer erhalten zunächst ein unbenutzbares Passwort.
    Der Einladungslink wird anschließend im Admin angezeigt.
    """

    email = forms.EmailField(
        required=True,
        label="E-Mail-Adresse",
        help_text=(
            "Nach dem Speichern wird ein Einladungslink erzeugt, "
            "der kopiert und manuell weitergegeben werden kann."
        ),
    )

    class Meta:
        model = User
        fields = ("username", "email")


class UserPreferencesForm(forms.ModelForm):
    """
    Formular für persönliche Anzeigeeinstellungen.
    """

    class Meta:
        model = UserPreferences
        fields = ["theme"]

        widgets = {
            "theme": forms.RadioSelect(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Standard-Theme immer zuerst anzeigen.
        self.fields["theme"].choices = sorted(
            self.fields["theme"].choices,
            key=lambda choice: (
                choice[0] != UserPreferences.Theme.DEEP_OCEAN
            ),
        )


class UserEmailForm(forms.ModelForm):
    """
    Änderung der eigenen E-Mail-Adresse.
    Erfordert zur Bestätigung das aktuelle Passwort.
    """

    email = forms.EmailField(
        label="E-Mail-Adresse",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
            }
        ),
    )

    current_password = forms.CharField(
        label="Aktuelles Passwort",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "current-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        # Keine mehrfach vergebenen E-Mail-Adressen
        if User.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Diese E-Mail-Adresse wird bereits verwendet."
            )

        return email

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]

        if not self.instance.check_password(password):
            raise forms.ValidationError(
                "Das aktuelle Passwort ist nicht korrekt."
            )

        return password
