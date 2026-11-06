"""System checks for the settings that formwork's renderer and search endpoint need."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Tags, register
from django.urls import NoReverseMatch, reverse

from django_formwork.search import _registry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig


@register(Tags.urls)
def check_search_urls(app_configs: Sequence[AppConfig] | None, **kwargs: Any) -> list[Error]:  # noqa: ARG001
    """A form that declares a server search needs the endpoint routed."""
    if not _registry or not hasattr(settings, "ROOT_URLCONF"):
        return []
    try:
        reverse("formwork:search", kwargs={"key": "check"})
    except NoReverseMatch:
        return [
            Error(
                "Forms declare server searches, but no URL pattern routes django_formwork.urls.",
                hint='Add path("__formwork__/", include("django_formwork.urls")) to urlpatterns.',
                id="django_formwork.E001",
            ),
        ]
    return []


@register(Tags.templates)
def check_forms_app(app_configs: Sequence[AppConfig] | None, **kwargs: Any) -> list[Error]:  # noqa: ARG001
    """FormworkRenderer loads Django's widget templates through TEMPLATES."""
    if apps.is_installed("django.forms"):
        return []
    return [
        Error(
            "FormworkRenderer renders Django's widget templates through TEMPLATES, "
            "which finds them only when django.forms is an installed app.",
            hint='Add "django.forms" to INSTALLED_APPS.',
            id="django_formwork.E002",
        ),
    ]
