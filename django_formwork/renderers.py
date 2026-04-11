"""Custom form renderers that use formwork's DaisyUI-styled templates.

Set ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in your Django
settings to make **all** forms render with DaisyUI styling automatically,
without needing to extend :class:`~django_formwork.forms.FormworkForm`.

For projects using Jinja2, use
``FORM_RENDERER = "django_formwork.FormworkJinja2Renderer"`` instead.

Django admin is unaffected because admin templates render fields
individually — they never call ``{{ form }}`` or ``as_field_group()``.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from django.forms.renderers import DjangoTemplates, Jinja2


class FormworkRenderer(DjangoTemplates):
    """Form renderer that uses formwork templates for all forms.

    Overrides both ``form_template_name`` (used by ``{{ form }}``) and
    ``field_template_name`` (used by ``{{ field.as_field_group }}``).
    """

    form_template_name = "django/forms/formwork.html"
    field_template_name = "django/forms/formwork_field.html"


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
    def engine(self) -> object:
        import django.forms.renderers as _fr
        from django.utils.html import escapejs

        # Include Django's built-in jinja2 widget templates directory so that
        # standard widget templates (e.g. django/forms/widgets/input.html) are
        # found even when APP_DIRS is True but the django package itself is not
        # in INSTALLED_APPS as an app with a jinja2/ dir.
        django_forms_jinja2 = Path(_fr.__file__).parent / self.backend.app_dirname

        return self.backend(
            {
                "APP_DIRS": True,
                "DIRS": [Path(__file__).parent / "jinja2", django_forms_jinja2],
                "NAME": "djangoformworkjinja2",
                "OPTIONS": {
                    "filters": {
                        "escapejs": escapejs,
                    },
                },
            },
        )
