"""DatePicker widget."""

from __future__ import annotations

import re
from typing import Any

from django import forms

from ._base import _ModuleScript

#: strftime code -> human placeholder token, for turning a date format into a
#: hint like ``DD/MM/YYYY``.  Unmapped codes are left as-is.
_PLACEHOLDER_TOKENS = {
    "Y": "YYYY",
    "y": "YY",
    "m": "MM",
    "d": "DD",
    "B": "Month",
    "b": "Mon",
    "A": "Weekday",
    "a": "Day",
}


class DatePicker(forms.DateInput):
    """Date input with an Alpine.js calendar dropdown.

    Renders a text input with a popover calendar panel for date selection.
    The submitted value is a date string in ``YYYY-MM-DD`` format.

    Usage::

        due_date = forms.DateField(widget=DatePicker)
    """

    template_name = "formwork/widgets/date_picker.html"
    input_type = "text"

    class Media:
        js = (_ModuleScript("formwork/widgets/date_picker.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None, *, format: str | None = None) -> None:  # noqa: A002
        resolved_format = format or "%Y-%m-%d"
        # Turn the strftime format into a human placeholder (%d/%m/%Y -> DD/MM/YYYY).
        placeholder = re.sub(r"%(.)", lambda m: _PLACEHOLDER_TOKENS.get(m[1], m[0]), resolved_format)
        defaults: dict[str, Any] = {"placeholder": placeholder}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults, format=resolved_format)

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        # The template hardcodes class="grow"; rendering attrs.class too
        # would emit a duplicate class attribute, so pass it separately.
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["extra_class"] = widget["attrs"].pop("class", "")
        return context
