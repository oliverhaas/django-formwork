"""System checks for the admin's settings and for each registered ``ModelAdmin``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.apps import apps
from django.conf import settings
from django.contrib.admin.utils import NotRelationField, label_for_field
from django.core import checks
from django.core.exceptions import FieldDoesNotExist

from django_formwork.admin.filters import build_filterset
from django_formwork.forms import FormworkModelForm

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig
    from django.db.models import ForeignObjectRel

    from django_formwork.admin.options import ModelAdmin


@checks.register(checks.Tags.admin)
def check_dependencies(app_configs: Sequence[AppConfig] | None, **kwargs: Any) -> list[checks.CheckMessage]:
    """The apps and middleware the admin's login and messages need."""
    errors: list[checks.CheckMessage] = []
    for app, hint_id in (
        ("django.contrib.contenttypes", "E401"),
        ("django.contrib.auth", "E405"),
        ("django.contrib.messages", "E406"),
    ):
        if not apps.is_installed(app):
            errors.append(
                checks.Error(
                    f"'{app}' must be in INSTALLED_APPS to use django_formwork.admin.", id=f"formwork_admin.{hint_id}"
                )
            )
    middleware = getattr(settings, "MIDDLEWARE", ())
    for path, hint_id in (
        ("django.contrib.auth.middleware.AuthenticationMiddleware", "E408"),
        ("django.contrib.messages.middleware.MessageMiddleware", "E409"),
        ("django.contrib.sessions.middleware.SessionMiddleware", "E410"),
    ):
        if not any(_is_subclass(entry, path) for entry in middleware):
            errors.append(
                checks.Error(
                    f"'{path}' must be in MIDDLEWARE to use django_formwork.admin.", id=f"formwork_admin.{hint_id}"
                )
            )
    return errors


def _is_subclass(entry: str, path: str) -> bool:
    from django.utils.module_loading import import_string

    try:
        return issubclass(import_string(entry), import_string(path))
    except ImportError:
        return entry == path


@checks.register(checks.Tags.admin)
def check_model_admins(app_configs: Sequence[AppConfig] | None, **kwargs: Any) -> list[checks.CheckMessage]:
    from django_formwork.admin.sites import _sites, get_site

    get_site("admin")
    errors: list[checks.CheckMessage] = []
    for admin_site in list(_sites.values()):
        for model_admin in admin_site._registry.values():
            errors.extend(check_model_admin(model_admin))
    return errors


# Django's inline classes, by dotted path: the module to import them from and formwork's module for the same name.
_DJANGO_INLINES = {
    "django.contrib.admin.options.InlineModelAdmin": ("django.contrib.admin.options", "django_formwork.admin.options"),
    "django.contrib.admin.options.StackedInline": ("django.contrib.admin", "django_formwork.admin"),
    "django.contrib.admin.options.TabularInline": ("django.contrib.admin", "django_formwork.admin"),
    **{
        f"django.contrib.contenttypes.admin.{name}": (
            "django.contrib.contenttypes.admin",
            "django_formwork.admin.contenttypes",
        )
        for name in ("GenericInlineModelAdmin", "GenericStackedInline", "GenericTabularInline")
    },
}


def _check_form(owner: type, option: str) -> list[checks.CheckMessage]:
    form = getattr(owner, option)
    if isinstance(form, type) and issubclass(form, FormworkModelForm):
        return []
    if isinstance(form, type):
        bases = [base.__name__ for base in form.__bases__ if base is not forms.ModelForm]
        declaration = f"class {form.__name__}({', '.join([*bases, 'FormworkModelForm'])})"
        hint = f"Declare it as '{declaration}', with FormworkModelForm from django_formwork.forms."
    else:
        hint = "Use a subclass of django_formwork.forms.FormworkModelForm."
    return [
        checks.Error(
            f"The value of '{option}' must inherit from 'FormworkModelForm'.",
            hint=hint,
            obj=owner,
            id="formwork_admin.E016",
        )
    ]


