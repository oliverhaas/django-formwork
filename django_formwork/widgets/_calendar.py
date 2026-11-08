"""Server side of the calendar dropdown that DatePicker and the range pickers share."""

from __future__ import annotations

import json
import re
from typing import Any

from django.utils import dateformat
from django.utils.dates import MONTHS, MONTHS_3, MONTHS_ALT, MONTHS_AP, WEEKDAYS, WEEKDAYS_ABBR
from django.utils.formats import get_format
from django.utils.translation import gettext

# Django's date format codes, as django.utils.dateformat reads them.
_FORMAT_CODE = re.compile(r"(?<!\\)([aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ])")


def _names() -> dict[str, list[str]]:
    """The names each code writes, in the active language. Months start at January, weekdays at Monday."""
    months = range(1, 13)
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


def calendar_context(months: int = 1, **formats: str) -> dict[str, Any]:
    """What the calendar template and script need to show ``months`` months and write dates like the server.

    Each keyword names a format the script writes with: a Django format setting such as
    ``"DATE_FORMAT"``, or a format string. Only the names those formats use are sent.
    """
    formats = {"title": "YEAR_MONTH_FORMAT", "label": "DATE_FORMAT", **formats}
    resolved = {key: str(get_format(value)) for key, value in formats.items()}
    codes = set(_FORMAT_CODE.findall("".join(resolved.values()))) | {"M"}
    if "P" in codes:
        codes.add("a")
    names = {code: names for code, names in _names().items() if code in codes}
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
    }


def format_date(value: Any, date_format: str) -> str:  # noqa: ANN401 (date or datetime)
    """``value`` written in ``date_format``, as the script writes it."""
    return dateformat.format(value, date_format) if value else ""
