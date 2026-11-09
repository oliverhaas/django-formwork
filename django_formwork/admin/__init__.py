"""A Django admin on formwork forms, django-filter, htmx and Jinja2.

The names match ``django.contrib.admin``, so an ``admin.py`` mostly switches its import.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.admin.filters import (
        BooleanFieldListFilter,
        ChoicesFieldListFilter,
        DateFieldListFilter,
        EmptyFieldListFilter,
        FieldListFilter,
        ListFilter,
        RelatedFieldListFilter,
        RelatedOnlyFieldListFilter,
        SimpleListFilter,
    )

    from django_formwork.admin.decorators import action, display, register
    from django_formwork.admin.options import (
        HORIZONTAL,
        VERTICAL,
        ModelAdmin,
        StackedInline,
        TabularInline,
    )
    from django_formwork.admin.sites import AdminSite, site

_EXPORTS = {
    "AdminSite": "django_formwork.admin.sites",
    "BooleanFieldListFilter": "django.contrib.admin.filters",
    "ChoicesFieldListFilter": "django.contrib.admin.filters",
    "DateFieldListFilter": "django.contrib.admin.filters",
    "EmptyFieldListFilter": "django.contrib.admin.filters",
    "FieldListFilter": "django.contrib.admin.filters",
    "HORIZONTAL": "django_formwork.admin.options",
    "ListFilter": "django.contrib.admin.filters",
    "ModelAdmin": "django_formwork.admin.options",
    "RelatedFieldListFilter": "django.contrib.admin.filters",
    "RelatedOnlyFieldListFilter": "django.contrib.admin.filters",
    "SimpleListFilter": "django.contrib.admin.filters",
    "StackedInline": "django_formwork.admin.options",
    "TabularInline": "django_formwork.admin.options",
    "VERTICAL": "django_formwork.admin.options",
    "action": "django_formwork.admin.decorators",
    "display": "django_formwork.admin.decorators",
    "register": "django_formwork.admin.decorators",
    "site": "django_formwork.admin.sites",
}

__all__ = [
    "HORIZONTAL",
    "VERTICAL",
    "AdminSite",
    "BooleanFieldListFilter",
    "ChoicesFieldListFilter",
    "DateFieldListFilter",
    "EmptyFieldListFilter",
    "FieldListFilter",
    "ListFilter",
    "ModelAdmin",
    "RelatedFieldListFilter",
    "RelatedOnlyFieldListFilter",
    "SimpleListFilter",
    "StackedInline",
    "TabularInline",
    "action",
    "autodiscover",
    "display",
    "register",
    "site",
]


def autodiscover() -> None:
    """Import every installed app's admin module (``FORMWORK_ADMIN_AUTODISCOVER``, ``admin`` by default)."""
    from django.conf import settings
    from django.utils.module_loading import autodiscover_modules

    from django_formwork.admin.sites import site

    autodiscover_modules(getattr(settings, "FORMWORK_ADMIN_AUTODISCOVER", "admin"), register_to=site)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_EXPORTS})
