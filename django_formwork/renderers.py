"""Form renderer that uses formwork's DaisyUI-styled templates.

Set ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in your Django
settings to make **all** forms render with DaisyUI styling automatically,
without needing to extend :class:`~django_formwork.forms.FormworkForm`.

The renderer loads templates through the project's ``TEMPLATES`` setting, so a
project overrides any formwork template from its own template directories.
This needs ``"django.forms"`` in ``INSTALLED_APPS`` (for Django's built-in
widget templates) and a ``DjangoTemplates`` backend that finds app templates
(``APP_DIRS=True`` or the ``app_directories`` loader).

Admin forms are unaffected: they render fields individually and never call
``{{ form }}`` or ``as_field_group()``, so the form and field-group wrappers
do not apply there. Formwork also shadows no built-in widget templates, which
would otherwise reach admin and third-party forms through the global
``FORM_RENDERER``; built-in widgets keep their stock rendering. Formwork's own
widgets are opt-in (see ``VISION.md``).
"""

from __future__ import annotations

from django.forms.renderers import TemplatesSetting

from django_formwork.boundfield import FormworkBoundField

__all__ = ["FormworkRenderer"]


class FormworkRenderer(TemplatesSetting):
    """Render ``{{ form }}`` and ``as_field_group()`` with formwork templates.

    ``bound_field_class`` gives plain Django forms the ARIA attributes too.
    """

    form_template_name = "formwork/forms/div.html"
    field_template_name = "formwork/forms/field.html"
    bound_field_class = FormworkBoundField
