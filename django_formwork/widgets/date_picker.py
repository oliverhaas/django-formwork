"""DatePicker widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _ModuleScript


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
        defaults: dict[str, Any] = {"placeholder": "YYYY-MM-DD"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults, format=format or "%Y-%m-%d")
