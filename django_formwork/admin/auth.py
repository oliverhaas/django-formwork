"""The admins of ``django.contrib.auth``'s User and Group, registered as ``django.contrib.auth.admin`` registers them.

``autodiscover()`` imports this module when ``django.contrib.auth`` is installed. A custom user
model subclasses ``UserAdmin`` the same way it subclasses Django's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.utils import unquote
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.forms.models import ModelChoiceIterator
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.text import format_lazy
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_post_parameters

from django_formwork.admin.decorators import register
from django_formwork.admin.options import ModelAdmin
from django_formwork.admin.widgets import IS_POPUP_VAR, RADIO_ROW_CLASS
from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.widgets import PasswordInput

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from django.db import models
    from django.http import HttpRequest, HttpResponse
    from django.urls import URLPattern
    from django_stubs_ext import StrPromise

__all__ = [
    "AdminPasswordChangeForm",
    "AdminUserCreationForm",
    "GroupAdmin",
    "PermissionMultipleChoiceField",
    "ReadOnlyPasswordHashWidget",
    "UserAdmin",
    "UserChangeForm",
]


class ReadOnlyPasswordHashWidget(auth_forms.ReadOnlyPasswordHashWidget):
    """The hash's algorithm and parameters, and a link to the password page."""

    template_name = "formwork_admin/widgets/read_only_password_hash.html"

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        summary: list[tuple[str, str]] = []
        error = ""
        if value and not value.startswith(UNUSABLE_PASSWORD_PREFIX):
            try:
                summary = [(str(key), str(item)) for key, item in identify_hasher(value).safe_summary(value).items()]
            except ValueError:
                error = gettext("Invalid password format or unknown hashing algorithm.")
        context["summary"] = summary
        context["error"] = error
        return context


class _PermissionChoiceIterator(ModelChoiceIterator):
    # Groups the permissions under their model, which the label of each option leaves out.
    def __iter__(self) -> Iterator[Any]:
        groups: dict[str, list[tuple[Any, str]]] = {}
        for permission in self.queryset.select_related("content_type"):
            groups.setdefault(str(permission.content_type), []).append(self.choice(permission))
        yield from groups.items()


class PermissionMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Permissions grouped by model, each option named by the permission alone."""

    iterator = _PermissionChoiceIterator

    def label_from_instance(self, obj: Any) -> str:
        return obj.name


class _PasswordFieldsMixin:
    # Puts the reveal button on each of Django's password inputs.
    usable_password_help: Any = auth_forms.SetUnusablePasswordMixin.usable_password_help_text
    fields: dict[str, forms.Field]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            field = self.fields.get(name)
            if field is not None:
                field.widget = PasswordInput(attrs=field.widget.attrs)
        usable = self.fields.get("usable_password")
        if usable is not None:
            # Django's field is a RadioSelect with the classes of Django's admin CSS.
            usable.widget.attrs["class"] = RADIO_ROW_CLASS
            usable.help_text = self.usable_password_help


class AdminUserCreationForm(_PasswordFieldsMixin, auth_forms.AdminUserCreationForm, FormworkModelForm):
    """Django's form to add a user, with the password-based authentication switch."""


class AdminPasswordChangeForm(_PasswordFieldsMixin, auth_forms.AdminPasswordChangeForm, FormworkForm):
    """Django's form to set another user's password, or to turn password-based authentication off."""

    # Django's help text adds the warning as HTML; the warning is plain text here.
    usable_password_help = format_lazy(
        "{} {}",
        auth_forms.SetUnusablePasswordMixin.usable_password_help_text,
        _("If disabled, the current password for this user will be lost."),
    )


class UserChangeForm(auth_forms.UserChangeForm, FormworkModelForm):
    """Django's user form; the password shows its hash summary and links to the password page."""

    password = auth_forms.ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_("Raw passwords are not stored, so there is no way to see the user’s password."),
        widget=ReadOnlyPasswordHashWidget,
    )


