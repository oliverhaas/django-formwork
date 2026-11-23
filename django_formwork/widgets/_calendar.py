"""Server side of the calendar dropdown that DatePicker and the range pickers share."""

from __future__ import annotations

import datetime as dt
import json
import re
from functools import cache
from typing import TYPE_CHECKING, Any

from django.core.signals import setting_changed
from django.utils import dateformat
from django.utils.dates import MONTHS, MONTHS_3, MONTHS_ALT, MONTHS_AP, WEEKDAYS, WEEKDAYS_ABBR
from django.utils.formats import get_format
from django.utils.translation import get_language, gettext, override

if TYPE_CHECKING:
    from collections.abc import Sequence


# Django's date format codes, as django.utils.dateformat reads them.
_FORMAT_CODE = re.compile(r"(?<!\\)([aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ])")

# The names a typed date can hold for each strftime code of an input format.
_INPUT_NAMES = {"a": {"D", "l"}, "A": {"D", "l"}, "p": {"a", "A"}}


@cache
def _names(language: str | None) -> dict[str, list[str]]:
    """The names each code writes in ``language``. Months start at January, weekdays at Monday.

    Cached, as every calendar of a page asks for them."""
    months = range(1, 13)
    with override(language):
        return {
            "F": [str(MONTHS[month]) for month in months],
            "N": [str(MONTHS_AP[month]) for month in months],
            "E": [str(MONTHS_ALT[month]) for month in months],
            "b": [str(MONTHS_3[month]) for month in months],
            "M": [str(MONTHS_3[month]).title() for month in months],
            "l": [str(WEEKDAYS[day]) for day in range(7)],
            "D": [str(WEEKDAYS_ABBR[day]) for day in range(7)],
            "a": [gettext("a.m."), gettext("p.m.")],
            "A": [gettext("AM"), gettext("PM")],
            "P": [gettext("midnight"), gettext("noon")],
        }


def _reset_names(*, setting: str, **_: object) -> None:
    # The settings with which Django reloads its translations.
    if setting in {"INSTALLED_APPS", "LANGUAGES", "LANGUAGE_CODE", "LOCALE_PATHS"}:
        _names.cache_clear()
        _sizing_texts.cache_clear()


setting_changed.connect(_reset_names)


def calendar_context(months: int = 1, *, input_formats: Sequence[str] = (), **formats: str) -> dict[str, Any]:
    """What the calendar needs to show ``months`` months and read and write dates like the server.

    Each keyword is a format setting or a format string; ``input_formats`` are strftime formats it reads."""
    formats = {"title": "YEAR_MONTH_FORMAT", "label": "DATE_FORMAT", **formats}
    resolved = {key: str(get_format(value)) for key, value in formats.items()}
    codes = set(_FORMAT_CODE.findall("".join(resolved.values()))) | {"M"}
    if input_formats:
        # A typed month can be a full name whatever the formats write.
        codes.add("F")
        for code in re.findall(r"%(.)", "".join(input_formats)):
            codes |= _INPUT_NAMES.get(code, set())
    if codes & {"a", "A", "P"}:
        codes |= {"a", "A"}
    names = {code: names for code, names in _names(get_language()).items() if code in codes}
    first_day = int(get_format("FIRST_DAY_OF_WEEK"))
    # Django counts weekdays from Monday, the calendar's FIRST_DAY_OF_WEEK from Sunday.
    columns = [(first_day + offset + 6) % 7 for offset in range(7)]
    return {
        "offsets": range(months),
        "first_day": first_day,
        "weekdays": [{"abbr": WEEKDAYS_ABBR[day], "name": WEEKDAYS[day]} for day in columns],
        "names_json": json.dumps(names, ensure_ascii=False),
        "formats_json": json.dumps(resolved, ensure_ascii=False),
        "formats": resolved,
        "input_formats_json": json.dumps(list(input_formats), ensure_ascii=False),
    }


def format_date(value: Any, date_format: str) -> str:  # noqa: ANN401 (date or datetime)
    """``value`` written in ``date_format``, as the script writes it."""
    return dateformat.format(value, date_format) if value else ""


def sizing_texts(date_format: str, *placeholders: str, strftime: bool = False) -> tuple[str, ...]:
    """The widest texts a date input shows: a date in each month in ``date_format``, and the placeholders.

    ``date_format`` is a Django format, or a ``strftime`` one with ``strftime``. The inputs set
    digits in tabular figures, so texts that differ only in digits count once.
    """
    return _sizing_texts(date_format, tuple(map(str, placeholders)), get_language(), strftime=strftime)


@cache
def _sizing_texts(
    date_format: str, placeholders: tuple[str, ...], language: str | None, *, strftime: bool
) -> tuple[str, ...]:
    """Cached, as each row of a table renders its date inputs."""
    dates = (dt.datetime(2026, month, 28, 23, 59) for month in range(1, 13))  # noqa: DTZ001 (only formatted)
    with override(language):
        texts = [date.strftime(date_format) if strftime else format_date(date, date_format) for date in dates]
    return tuple(dict.fromkeys(re.sub(r"\d", "0", text) for text in (*texts, *placeholders)))
