"""Form renderer for formwork's Jinja2 templates; it loads any other template through ``TEMPLATES``.

An app listed before ``django_formwork`` overrides a template with one at the same path in its ``jinja2/``.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import django.forms
import jinja2
from django.core.signals import setting_changed
from django.forms.renderers import TemplatesSetting
from django.template import TemplateDoesNotExist, defaultfilters
from django.template.backends.jinja2 import Jinja2
from django.utils.formats import localize
from django.utils.timezone import template_localtime  # type: ignore[attr-defined]  # ty: ignore[missing-module-member]  (missing from django-stubs)
from django.utils.translation import gettext, ngettext, npgettext, pgettext, pgettext_lazy

from django_formwork.boundfield import FormworkBoundField
from django_formwork.widgets.display import clamp

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from django.forms.renderers import BaseRenderer

__all__ = ["FormworkRenderer", "engine", "formwork_renderer"]

# A plain dict has no attributes besides these, so any other name a template reads from it is a key.
_DICT_ATTRIBUTES = frozenset(dir(dict))


class Environment(jinja2.Environment):
    """Jinja2's environment, with two shortcuts for the hundreds of small templates that a table renders.

    The output stays the same as Jinja's.
    """

    def getattr(self, obj: Any, attribute: str) -> Any:  # noqa: ANN401
        # Jinja tries the attribute first, and on a widget's dicts that raises an AttributeError for each key.
        if type(obj) is dict and attribute not in _DICT_ATTRIBUTES:
            try:
                return obj[attribute]
            except KeyError:
                return self.undefined(obj=obj, name=attribute)
        return super().getattr(obj, attribute)

    def make_globals(self, d: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
        # Jinja's ChainMap shows globals added after a template loads, and each render copies it twice, slowly.
        # The environment functions add every global before the first template loads.
        return {**self.globals, **(d or {})}


def _localize(value: Any) -> Any:  # noqa: ANN401
    """``value`` as Django templates print it: a date or number in the active locale, a datetime in local time."""
    return localize(template_localtime(value))


def environment(**options: Any) -> jinja2.Environment:
    env = Environment(**options)
    env.install_gettext_callables(  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]
        gettext,
        ngettext,
        newstyle=True,
        pgettext=pgettext,
        npgettext=npgettext,
    )
    env.filters.update(
        {
            "capfirst": defaultfilters.capfirst,
            "clamp": clamp,
            # Jinja's forceescape leaves a SafeString as it is.
            "force_escape": defaultfilters.force_escape,
            "localize": _localize,
            # Jinja's striptags also decodes entities and collapses whitespace.
            "striptags": defaultfilters.striptags,
        },
    )
    # makemessages reads only Django's template tags, so a text with a context comes from here.
    env.globals["help_toggle"] = {  # ty: ignore[invalid-assignment]
        "more": pgettext_lazy("help text toggle", "[more]"),
        "less": pgettext_lazy("help text toggle", "[less]"),
    }
    return env


@cache
def engine() -> Jinja2:
    """The Jinja2 backend that holds formwork's templates and Django's built-in widget templates."""
    return Jinja2(
        {
            "NAME": "formwork",
            "DIRS": [Path(django.forms.__file__).parent / "jinja2"],
            "APP_DIRS": True,
            "OPTIONS": {
                "environment": "django_formwork.renderers.environment",
                # Django's templates print nothing for a missing name, at any depth.
                "undefined": jinja2.ChainableUndefined,
                "extensions": ["jinja2.ext.i18n"],
            },
        },
    )


def _reset_engine(*, setting: str, **_: Any) -> None:
    if setting in {"INSTALLED_APPS", "DEBUG"}:
        engine.cache_clear()


setting_changed.connect(_reset_engine)


class FormworkRenderer(TemplatesSetting):
    """Render ``{{ form }}`` and ``as_field_group()`` with formwork templates.

    ``bound_field_class`` gives plain Django forms the ARIA attributes too.
    """

    form_template_name = "formwork/forms/div.html"
    field_template_name = "formwork/forms/field.html"
    bound_field_class = FormworkBoundField
    #: Formwork's template for each of Django's form layouts, also for a plain Django form.
    #: A ``<p>`` cannot hold a field group, so ``as_p()`` renders what ``as_div()`` does.
    layout_template_names: ClassVar[dict[str, str]] = {
        "django/forms/div.html": "formwork/forms/div.html",
        "django/forms/p.html": "formwork/forms/div.html",
        "django/forms/ul.html": "formwork/forms/ul.html",
        "django/forms/table.html": "formwork/forms/table.html",
    }

    def get_template(self, template_name: str) -> Any:  # noqa: ANN401
        template_name = self.layout_template_names.get(template_name, template_name)
        try:
            return engine().get_template(template_name)
        except TemplateDoesNotExist:
            return super().get_template(template_name)


@cache
def _default_renderer() -> FormworkRenderer:
    return FormworkRenderer()


def formwork_renderer(renderer: BaseRenderer | None) -> FormworkRenderer:
    """``renderer`` if it loads formwork's templates, else a ``FormworkRenderer``."""
    return renderer if isinstance(renderer, FormworkRenderer) else _default_renderer()
