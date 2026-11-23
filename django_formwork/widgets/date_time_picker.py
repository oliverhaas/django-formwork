"""DateTimePicker widget."""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from typing import Any

from django import forms
from django.core.signals import setting_changed
from django.forms.utils import to_current_timezone
from django.utils import dateformat, translation
from django.utils.dateparse import parse_datetime
from django.utils.formats import get_format
from django.utils.translation import get_language, pgettext_lazy

from ._base import _ModuleScript, _StubMixin
from ._calendar import calendar_context, format_date, sizing_texts
from .date_picker import _PLACEHOLDER_TOKENS

_HOUR = pgettext_lazy("time format placeholder", "hh")
_MINUTE = pgettext_lazy("time format placeholder", "mm")

# How a placeholder spells each Django format code. Other codes write nothing.
_SPELLED = {
    "Y": _PLACEHOLDER_TOKENS["Y"],
    "y": _PLACEHOLDER_TOKENS["y"],
    "m": _PLACEHOLDER_TOKENS["m"],
    "n": _PLACEHOLDER_TOKENS["m"],
    "d": _PLACEHOLDER_TOKENS["d"],
    "j": _PLACEHOLDER_TOKENS["d"],
    "F": _PLACEHOLDER_TOKENS["B"],
    "E": _PLACEHOLDER_TOKENS["B"],
    "b": _PLACEHOLDER_TOKENS["b"],
    "M": _PLACEHOLDER_TOKENS["b"],
    "N": _PLACEHOLDER_TOKENS["b"],
    "l": _PLACEHOLDER_TOKENS["A"],
    "D": _PLACEHOLDER_TOKENS["a"],
    "H": _HOUR,
    "h": _HOUR,
    "G": _HOUR,
    "g": _HOUR,
    "i": _MINUTE,
    "s": pgettext_lazy("time format placeholder", "ss"),
}

_FORMAT_CODE = re.compile(r"\\(.)|([aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ])")


def _placeholder(date_format: str) -> str:
    """A Django format spelled out, such as ``MM/DD/YYYY hh:mm``."""
    return _spelled(date_format, get_language())


@lru_cache(maxsize=64)
def _spelled(date_format: str, language: str | None) -> str:
    morning = dt.datetime(2000, 1, 1)  # noqa: DTZ001 (only formatted)
    with translation.override(language):
        spelled = {code: str(token) for code, token in _SPELLED.items()}
        spelled |= {code: dateformat.format(morning, code) for code in "aA"}
    spelled |= {"f": f"{spelled['h']}:{spelled['i']}", "P": f"{spelled['h']}:{spelled['i']} {spelled['a']}"}
    return _FORMAT_CODE.sub(lambda match: match[1] or spelled.get(match[2], ""), date_format).strip()


def _forget_spellings(*, setting: str, **_: Any) -> None:
    if setting in {"LOCALE_PATHS", "INSTALLED_APPS"}:
        _spelled.cache_clear()


setting_changed.connect(_forget_spellings)


class DateTimePicker(_StubMixin, forms.Widget):
    """A day and a time, typed or picked in a calendar, posted as ``YYYY-MM-DDTHH:MM`` local time.

    ``format`` is how the input shows the value: a Django format setting name or a format string."""

    template_name = "formwork/widgets/date_time_picker.html"
    stub_template_name = "formwork/widgets/date_time_picker_stub.html"
    supports_microseconds = False
    default_format = "SHORT_DATETIME_FORMAT"
    # The settings whose strftime formats a typed value can also take.
    input_format_settings = ("DATETIME_INPUT_FORMATS", "DATE_INPUT_FORMATS")

    class Media:
        js = (_ModuleScript("formwork/widgets/date_time_picker.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None, *, format: str | None = None) -> None:  # noqa: A002
        self.format = format or self.default_format
        super().__init__(attrs)

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = self.get_stub_context(name, value, attrs)
        input_formats = dict.fromkeys(str(fmt) for setting in self.input_format_settings for fmt in get_format(setting))
        context["widget"]["calendar"] = calendar_context(value=self.format, input_formats=list(input_formats))
        return context

    def get_stub_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # The calendar's "value" format.
        text_format = str(get_format(self.format))
        parsed = self._parse(value)
        if parsed is None:
            # Text that names no day goes back as it came, next to the error it gets.
            widget["iso_value"] = widget["text"] = "" if value is None else str(value)
        else:
            widget["iso_value"] = parsed.strftime("%Y-%m-%dT%H:%M:%S" if parsed.second else "%Y-%m-%dT%H:%M")
            widget["text"] = format_date(parsed, text_format)
        # Data and htmx attrs go on the hidden input, which fires `change`.
        attrs = widget["attrs"]
        hidden = {key: val for key, val in attrs.items() if key.startswith(("data-", "hx-"))}
        widget["attrs"] = {"placeholder": _placeholder(text_format)} | {
            key: val for key, val in attrs.items() if key not in hidden
        }
        # The input is as wide as the widest date it can show, whatever it holds.
        placeholder = str(widget["attrs"].get("placeholder") or "")
        widget["sizing_texts"] = sizing_texts(text_format, placeholder)
        # The template places the class itself, after its own.
        widget["extra_class"] = widget["attrs"].pop("class", "")
        widget["hidden"] = {"attrs": hidden}
        return context

    def _parse(self, value: object) -> dt.datetime | None:
        """The local date and time that a value names, or None."""
        if isinstance(value, dt.datetime):
            return to_current_timezone(value)
        if isinstance(value, dt.date):
            return dt.datetime.combine(value, dt.time())
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = parse_datetime(value.strip())
        except ValueError:
            return None
        return to_current_timezone(parsed) if parsed else None
