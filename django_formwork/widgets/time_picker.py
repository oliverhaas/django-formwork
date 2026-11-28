"""TimePicker widget."""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from django import forms
from django.utils import dateformat
from django.utils.dateparse import parse_time
from django.utils.formats import get_format
from django.utils.translation import get_language

from ._base import _ModuleScript, _StubMixin
from ._calendar import _names, sizing_texts
from .date_time_picker import _placeholder

# The codes of a time, unless escaped.
_CLOCK_CODE = re.compile(r"\\.|([HGhgfPaA])")


class TimePicker(_StubMixin, forms.Widget):
    """A time of day, typed or picked from lists of hours and minutes, posted as ``HH:MM``.

    ``format`` is how the input shows the time: a Django format setting name or a format string.
    ``minute_step`` sets the minutes the list offers; a typed time can hold any minute."""

    template_name = "formwork/widgets/time_picker.html"
    stub_template_name = "formwork/widgets/time_picker_stub.html"
    supports_microseconds = False
    default_format = "TIME_FORMAT"

    class Media:
        js = (_ModuleScript("formwork/widgets/time_picker.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        format: str | None = None,  # noqa: A002
        minute_step: int = 5,
    ) -> None:
        if minute_step < 1:
            msg = "minute_step must be at least 1."
            raise ValueError(msg)
        self.format = format or self.default_format
        self.minute_step = minute_step
        super().__init__(attrs)

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = self.get_stub_context(name, value, attrs)
        widget = context["widget"]
        codes = {match[1] for match in _CLOCK_CODE.finditer(widget["time_format"]) if match[1]}
        # How the hour list writes an hour, and for a 12-hour clock the code of its a.m. and p.m.
        # names: those the format writes, ``a`` when it writes none.
        hour = next((code for code in "HGhg" if code in codes), "g" if codes & {"f", "P"} else "H")
        half = "" if hour in "HG" else "A" if "A" in codes else "a"
        # The names the format writes, and those of the hour list. P writes a.m. and p.m. as ``a`` does.
        name_codes = (codes & {"a", "A", "P"}) | ({half} - {""}) | ({"a"} if "P" in codes else set())
        names = {code: names for code, names in _names(get_language()).items() if code in name_codes}
        input_formats = [str(fmt) for fmt in get_format("TIME_INPUT_FORMATS")]
        widget["clock"] = {
            "hour": hour,
            "half": half,
            "step": self.minute_step,
            "names_json": json.dumps(names, ensure_ascii=False),
            "formats_json": json.dumps({"value": widget["time_format"]}, ensure_ascii=False),
            "input_formats_json": json.dumps(list(dict.fromkeys(input_formats)), ensure_ascii=False),
        }
        return context

    def get_stub_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        time_format = str(get_format(self.format))
        widget["time_format"] = time_format
        parsed = self._parse(value)
        if parsed is None:
            # Text that names no time goes back as it came, next to the error it gets.
            widget["iso_value"] = widget["text"] = "" if value is None else str(value)
        else:
            widget["iso_value"] = parsed.strftime("%H:%M:%S" if parsed.second else "%H:%M")
            widget["text"] = dateformat.time_format(parsed, time_format)
        # Data and htmx attrs go on the hidden input, which fires `change`.
        attrs = widget["attrs"]
        hidden = {key: val for key, val in attrs.items() if key.startswith(("data-", "hx-"))}
        widget["attrs"] = {"placeholder": _placeholder(time_format)} | {
            key: val for key, val in attrs.items() if key not in hidden
        }
        # The input is as wide as the widest time it can show, whatever it holds.
        placeholder = str(widget["attrs"].get("placeholder") or "")
        widget["sizing_texts"] = sizing_texts(time_format, placeholder)
        # The template places the class itself, after its own.
        widget["extra_class"] = widget["attrs"].pop("class", "")
        widget["hidden"] = {"attrs": hidden}
        return context

    def _parse(self, value: object) -> dt.time | None:
        """The time of day that a value names, or None."""
        if isinstance(value, dt.time):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return parse_time(value.strip())
        except ValueError:
            return None
