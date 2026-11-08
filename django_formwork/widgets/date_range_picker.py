"""DateRangePicker and DateTimeRangePicker widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.forms.utils import to_current_timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import ngettext

from ._base import _ModuleScript, _plural_forms
from ._calendar import calendar_context, format_date

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence

# Attrs the template places itself. Data and htmx attrs go on the end input,
# which fires `change`; the rest go on the trigger, which takes focus.
_TEMPLATE_ATTRS = frozenset({"id", "class", "placeholder", "disabled", "required"})


def _days_text(count: int) -> str:
    return ngettext("%(count)s day", "%(count)s days", count)


class DateRangePicker(forms.MultiWidget):
    """A start and an end date in one control, picked in a two-month calendar and posted as ISO.

    ``format`` is how the control shows each date: a Django format setting name or a format string.
    """

    template_name = "formwork/widgets/date_range_picker.html"
    # MultiWidget counts a widget of hidden inputs as hidden, and a form then
    # renders it without its label, help text and errors.
    is_hidden = False
    use_fieldset = False
    with_time = False
    value_format = "%Y-%m-%d"
    default_format = "DATE_FORMAT"

    class Media:
        js = (_ModuleScript("formwork/widgets/date_range_picker.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None, *, format: str | None = None) -> None:  # noqa: A002
        self.format = format or self.default_format
        super().__init__([forms.HiddenInput(), forms.HiddenInput()], attrs)

    def decompress(self, value: object) -> list[object]:
        if not value:
            return [None, None]
        start, end = cast("Sequence[object]", value)
        return [start, end]

    def id_for_label(self, id_: str) -> str:  # noqa: ARG002
        # The trigger is a button, which `<label for>` cannot name; boundfield.py
        # points it at the label instead.
        return ""

    def use_required_attribute(self, initial: object) -> bool:  # noqa: ARG002
        # The inputs are hidden and the trigger is a button; the trigger gets aria-required.
        return False

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        start, end = (self._parse(subwidget["value"]) for subwidget in widget["subwidgets"])
        widget["start"] = start.strftime(self.value_format) if start else ""
        widget["end"] = end.strftime(self.value_format) if end else ""
        widget["with_time"] = self.with_time
        widget["calendar"] = calendar = calendar_context(months=2, value=self.format)
        widget["start_label"] = format_date(start, calendar["formats"]["value"])
        widget["end_label"] = format_date(end, calendar["formats"]["value"])
        widget["count_text"] = _plural_forms(_days_text)
        attrs = widget["attrs"]
        widget["disabled"] = bool(attrs.get("disabled"))
        rest = {key: val for key, val in attrs.items() if key not in _TEMPLATE_ATTRS}
        widget["input_attrs"] = {key: val for key, val in rest.items() if key.startswith(("data-", "hx-"))}
        widget["trigger_attrs"] = {key: val for key, val in rest.items() if key not in widget["input_attrs"]}
        return context

    def _parse(self, value: str | None) -> dt.date | None:
        """The day a subwidget's text names, or None: posted text that names none shows as empty."""
        try:
            return parse_date(value.strip()[:10]) if value else None
        except ValueError:
            return None


class DateTimeRangePicker(DateRangePicker):
    """A start and an end, each a calendar day and a time, posted as ``YYYY-MM-DDTHH:MM`` local time.

    Times start at 00:00 and 23:59 until the user changes them.
    """

    with_time = True
    value_format = "%Y-%m-%dT%H:%M"
    default_format = "DATETIME_FORMAT"

    def _parse(self, value: str | None) -> dt.datetime | None:
        # A model's aware datetime arrives as its str(); show it in the current time zone.
        try:
            parsed = parse_datetime(value.strip()) if value else None
        except ValueError:
            return None
        return to_current_timezone(parsed) if parsed else None
