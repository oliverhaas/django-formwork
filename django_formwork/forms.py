"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` automatically apply
DaisyUI CSS classes to all widgets, and inject error-state classes
(e.g. ``input-error``) when fields have validation errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import Form, ModelForm
from django.forms.boundfield import BoundField

if TYPE_CHECKING:
    from django.forms import Widget

from django_formwork.widgets import _add_css_class, _get_error_class, apply_daisy_classes


class FormworkBoundField(BoundField):
    """BoundField that adds DaisyUI error classes during rendering.

    When a field has validation errors, the appropriate DaisyUI error
    modifier (e.g. ``input-error``, ``select-error``) is added to the
    widget's rendered attributes.
    """

    template_name = "formwork/field.html"

    def build_widget_attrs(
        self,
        attrs: dict[str, Any],
        widget: Widget | None = None,
    ) -> dict[str, Any]:
        attrs = super().build_widget_attrs(attrs, widget)
        if self.errors:
            w = widget or self.field.widget
            error_class = _get_error_class(w)
            if error_class:
                _add_css_class(attrs, error_class)
        return attrs


class FormworkForm(Form):
    """Form base class with DaisyUI styling.

    Usage::

        class ContactForm(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            message = forms.CharField(widget=forms.Textarea)
    """

    template_name = "formwork/form.html"
    template_name_div = "formwork/form.html"
    bound_field_class = FormworkBoundField

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        apply_daisy_classes(self)


class FormworkModelForm(ModelForm):
    """ModelForm base class with DaisyUI styling."""

    template_name = "formwork/form.html"
    template_name_div = "formwork/form.html"
    bound_field_class = FormworkBoundField

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        apply_daisy_classes(self)
