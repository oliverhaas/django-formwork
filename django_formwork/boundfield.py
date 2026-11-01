"""Bound field with the ARIA attributes that ``formwork/forms/field.html`` relies on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms

if TYPE_CHECKING:
    from django.forms import Widget

__all__ = ["FormworkBoundField"]


class FormworkBoundField(forms.BoundField):
    """Adds the ARIA attributes only the bound field can decide on."""

    @property
    def is_mandatory(self) -> bool:
        """Required by this save, or by a later step through the form's ``mandatory``."""
        return self.field.required or self.name in getattr(self.form, "mandatory", ())

    def build_widget_attrs(self, attrs: dict[str, str | bool], widget: Widget | None = None) -> dict[str, str | bool]:
        attrs = super().build_widget_attrs(attrs, widget)
        if self.is_mandatory and not self.field.disabled and self.form.use_required_attribute:
            attrs["aria-required"] = "true"
        widget = widget or self.field.widget
        # A control `<label for>` cannot target (a <summary> trigger) points back
        # at the label instead, but only where field.html renders one to point at.
        if self.label and self.auto_id and not self.use_fieldset and not widget.id_for_label(self.auto_id):
            # Label first, then the trigger, so the value is announced after the name.
            attrs["aria-labelledby"] = f"{self.auto_id}_label {self.auto_id}"
        return attrs
