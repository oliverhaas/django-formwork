"""Custom form renderer that uses formwork's DaisyUI-styled template.

Set ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in your Django
settings to make **all** forms render with DaisyUI styling automatically,
without needing to extend :class:`~django_formwork.forms.FormworkForm`.

Django admin is unaffected because admin templates render fields
individually — they never call ``{{ form }}`` or ``form.render()``.
"""

from __future__ import annotations

from django.forms.renderers import DjangoTemplates


class FormworkRenderer(DjangoTemplates):
    """Form renderer that uses the formwork template for all forms."""

    form_template_name = "django/forms/formwork.html"
