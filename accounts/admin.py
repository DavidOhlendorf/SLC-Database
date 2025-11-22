# accounts/admin.py

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import User

from .forms import CustomUserCreationForm, InvitationPasswordResetForm


class CustomUserAdmin(BaseUserAdmin):
    """
    Erweiterter UserAdmin:
    - Beim Anlegen eines neuen Users:
      * Formular zeigt nur username + email
      * Es wird ein 'unusable password' gesetzt (Login nur per gesetztem Passwort)
      * Automatisch wird eine Passwort-Setzen-Mail (PasswordReset) an die E-Mail geschickt
    """

    add_form = CustomUserCreationForm
    form = UserChangeForm

    # Felder im "Neuen Benutzer anlegen"-Formular
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email"),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Vor dem Speichern merken, ob es ein neuer User ist
        is_new = obj.pk is None

        # Für neue User: Passwort absichtlich unbenutzbar machen
        if is_new:
            obj.set_unusable_password()

        # Normales Speichern über den Basis-Admin
        super().save_model(request, obj, form, change)

        # Nur beim ersten Anlegen und nur, wenn eine E-Mail existiert
        if is_new:
            if not obj.email:
                self.message_user(
                    request,
                    "User wurde angelegt, aber es wurde keine E-Mail-Adresse hinterlegt – "
                    "es wurde daher keine Einladungs-Mail verschickt.",
                    level=messages.WARNING,
                )
                return

            reset_form = InvitationPasswordResetForm({"email": obj.email})

            if reset_form.is_valid():
                try:
                    reset_form.save(
                        request=request,
                        use_https=request.is_secure(),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        email_template_name="accounts/password_invite_email.txt",  
                        subject_template_name="accounts/password_invite_subject.txt", 

                    ),

                    self.message_user(
                        request,
                        f"Einladungs-/Passwort-Setzen-Mail an {obj.email} vorbereitet ",
                        level=messages.SUCCESS,
                    )
                except Exception as e:
                    self.message_user(
                        request,
                        f"User wurde angelegt, aber beim Erzeugen der Passwort-Mail ist ein Fehler "
                        f"aufgetreten: {e}",
                        level=messages.ERROR,
                    )
            else:
                self.message_user(
                    request,
                    "User wurde angelegt, aber die E-Mail-Adresse war im PasswordResetForm nicht gültig – "
                    "es wurde keine Passwort-Mail verschickt.",
                    level=messages.WARNING,
                )


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
