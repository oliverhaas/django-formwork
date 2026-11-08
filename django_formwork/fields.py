"""Form fields that clean several inputs into one value."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from django import forms
from django.utils.translation import gettext_lazy as _

from django_formwork.widgets.date_range_picker import DateRangePicker, DateTimeRangePicker
from django_formwork.widgets.file_dropzone import FileDropzoneInput

if TYPE_CHECKING:
    import datetime as dt

    from django.core.files.uploadedfile import UploadedFile

__all__ = ["DateRange", "DateRangeField", "DateTimeRange", "DateTimeRangeField", "MultipleFileField"]


class DateRange(NamedTuple):
    start: dt.date | None
    end: dt.date | None


class DateTimeRange(NamedTuple):
    start: dt.datetime | None
    end: dt.datetime | None


class _RangeField(forms.MultiValueField):
    """Cleans a start and an end to a range and owns the rules that span both."""

    range_type: ClassVar[type[DateRange | DateTimeRange]]
    end_field: ClassVar[type[forms.Field]]

    def __init__(self, *, max_span: dt.timedelta | None = None, **kwargs: Any) -> None:
        self.max_span = max_span
        super().__init__(fields=(self.end_field(), self.end_field()), **kwargs)

    def compress(self, data_list: list[Any]) -> DateRange | DateTimeRange:
        if not data_list:
            return self.range_type(None, None)
        return self.range_type(*data_list)

    def validate(self, value: DateRange | DateTimeRange) -> None:
        super().validate(value)
        start, end = value
        if not start or not end:
            return
        if start > end:
            raise forms.ValidationError(self.error_messages["start_after_end"], code="start_after_end")
        if self.max_span is not None and end > start + self.max_span:
            raise forms.ValidationError(self.error_messages["max_span"], code="max_span")


class DateRangeField(_RangeField):
    """Cleans a start and an end date to a ``DateRange``.

    ``required`` demands both dates. ``max_span`` caps the distance between them; name the limit in
    ``error_messages["max_span"]``.
    """

    widget = DateRangePicker
    range_type = DateRange
    end_field = forms.DateField
    default_error_messages = {  # noqa: RUF012 (Django merges it up the MRO)
        "start_after_end": _("Start date must be before end date"),
        "max_span": _("The date range is too long."),
    }


class DateTimeRangeField(_RangeField):
    """Cleans a start and an end date and time to a ``DateTimeRange``.

    ``required`` demands both ends. ``max_span`` caps the distance between them; name the limit in
    ``error_messages["max_span"]``.
    """

    widget = DateTimeRangePicker
    range_type = DateTimeRange
    end_field = forms.DateTimeField
    default_error_messages = {  # noqa: RUF012 (Django merges it up the MRO)
        "start_after_end": _("Start must be before end"),
        "max_span": _("The time range is too long."),
    }


class MultipleFileField(forms.FileField):
    """Cleans the files of a ``multiple`` file input to a list.

    The default widget is ``FileDropzoneInput`` with ``multiple``. ``required`` demands at least one
    file, and each file passes the ``FileField`` checks.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["widget"] = kwargs.get("widget") or FileDropzoneInput(attrs={"multiple": True})
        super().__init__(**kwargs)

    def clean(self, data: Any, initial: Any = None) -> list[UploadedFile]:  # noqa: ANN401, ARG002 (widget data)
        files = data if isinstance(data, list | tuple) else [data] if data else []
        clean_file = super().clean
        if not files:
            clean_file(None)
            return []
        return [clean_file(file) for file in files]

    def has_changed(self, initial: Any, data: Any) -> bool:  # noqa: ANN401, ARG002 (widget data)
        return not self.disabled and bool(data)