def _permissions_field(db_field: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    queryset = kwargs.get("queryset", db_field.remote_field.model.objects)
    return {"form_class": PermissionMultipleChoiceField, **kwargs, "queryset": queryset.select_related("content_type")}


@register(Group)
class GroupAdmin(ModelAdmin):
    icon = "users"
    search_fields = ("name",)
    ordering = ("name",)
    filter_horizontal = ("permissions",)

    def formfield_for_manytomany(
        self, db_field: models.ManyToManyField[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        if db_field.name == "permissions":
            kwargs = _permissions_field(db_field, kwargs)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@register(User)
class UserAdmin(ModelAdmin):
    icon = "user"
    add_form_template = "formwork_admin/auth/user/add_form.html"
    change_user_password_template: str | None = None
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets: Sequence[tuple[str | StrPromise | None, dict[str, Any]]] = (
        (None, {"classes": ("wide",), "fields": ("username", "usable_password", "password1", "password2")}),
    )
    form = UserChangeForm
    add_form: type[forms.ModelForm[Any]] = AdminUserCreationForm
    change_password_form: type[auth_forms.AdminPasswordChangeForm] = AdminPasswordChangeForm
    list_display = ("username", "email", "first_name", "last_name", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    filter_horizontal = ("groups", "user_permissions")

    def lookup_allowed(self, lookup: str, value: str, request: HttpRequest) -> bool:
        # A query on the hash would read it out one character at a time.
        return not lookup.startswith("password") and super().lookup_allowed(lookup, value, request)

    def get_fieldsets(self, request: HttpRequest, obj: models.Model | None = None) -> Any:
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(
        self, request: HttpRequest, obj: models.Model | None = None, change: bool = False, **kwargs: Any
    ) -> type[forms.ModelForm[Any]]:
        """The creation form for a new user."""
        defaults: dict[str, Any] = {}
        if obj is None:
            defaults["form"] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, change=change, **defaults)

    def formfield_for_manytomany(
        self, db_field: models.ManyToManyField[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        if db_field.name == "user_permissions":
            kwargs = _permissions_field(db_field, kwargs)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                "<id>/password/",
                self.admin_site.admin_view(self.user_change_password),
                name=f"{self.opts.app_label}_{self.opts.model_name}_password_change",
            ),
            *super().get_urls(),
        ]

    @method_decorator(sensitive_post_parameters())
    def add_view(
        self, request: HttpRequest, form_url: str = "", extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        # Whoever adds users could add a superuser, so adding takes the change permission too.
        if not self.has_change_permission(request):
            if self.has_add_permission(request) and settings.DEBUG:
                raise Http404(
                    'Your user does not have the "Change user" permission. In '
                    "order to add users, Django requires that your user "
                    'account have both the "Add user" and "Change user" '
                    "permissions set."
                )
            raise PermissionDenied
        username_field = self.opts.get_field(cast("Any", self.model).USERNAME_FIELD)
        context = {"auto_populated_fields": (), "username_help_text": username_field.help_text, **(extra_context or {})}
        return super().add_view(request, form_url, context)

    @method_decorator(sensitive_post_parameters())
    def user_change_password(self, request: HttpRequest, id: str, form_url: str = "") -> HttpResponse:  # noqa: A002 (Django's URL keyword)
        user: Any = self.get_object(request, unquote(id))
        if not self.has_change_permission(request, user):
            raise PermissionDenied
        if user is None:
            raise Http404(
                _("%(name)s object with primary key %(key)r does not exist.")
                % {"name": self.opts.verbose_name, "key": escape(id)}
            )
        change_url = reverse(self.url_name("change"), args=(user.pk,))
        if request.method == "POST":
            form: Any = self.change_password_form(user, request.POST)
            if form.is_valid():
                # Turning password-based authentication off takes the button that says so.
                if not (form.cleaned_data["set_usable_password"] or "unset-password" in request.POST):
                    messages.error(request, gettext("Conflicting form data submitted. Please try again."))
                    return HttpResponseRedirect(request.get_full_path())
                user = form.save()
                self.log_change(request, user, self.construct_change_message(request, form, []))
                if user.has_usable_password():
                    messages.success(request, gettext("Password changed successfully."))
                else:
                    messages.success(request, gettext("Password-based authentication was disabled."))
                update_session_auth_hash(request, form.user)
                return HttpResponseRedirect(change_url)
        else:
            form = self.change_password_form(user)

        title = _("Change password: %s") if user.has_usable_password() else _("Set password: %s")
        context = self.page_context(
            request,
            title=title % user.get_username(),
            form_url=form_url,
            form=form,
            original=user,
            change_url=change_url,
            media=self.media + form.media,
            is_popup=IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            is_popup_var=IS_POPUP_VAR,
        )
        return self.render(
            request, self.change_user_password_template or "formwork_admin/auth/user/change_password.html", context
        )

    def response_add(self, request: HttpRequest, obj: models.Model, post_url_continue: str | None = None) -> Any:
        """Open the new user's change page, so the rest of their details follow; "Save and add another" stays."""
        if "_addanother" not in request.POST:
            post = request.POST.copy()
            post["_continue"] = "1"
            request.POST = post  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
        return super().response_add(request, obj, post_url_continue)
