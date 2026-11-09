"""The admin's private Jinja2 engine, which reads ``<app>/jinja2/`` of every installed app.

An app listed before ``django_formwork.admin`` overrides any ``formwork_admin/`` template.
"""

from __future__ import annotations

import json
from datetime import timedelta
from functools import cache
from typing import TYPE_CHECKING, Any

import jinja2
from django.core.signals import setting_changed
from django.template import TemplateDoesNotExist
from django.template.backends.jinja2 import Jinja2
from django.template.response import TemplateResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format, localize, number_format
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.timesince import timesince
from django.utils.translation import gettext, ngettext, npgettext, pgettext

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

    from django.http import HttpRequest

__all__ = ["AdminTemplateResponse", "engine", "environment"]


@cache
def engine() -> Jinja2:
    """The Jinja2 backend every admin page renders through."""
    return Jinja2(
        {
            "NAME": "formwork_admin",
            "DIRS": [],
            "APP_DIRS": True,
            "OPTIONS": {
                "environment": "django_formwork.admin.jinja.environment",
                "undefined": jinja2.StrictUndefined,
                "extensions": ["jinja2.ext.i18n", "jinja2.ext.do", "jinja2.ext.loopcontrols"],
                "trim_blocks": True,
                "lstrip_blocks": True,
            },
        },
    )


def _reset_engine(*, setting: str, **kwargs: Any) -> None:
    if setting in {"INSTALLED_APPS", "DEBUG"}:
        engine.cache_clear()


setting_changed.connect(_reset_engine)


def select_template(names: Sequence[str]) -> Any:
    """The first of ``names`` the engine finds."""
    backend = engine()
    for name in names:
        try:
            return backend.get_template(name)
        except TemplateDoesNotExist:
            continue
    raise TemplateDoesNotExist(", ".join(names))


class AdminTemplateResponse(TemplateResponse):
    """A ``TemplateResponse`` that renders through the admin's Jinja2 engine."""

    def resolve_template(self, template: Any) -> Any:
        if isinstance(template, str):
            return select_template([template])
        if isinstance(template, list | tuple):
            return select_template(template)
        return template


def url(viewname: str, *args: object, **kwargs: object) -> str:
    return reverse(viewname, args=args or None, kwargs=kwargs or None)


def icon(name: str, classes: str = "size-4") -> str:
    """A Lucide icon from the project's iconx CSS."""
    return format_html('<i class="icon icon-{} {}" aria-hidden="true"></i>', name, classes)


def number(value: Decimal | float | str) -> str:
    return number_format(value, force_grouping=True)


def datetime(value: Any, fmt: str = "DATETIME_FORMAT") -> str:
    if value is None:
        return ""
    if hasattr(value, "tzinfo"):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
    return date_format(value, fmt)


def ago(value: Any) -> str:
    """``value`` as "5 minutes ago", or "just now" within the last minute."""
    if timezone.now() - value < timedelta(minutes=1):
        return gettext("just now")
    return gettext("%(time)s ago") % {"time": timesince(value, depth=1)}


def tojson(value: object) -> str:
    """JSON for an HTML attribute; autoescaping quotes it."""
    return json.dumps(value, ensure_ascii=False, default=str)


def environment(**options: Any) -> jinja2.Environment:
    env = jinja2.Environment(**options)  # noqa: S701 (Django's backend sets autoescape)
    env.install_gettext_callables(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        gettext,
        ngettext,
        newstyle=True,
        pgettext=pgettext,
        npgettext=npgettext,
    )
    env.globals.update(  # ty: ignore[no-matching-overload]
        {
            "url": url,
            "static": static,
            "icon": icon,
            "number": number,
        },
    )
    env.filters.update(
        {
            "ago": ago,
            "capfirst": capfirst,
            "datetime": datetime,
            "localize": localize,
            "number": number,
            "timesince": timesince,
            "tojson_attr": tojson,
        },
    )
    return env


def render_context(request: HttpRequest, context: dict[str, Any]) -> dict[str, Any]:
    """``context`` as the engine's templates read it."""
    return {"request": request, **context}
