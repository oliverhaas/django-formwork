"""Form fields that clean several inputs into one value."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from django import forms
from django.utils.translation import gettext_lazy as _

from django_formwork.widgets.date_input import DateRangeInput

if TYPE_CHECKING:
    import datetime as dt

__all__ = ["DateRange", "DateRangeField"]


class DateRange(NamedTuple):
    start: dt.date | None
    end: dt.date | None


class DateRangeField(forms.MultiValueField):
    """Cleans to a ``DateRange`` and owns the rules that span both dates.

    ``required`` demands both dates. ``max_span`` caps the distance between them; name the limit in
    ``error_messages["max_span"]``.
    """

    widget = DateRangeInput
    default_error_messages = {  # noqa: RUF012 (Django merges it up the MRO)
        "start_after_end": _("Start date must be before end date"),
        "max_span": _("The date range is too long."),
    }

    def __init__(self, *, max_span: dt.timedelta | None = None, **kwargs: Any) -> None:
        self.max_span = max_span
        super().__init__(fields=(forms.DateField(), forms.DateField()), **kwargs)

    def compress(self, data_list: list[dt.date | None]) -> DateRange:
        if not data_list:
            return DateRange(None, None)
        return DateRange(*data_list)

    def validate(self, value: DateRange) -> None:
        super().validate(value)
        start, end = value
        if not start or not end:
            return
        if start > end:
            raise forms.ValidationError(self.error_messages["start_after_end"], code="start_after_end")
        if self.max_span and end > start + self.max_span:
            raise forms.ValidationError(self.error_messages["max_span"], code="max_span")
