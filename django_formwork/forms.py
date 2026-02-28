"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` use formwork's
form template to render fields with DaisyUI-styled markup.  All
component styling (``input``, ``select``, ``textarea``, …) is handled
by the formwork CSS file via ``@apply`` — no widget attributes are
mutated in Python.
"""

from __future__ import annotations

from django.forms import Form, ModelForm


class FormworkForm(Form):
    """Form base class with DaisyUI styling.

    Usage::

        class ContactForm(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            message = forms.CharField(widget=forms.Textarea)
    """

    template_name = "django/forms/formwork.html"
    template_name_div = "django/forms/formwork.html"


class FormworkModelForm(ModelForm):
    """ModelForm base class with DaisyUI styling."""

    template_name = "django/forms/formwork.html"
    template_name_div = "django/forms/formwork.html"
