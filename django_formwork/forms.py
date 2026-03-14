"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` use
:class:`~django_formwork.renderers.FormworkRenderer` so that both
``{{ form }}`` and ``{{ field.as_field_group }}`` produce DaisyUI-styled
markup.  All component styling is handled by the formwork CSS file via
``@apply`` — no widget attributes are mutated in Python.

Using ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in settings
is preferred over these base classes (it applies to *all* forms), but
these are useful when you want formwork styling on specific forms only.
"""

from __future__ import annotations

from django.forms import Form, ModelForm

from django_formwork.renderers import FormworkRenderer


class FormworkForm(Form):
    """Form base class with DaisyUI styling.

    Usage::

        class ContactForm(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            message = forms.CharField(widget=forms.Textarea)
    """

    default_renderer = FormworkRenderer


class FormworkModelForm(ModelForm):
    """ModelForm base class with DaisyUI styling."""

    default_renderer = FormworkRenderer
