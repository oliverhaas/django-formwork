"""DatePicker widget."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from django import forms
from django.utils.dates import WEEKDAYS_ABBR
from django.utils.functional import lazy
from django.utils.translation import pgettext_lazy

from ._base import _ModuleScript

#: strftime code -> human placeholder token, for turning a date format into a
#: hint like ``DD/MM/YYYY``.  Unmapped codes are left as-is.
_PLACEHOLDER_TOKENS = {
    "Y": pgettext_lazy("date format placeholder", "YYYY"),
    "y": pgettext_lazy("date format placeholder", "YY"),
    "m": pgettext_lazy("date format placeholder", "MM"),
    "d": pgettext_lazy("date format placeholder", "DD"),
    "B": pgettext_lazy("date format placeholder", "Month"),
    "b": pgettext_lazy("date format placeholder: abbreviated month name", "Mon"),
    "A": pgettext_lazy("date format placeholder", "Weekday"),
    "a": pgettext_lazy("date format placeholder: abbreviated weekday name", "Day"),
}


def _format_placeholder(date_format: str) -> str:
    """Turn a strftime format into a human placeholder (``%d/%m/%Y`` -> ``DD/MM/YYYY``)."""
    return re.sub(r"%(.)", lambda m: str(_PLACEHOLDER_TOKENS.get(m[1], m[0])), date_format)


# The widget is built at import time, before a language is active.
_lazy_format_placeholder = lazy(_format_placeholder, str)


class DatePicker(forms.DateInput):
    """Text date input with a calendar dropdown, opt-in where the native ``DateInput`` does not fit.

    ``format`` sets how the input shows the date, both from the server and after a pick in the
    calendar. The widget reads that format back and hands the field an ISO date, so the field
    needs no matching ``input_formats``.
    """

    template_name = "formwork/widgets/date_picker.html"
    input_type = "text"

    class Media:
        js = (_ModuleScript("formwork/widgets/date_picker.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None, *, format: str | None = None) -> None:  # noqa: A002
        resolved_format = format or "%Y-%m-%d"
        defaults: dict[str, Any] = {"placeholder": _lazy_format_placeholder(resolved_format)}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults, format=resolved_format)

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        # The template hardcodes class="grow"; rendering attrs.class too
        # would emit a duplicate class attribute, so pass it separately.
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["extra_class"] = widget["attrs"].pop("class", "")
        # Sunday first, like Date.getDay() in the calendar grid.
        widget["weekdays"] = [WEEKDAYS_ABBR[day] for day in (6, 0, 1, 2, 3, 4, 5)]
        widget["iso_value"] = self._iso_value(value)
        widget["date_format"] = self.format
        return context

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:  # noqa: ANN401 (widget data)
        # The language's DATE_INPUT_FORMATS can lack ``format``, but every DateField reads ISO.
        value = super().value_from_datadict(data, files, name)
        return self._iso_value(value) or value

    def format_value(self, value: Any) -> str | None:  # noqa: ANN401 (widget data)
        # Bound data is ISO text from value_from_datadict; show it in ``format`` again.
        if isinstance(value, str) and (iso_value := self._iso_value(value)):
            value = dt.date.fromisoformat(iso_value)
        return super().format_value(value)

    def _iso_value(self, value: object) -> str:
        """The calendar parses only ``YYYY-MM-DD``, whatever ``format`` renders."""
        if isinstance(value, dt.date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            for date_format in (self.format or "%Y-%m-%d", "%Y-%m-%d"):
                try:
                    return dt.datetime.strptime(value, date_format).date().isoformat()  # noqa: DTZ007
                except ValueError:
                    continue
        return ""