def _check_inline(model_admin: ModelAdmin, inline: Any) -> list[checks.CheckMessage]:
    from django_formwork.admin.options import InlineModelAdmin

    if isinstance(inline, type) and issubclass(inline, InlineModelAdmin):
        return _check_form(inline, "form")
    django_path = next(
        (
            path
            for klass in getattr(inline, "__mro__", ())
            if (path := f"{klass.__module__}.{klass.__qualname__}") in _DJANGO_INLINES
        ),
        None,
    )
    if django_path is None:
        hint = "Base it on TabularInline or StackedInline from django_formwork.admin."
    else:
        old_module, new_module = _DJANGO_INLINES[django_path]
        hint = f"Import {django_path.rpartition('.')[2]} from {new_module} instead of {old_module}."
    name = getattr(inline, "__qualname__", repr(inline))
    return [
        checks.Error(
            f"'{name}' must inherit from 'django_formwork.admin.options.InlineModelAdmin'.",
            hint=hint,
            obj=type(model_admin),
            id="formwork_admin.E104",
        )
    ]


def check_model_admin(model_admin: ModelAdmin) -> list[checks.CheckMessage]:
    """The options a typo breaks only when someone opens the page."""
    errors: list[checks.CheckMessage] = []
    opts = model_admin.model._meta
    name = type(model_admin).__qualname__
    errors.extend(_check_form(type(model_admin), "form"))
    if hasattr(model_admin, "add_form"):
        errors.extend(_check_form(type(model_admin), "add_form"))
    for inline in model_admin.inlines:
        errors.extend(_check_inline(model_admin, inline))
    for item in model_admin.list_display:
        try:
            label_for_field(item, model_admin.model, model_admin)  # type: ignore[call-overload]  # ty: ignore[no-matching-overload]
        except AttributeError:
            errors.append(
                checks.Error(
                    f"The value of 'list_display' refers to '{item}', which is not a callable, an attribute of '{name}', "
                    f"or an attribute or method on '{opts.label}'.",
                    obj=type(model_admin),
                    id="formwork_admin.E108",
                ),
            )
    links = model_admin.list_display_links or ()
    for item in model_admin.list_editable:
        if item not in model_admin.list_display:
            errors.append(
                checks.Error(
                    f"The value of 'list_editable' refers to '{item}', which is not contained in 'list_display'.",
                    obj=type(model_admin),
                    id="formwork_admin.E122",
                ),
            )
        elif item in links or (
            not links and model_admin.list_display_links is not None and list(model_admin.list_display)[:1] == [item]
        ):
            errors.append(
                checks.Error(
                    f"The value of 'list_editable' refers to '{item}', which is also a link to the change page.",
                    obj=type(model_admin),
                    id="formwork_admin.E124",
                ),
            )
    for item in (*model_admin.autocomplete_fields, *model_admin.raw_id_fields):
        try:
            field = opts.get_field(item)
        except FieldDoesNotExist:
            errors.append(
                checks.Error(
                    f"'{item}' is not a field of '{opts.label}'.", obj=type(model_admin), id="formwork_admin.E037"
                )
            )
            continue
        if not field.many_to_many and not field.many_to_one and not field.one_to_one:
            errors.append(
                checks.Error(
                    f"'{item}' must be a foreign key or a many-to-many field.",
                    obj=type(model_admin),
                    id="formwork_admin.E038",
                )
            )
            continue
        related_model = cast("ForeignObjectRel", field.remote_field).model
        related_admin = model_admin.admin_site.get_model_admin_or_none(related_model)
        if item in model_admin.autocomplete_fields and (related_admin is None or not related_admin.search_fields):
            errors.append(
                checks.Error(
                    f"'{item}' is in autocomplete_fields, so the admin of '{related_model._meta.label}' "
                    "must be registered and define search_fields.",
                    obj=type(model_admin),
                    id="formwork_admin.E040",
                ),
            )
    limit = model_admin.delete_confirmation_max_display
    if limit is not None and (not isinstance(limit, int) or limit < 0):
        errors.append(
            checks.Error(
                "The value of 'delete_confirmation_max_display' must be a non-negative integer or None.",
                obj=type(model_admin),
                id="formwork_admin.E041",
            ),
        )
    try:
        build_filterset(model_admin, model_admin.list_filter, model_admin.search_fields)
    except NotRelationField:
        msg = "list_filter names a field path that crosses a field without a relation."
        errors.append(checks.Error(msg, obj=type(model_admin), id="formwork_admin.E116"))
    except (TypeError, FieldDoesNotExist) as error:
        errors.append(checks.Error(str(error), obj=type(model_admin), id="formwork_admin.E116"))
    return errors
