"""Bound field with the ARIA attributes that ``formwork/forms/field.html`` relies on."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from django import forms
from django.forms.widgets import ChoiceWidget
from django.utils.choices import flatten_choices

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from django.forms import Widget
    from django.utils.safestring import SafeString

__all__ = ["FormworkBoundField"]


class FormworkBoundField(forms.BoundField):
    """Adds the ARIA attributes only the bound field can decide on."""

    @property
    def _inner_widget(self) -> Widget:
        widget = self.field.widget
        inner = getattr(widget, "widget", None)
        return inner if isinstance(inner, forms.Widget) else widget

    @property
    def widget_type(self) -> str:
        """The type of the widget, also when a wrapper such as an admin's relation buttons holds it in ``widget``."""
        return re.sub(r"widget$|input$", "", type(self._inner_widget).__name__.lower())

    @property
    def initial_checked(self) -> str:
        """The option values a checkbox or radio field had checked at first, as JSON, or ``""`` for other fields.

        After a failed save the page marks each changed option, and drops
        the mark when the user checks the first options again.
        """
        widget = self._inner_widget
        value = self.field.prepare_value(self.initial)
        if isinstance(widget, forms.CheckboxInput):
            return json.dumps(["on"] if widget.check_test(value) else [])
        if isinstance(widget, ChoiceWidget) and widget.input_type in {"checkbox", "radio"}:
            return json.dumps(widget.format_value(value))
        return ""

    @property
    def is_mandatory(self) -> bool:
        """Required by this save, or by a later step through the form's ``mandatory``."""
        return self.field.required or self.name in getattr(self.form, "mandatory", ())

    @property
    def label_links(self) -> str:
        """Links for the end of the label row, from a widget with a ``label_links(name, value, renderer)`` method.

        The admin's relation widget puts its Edit and Add links there.
        """
        links = getattr(self.field.widget, "label_links", None)
        if links is None or self.is_hidden:
            return ""
        return links(self.html_name, self.value(), renderer=self.form.renderer)

    @property
    def display_value(self) -> Any:  # noqa: ANN401
        """The value as text, as a table cell shows a field that posts nothing.

        The instance's ``get_<name>_display()``, else its value, else the labels of the chosen values."""
        instance = getattr(self.form, "instance", None)
        if instance is not None:
            display = getattr(instance, f"get_{self.name}_display", None)
            if callable(display):
                return display()
            value = getattr(instance, self.name, None)
            related = getattr(value, "all", None)  # related manager (M2M / reverse FK)
            if related is not None:
                return ", ".join(str(obj) for obj in related())
            return "" if value is None else str(value)
        choices: Iterator[tuple[Any, Any]] = flatten_choices(getattr(self.field, "choices", ()))
        labels = {str(key): label for key, label in choices}
        value = self.value()
        values = value if isinstance(value, list | tuple) else [value]
        return ", ".join(str(labels.get(str(item), item)) for item in values if item is not None)

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

    def as_control(self) -> SafeString:
        """The widget and its error tooltip, without the label, help text and fieldset of ``as_field_group()``."""
        return self.render("formwork/forms/control.html")

    def table_cell(self, caller: Callable[[FormworkBoundField], str]) -> str:
        """The HTML that ``caller`` renders for the field's table cell, from the column's ``cache_cells()``."""
        cache = getattr(self.field, "cell_cache", None)
        if cache is None:
            return caller(self)
        return cache.render(self, caller)

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
