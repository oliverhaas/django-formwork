"""Custom form renderer that uses formwork's DaisyUI-styled templates.

Set ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in your Django
settings to make **all** forms render with DaisyUI styling automatically,
without needing to extend :class:`~django_formwork.forms.FormworkForm`.

Django admin is unaffected because admin templates render fields
individually — they never call ``{{ form }}`` or ``as_field_group()``.
"""

from __future__ import annotations

from django.forms.renderers import DjangoTemplates


class FormworkRenderer(DjangoTemplates):
    """Form renderer that uses formwork templates for all forms.

    Overrides both ``form_template_name`` (used by ``{{ form }}``) and
    ``field_template_name`` (used by ``{{ field.as_field_group }}``).
    """

    form_template_name = "django/forms/formwork.html"
    field_template_name = "django/forms/formwork_field.html"
