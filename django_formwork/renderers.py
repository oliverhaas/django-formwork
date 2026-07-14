"""Custom form renderers that use formwork's DaisyUI-styled templates.

Set ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in your Django
settings to make **all** forms render with DaisyUI styling automatically,
without needing to extend :class:`~django_formwork.forms.FormworkForm`.

For projects using Jinja2, use
``FORM_RENDERER = "django_formwork.FormworkJinja2Renderer"`` instead.

Django admin is unaffected because admin templates render fields
individually: they never call ``{{ form }}`` or ``as_field_group()``.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.forms.renderers import DjangoTemplates, Jinja2

if TYPE_CHECKING:
    from django.template.backends.base import BaseEngine

__all__ = [
    "FormworkJinja2Renderer",
    "FormworkRenderer",
    "formwork_jinja2_environment",
]


class FormworkRenderer(DjangoTemplates):
    """Form renderer that uses formwork templates for all forms.

    Overrides both ``form_template_name`` (used by ``{{ form }}``) and
    ``field_template_name`` (used by ``{{ field.as_field_group }}``).

    Adds formwork's template directory to DIRS so our widget template
    overrides (e.g. clearable_file_input.html) take precedence over
    Django's built-in versions.
    """

    form_template_name = "django/forms/formwork.html"
    field_template_name = "django/forms/formwork_field.html"

    @cached_property
    def engine(self) -> BaseEngine:
        import django.forms.renderers as _fr

        return self.backend(
            {
                "APP_DIRS": True,
                "DIRS": [
                    # Formwork templates first (widget overrides).
                    Path(__file__).parent / "templates",
                    # Django's built-in widget templates (attrs.html, etc.).
                    Path(_fr.__file__).parent / "templates",
                ],
                "NAME": "djangoformwork",
                # Lets widget templates ``{% load formwork %}`` even when the
                # app is absent from INSTALLED_APPS.
                "OPTIONS": {"libraries": {"formwork": "django_formwork.templatetags.formwork"}},
            },
        )


class FormworkJinja2Renderer(Jinja2):
    """Jinja2 form renderer that uses formwork templates for all forms.

    Mirrors :class:`FormworkRenderer` but uses Jinja2 templates from the
    ``jinja2/`` directory tree.  A custom Jinja2 environment is configured
    with the ``escapejs`` filter so widget templates can safely embed values
    inside JavaScript string literals.

    Usage::

        FORM_RENDERER = "django_formwork.FormworkJinja2Renderer"
    """

    form_template_name = "django/forms/formwork.html"
    field_template_name = "django/forms/formwork_field.html"

    @cached_property
    def engine(self) -> BaseEngine:
        import django.forms.renderers as _fr

        # Include Django's built-in jinja2 widget templates directory so that
        # standard widget templates (e.g. django/forms/widgets/input.html) are
        # found even when APP_DIRS is True but the django package itself is not
        # in INSTALLED_APPS as an app with a jinja2/ dir.
        app_dirname: str = self.backend.app_dirname  # type: ignore[assignment]
        django_forms_jinja2 = Path(_fr.__file__).parent / app_dirname

        return self.backend(
            {
                "APP_DIRS": True,
                "DIRS": [Path(__file__).parent / "jinja2", django_forms_jinja2],
                "NAME": "djangoformworkjinja2",
                "OPTIONS": {
                    "environment": "django_formwork.renderers.formwork_jinja2_environment",
                },
            },
        )


def formwork_jinja2_environment(**options: Any) -> Any:  # noqa: ANN401
    """Jinja2 environment factory that registers the ``escapejs`` and ``force_escape`` filters."""
    import jinja2
    from django.template.defaultfilters import force_escape
    from django.utils.html import escapejs

    env = jinja2.Environment(**options)  # noqa: S701 (Django's Jinja2 backend passes autoescape=True)
    env.filters["escapejs"] = escapejs
    # Django's force_escape, not Jinja2's |e/|forceescape: those honor
    # __html__ and are no-ops on mark_safe()-wrapped icon markup, which
    # must be HTML-escaped when embedded in data-icon attributes.
    env.filters["force_escape"] = force_escape
    return env
