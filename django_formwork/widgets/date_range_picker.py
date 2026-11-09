"""DateRangePicker and DateTimeRangePicker widgets."""

from __future__ import annotations

import calendar
import datetime as dt
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.forms.utils import to_current_timezone
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.formats import get_format
from django.utils.translation import gettext, ngettext

from ._base import _ModuleScript, _plural_forms
from ._calendar import calendar_context, format_date

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    # A button under the calendar that picks a whole range: its label, start and end.
    Preset = tuple[str, dt.date, dt.date]

# Attrs the template places itself. Data and htmx attrs go on the end's hidden
# input, which fires `change`. The ARIA state goes on both inputs, the rest on the start.
_TEMPLATE_ATTRS = frozenset({"id", "class", "placeholder", "disabled", "required", "aria-labelledby"})
_PART_ATTRS = frozenset({"aria-describedby", "aria-invalid", "aria-required"})


def _days_text(count: int) -> str:
    return ngettext("%(count)s day", "%(count)s days", count)


def _today() -> dt.date:
    """Today in the current time zone, as Django's admin date filter takes it."""
    now = timezone.now()
    return (timezone.localtime(now) if timezone.is_aware(now) else now).date()


def _text_width(date_format: str, *placeholders: str) -> int:
    """The characters of the longest date ``date_format`` writes or placeholder, and one for the caret."""
    dates = (dt.datetime(2026, month, 28, 23, 59) for month in range(1, 13))  # noqa: DTZ001 (only formatted)
    return max(len(text) for text in (*(format_date(date, date_format) for date in dates), *placeholders)) + 1


class DateRangePicker(forms.MultiWidget):
    """A start and an end date, typed or picked in a two-month calendar, and posted as ISO.

    ``format`` is how the inputs show each date: a Django format setting name or a format string.
    ``presets`` adds buttons that pick a range: True for ``default_presets``, or a function of today.
    """

    template_name = "formwork/widgets/date_range_picker.html"
    # MultiWidget counts a widget of hidden inputs as hidden, and a form then
    # renders it without its label, help text and errors.
    is_hidden = False
    use_fieldset = False
    with_time = False
    value_format = "%Y-%m-%d"
    default_format = "DATE_FORMAT"
    # The settings whose strftime formats a typed date can also take.
    input_format_settings: tuple[str, ...] = ("DATE_INPUT_FORMATS",)

    class Media:
        js = (_ModuleScript("formwork/widgets/date_range_picker.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        format: str | None = None,  # noqa: A002
        presets: bool | Callable[[dt.date], Iterable[Preset]] = False,
    ) -> None:
        self.format = format or self.default_format
        self.presets = presets
        super().__init__([forms.HiddenInput(), forms.HiddenInput()], attrs)

    @staticmethod
    def default_presets(today: dt.date) -> list[Preset]:
        """Today, the past 7 days, this month and this year, as Django's admin date filter offers them."""
        last_day = calendar.monthrange(today.year, today.month)[1]
        return [
            (gettext("Today"), today, today),
            (gettext("Past 7 days"), today - dt.timedelta(days=6), today),
            (gettext("This month"), today.replace(day=1), today.replace(day=last_day)),
            (gettext("This year"), today.replace(month=1, day=1), today.replace(month=12, day=31)),
        ]

    def decompress(self, value: object) -> list[object]:
        if not value:
            return [None, None]
        start, end = cast("Sequence[object]", value)
        return [start, end]

    def id_for_label(self, id_: str) -> str:  # noqa: ARG002
        # Two inputs share the label: boundfield.py names their group with it.
        return ""

    def use_required_attribute(self, initial: object) -> bool:  # noqa: ARG002
        # A half-open range can be valid; the text inputs get aria-required.
        return False

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["with_time"] = self.with_time
        input_formats = dict.fromkeys(str(fmt) for setting in self.input_format_settings for fmt in get_format(setting))
        calendar = calendar_context(months=2, value=self.format, input_formats=list(input_formats))
        widget["calendar"] = calendar
        value_format = calendar["formats"]["value"]
        for part, subwidget in zip(("start", "end"), widget["subwidgets"], strict=True):
            text = subwidget["value"] or ""
            parsed = self._parse(text)
            # Text that names no day goes back as it came, next to the error it gets.
            widget[part] = parsed.strftime(self.value_format) if parsed else text
            widget[f"{part}_text"] = format_date(parsed, value_format) if parsed else text
        widget["start_placeholder"] = start_placeholder = gettext("Start date")
        widget["end_placeholder"] = end_placeholder = gettext("End date")
        widget["text_width"] = _text_width(value_format, start_placeholder, end_placeholder)
        widget["count_text"] = _plural_forms(_days_text)
        presets = self.default_presets if self.presets is True else self.presets
        widget["presets"] = (
            [
                {"label": label, "start": start.isoformat(), "end": end.isoformat()}
                for label, start, end in presets(_today())
            ]
            if callable(presets)
            else []
        )
        attrs = widget["attrs"]
        widget["disabled"] = bool(attrs.get("disabled"))
        # boundfield.py names the label and the control; the group takes the label.
        own_id = attrs.get("id")
        widget["labelledby"] = " ".join(
            token for token in str(attrs.get("aria-labelledby", "")).split() if token != own_id
        )
        rest = {key: val for key, val in attrs.items() if key not in _TEMPLATE_ATTRS}
        widget["input_attrs"] = {key: val for key, val in rest.items() if key.startswith(("data-", "hx-"))}
        widget["part_attrs"] = {key: val for key, val in rest.items() if key in _PART_ATTRS}
        widget["start_attrs"] = {
            key: val for key, val in rest.items() if key not in widget["input_attrs"] and key not in _PART_ATTRS
        }
        return context

    def _parse(self, value: str | None) -> dt.date | None:
        """The day a subwidget's ISO text names, or None."""
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
    input_format_settings = ("DATETIME_INPUT_FORMATS", "DATE_INPUT_FORMATS")

    def _parse(self, value: str | None) -> dt.datetime | None:
        # A model's aware datetime arrives as its str(); show it in the current time zone.
        try:
            parsed = parse_datetime(value.strip()) if value else None
        except ValueError:
            return None
        return to_current_timezone(parsed) if parsed else None
