# accounts/admin.py

from django.contrib import admin, messages
from django.contrib.auth.admin import (
    GroupAdmin as BaseGroupAdmin,
    UserAdmin as BaseUserAdmin,
)
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.cache import add_never_cache_headers

from .forms import CustomUserCreationForm
from .password_links import create_password_setup_link


class RestrictedGroupAdmin(BaseGroupAdmin):
    """Gruppen und ihre Berechtigungen verwalten nur Superuser."""

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class CustomUserAdmin(BaseUserAdmin):
    """Einladungen und Passwort-Resets über kopierbare Links im Admin."""

    add_form = CustomUserCreationForm
    form = UserChangeForm

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email"),
        }),
    )

    @staticmethod
    def _is_protected(user):
        return user is not None and (user.is_staff or user.is_superuser)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser and self._is_protected(obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser and self._is_protected(obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)

        if not request.user.is_superuser:
            actions.pop("delete_selected", None)

        return actions

    
    def _may_generate_password_link(self, request, user):
        """
        Administratoren dürfen Passwort-Links für alle
        Benutzer außer Superuser erzeugen.
        """
        if user is None:
            return False

        if not request.user.has_perm("auth.change_user"):
            return False

        if user.is_superuser and not request.user.is_superuser:
            return False

        return True

    def render_change_form(
        self, request, context, add=False,
        change=False, form_url="", obj=None
    ):
        context["can_generate_password_link"] = (
            bool(change and obj and obj.is_active)
            and self._may_generate_password_link(request, obj)
        )

        return super().render_change_form(
            request, context,
            add=add, change=change,
            form_url=form_url, obj=obj
        )


    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        if request.user.is_superuser:
            return super().get_fieldsets(request, obj)
        return (
            (None, {"fields": ("username",)}),
            ("Persönliche Angaben", {
                "fields": ("first_name", "last_name", "email"),
            }),
            ("Status und Editorrechte", {
                "fields": ("is_active", "groups", "user_permissions"),
            }),
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            editor_permissions = Permission.objects.filter(
                content_type__app_label="accounts",
                content_type__model="slcsettings",
                codename="can_edit_slc",
            )
            if db_field.name == "user_permissions":
                kwargs["queryset"] = editor_permissions
            elif db_field.name == "groups":
                # Nur Gruppen ohne andere (insbesondere administrative) Rechte.
                other_permissions = Permission.objects.exclude(
                    pk__in=editor_permissions.values("pk")
                )
                kwargs["queryset"] = Group.objects.exclude(
                    permissions__in=other_permissions
                ).distinct()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def user_change_password(self, request, id, form_url=""):
        # Die direkte Vergabe eines neuen Passworts ist ein Superuser-Fallback.
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.set_unusable_password()
            if not request.user.is_superuser:
                obj.is_staff = False
                obj.is_superuser = False
        super().save_model(request, obj, form, change)

    def get_urls(self):
        own_urls = [
            path(
                "<int:user_id>/password-link/",
                self.admin_site.admin_view(self.password_link_view),
                name="auth_user_password_link",
            ),
        ]
        return own_urls + super().get_urls()

    def _password_link_response(self, request, user, *, is_invitation):
        link = create_password_setup_link(request, user)
        username = user.get_username()

        if is_invitation:
            title = "Einladungslink erzeugt"
            mail_subject = "Einladung zur SLC-Datenbank"
            mail_body = (
                "Guten Tag,\n\n"
                "für Sie wurde ein Benutzerkonto in der SLC-Datenbank eingerichtet.\n\n"
                f"Benutzername: {username}\n\n"
                "Bitte öffnen Sie den folgenden Link, um Ihr Passwort festzulegen:\n\n"
                f"{link}\n\n"
                "Der Link ist 24 Stunden gültig.\n\n"
                "Viele Grüße\nIhr SLC-Datenbank-Team"
            )
        else:
            title = "Passwort-Reset-Link erzeugt"
            mail_subject = "Passwort für die SLC-Datenbank zurücksetzen"
            mail_body = (
                "Guten Tag,\n\n"
                "für Ihr Benutzerkonto in der SLC-Datenbank kann ein neues Passwort festgelegt werden.\n\n"
                f"Benutzername: {username}\n\n"
                "Bitte öffnen Sie dazu folgenden Link:\n\n"
                f"{link}\n\n"
                "Der Link ist 24 Stunden gültig.\n\n"
                "Viele Grüße\nIhr SLC-Datenbank-Team"
            )

        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "original": user,
            "user_obj": user,
            "password_link": link,
            "mail_subject": mail_subject,
            "mail_body": mail_body,
            "change_url": reverse("admin:auth_user_change", args=[user.pk]),
        }
        request.current_app = self.admin_site.name
        response = TemplateResponse(
            request,
            "admin/auth/user/password_link_result.html",
            context,
        )
        add_never_cache_headers(response)
        response["Referrer-Policy"] = "same-origin"
        return response

    def response_add(self, request, obj, post_url_continue=None):
        if not obj.is_active:
            self.message_user(
                request,
                "Der Benutzer wurde angelegt, ist aber inaktiv. "
                "Ein Einladungslink kann erst nach der Aktivierung erstellt werden.",
                level=messages.WARNING,
            )
            return super().response_add(request, obj, post_url_continue)

        self.log_change(request, obj, "Einladungslink erzeugt (ohne Token).")
        return self._password_link_response(request, obj, is_invitation=True)

    def password_link_view(self, request, user_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        user = self.get_object(request, str(user_id))
        if user is None:
            raise Http404("Benutzer nicht gefunden.")
        if not self._may_generate_password_link(request, user):
            raise PermissionDenied
        if not user.is_active:
            self.message_user(
                request,
                "Für deaktivierte Benutzer kann kein Passwort-Link erzeugt werden.",
                level=messages.ERROR,
            )
            return redirect("admin:auth_user_change", user.pk)

        self.log_change(request, user, "Passwort-Reset-Link erzeugt (ohne Token).")
        return self._password_link_response(request, user, is_invitation=False)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.unregister(Group)
admin.site.register(Group, RestrictedGroupAdmin)
