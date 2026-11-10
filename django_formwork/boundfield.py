"""Bound field with the ARIA attributes that ``formwork/forms/field.html`` relies on."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django import forms

if TYPE_CHECKING:
    from django.forms import Widget

__all__ = ["FormworkBoundField"]


class FormworkBoundField(forms.BoundField):
    """Adds the ARIA attributes only the bound field can decide on."""

    @property
    def widget_type(self) -> str:
        """The type of the widget, also when a wrapper such as an admin's relation buttons holds it in ``widget``."""
        widget = self.field.widget
        inner = getattr(widget, "widget", None)
        if isinstance(inner, forms.Widget):
            widget = inner
        return re.sub(r"widget$|input$", "", type(widget).__name__.lower())

    @property
    def is_mandatory(self) -> bool:
        """Required by this save, or by a later step through the form's ``mandatory``."""
        return self.field.required or self.name in getattr(self.form, "mandatory", ())

    def value(self) -> object:
        """The posted value, or the initial one for a field a dirty-only post left out.

        Dirty-only validation counts an omitted field as unchanged, so a
        re-render shows what the field held instead of an empty value.
        """
        form = self.form
        if (
            form.is_bound
            and getattr(form, "_validate_dirty_only", False)
            and self.field.widget.value_omitted_from_data(form.data, form.files, self.html_name)
        ):
            return self.field.prepare_value(self.initial)
        return super().value()

    def build_widget_attrs(self, attrs: dict[str, str | bool], widget: Widget | None = None) -> dict[str, str | bool]:
        attrs = super().build_widget_attrs(attrs, widget)
        if self.is_mandatory and not self.field.disabled and self.form.use_required_attribute:
            attrs["aria-required"] = "true"
        widget = widget or self.field.widget
        # A control `<label for>` cannot target (a <summary> trigger) points back
        # at the label instead, but only where field.html renders one to point at.
        if self.label and self.auto_id and not self.use_fieldset and not widget.id_for_label(self.auto_id):
            # Label first, then the trigger, so the value is announced after the name.
            trigger = widget.attrs.get("id") or self.auto_id
            attrs["aria-labelledby"] = f"{self.auto_id}_label {trigger}"
        return attrs
