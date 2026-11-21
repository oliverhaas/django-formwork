"""Form fields that clean several inputs into one value, and a field that only shows one."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, cast

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.fields.related_descriptors import ReverseManyToOneDescriptor
from django.utils.translation import gettext_lazy as _

from django_formwork.boundfield import FormworkBoundField
from django_formwork.widgets.date_range_picker import DateRangePicker, DateTimeRangePicker
from django_formwork.widgets.display import Display
from django_formwork.widgets.file_dropzone import FileDropzoneInput

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterable

    from django.core.files.uploadedfile import UploadedFile

__all__ = [
    "DateRange",
    "DateRangeField",
    "DateTimeRange",
    "DateTimeRangeField",
    "DisplayField",
    "MultipleFileField",
]


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

    # Django's MultiWidget decompresses any value that is not a pair, and its own
    # decompress raises. The widget always gets a pair, so a plain MultiWidget works.
    def prepare_value(self, value: object) -> object:
        return value or self.range_type(None, None)

    def has_changed(self, initial: object, data: object) -> bool:
        pair = list(cast("Iterable[object]", initial)) if initial else None
        return super().has_changed(pair, data)

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


def _instance_value(instance: models.Model, source: str | Callable[[Any], Any]) -> Any:  # noqa: ANN401
    if callable(source):
        return source(instance)
    display = getattr(instance, f"get_{source}_display", None)
    if callable(display):
        return display()
    # An unsaved instance has no related rows, and its managers raise.
    if instance.pk is None and isinstance(getattr(type(instance), source, None), ReverseManyToOneDescriptor):
        return []
    try:
        value = getattr(instance, source)
    except ObjectDoesNotExist:
        return None
    if isinstance(value, models.Manager):
        return list(value.all())
    return value() if callable(value) else value


class _DisplayBoundField(FormworkBoundField):
    """Reads the value when the page shows it, and never from the post."""

    @cached_property
    def initial(self) -> Any:  # noqa: ANN401
        return cast("DisplayField", self.field).value_for(self.form, self.name)

    def value(self) -> Any:  # noqa: ANN401
        return self.field.prepare_value(self.initial)

    def _has_changed(self) -> bool:
        return False


class DisplayField(forms.Field):
    """A value the form shows and never posts: an attribute, a method or an annotation of the form's instance.

    ``source`` names the attribute, or is a function of the instance, and defaults to the field's name.
    A form without an instance shows its ``initial`` value. Formwork's forms leave the field out of ``cleaned_data``.
    """

    widget = Display
    bound_field_class = _DisplayBoundField

    def __init__(self, *, source: str | Callable[[Any], Any] | None = None, **kwargs: Any) -> None:
        super().__init__(required=False, disabled=True, **kwargs)
        self.source = source

    def value_for(self, form: forms.BaseForm, name: str) -> Any:  # noqa: ANN401
        """The value the field shows on ``form``: from its instance, else from its initial data."""
        instance = getattr(form, "instance", None)
        if instance is None:
            return form.get_initial_for_field(self, name)
        return _instance_value(instance, self.source or name)

    def has_changed(self, initial: Any, data: Any) -> bool:  # noqa: ANN401, ARG002
        return False

    # Django cleans a disabled field's initial value, which would read the instance on every post.
    def _clean_bound_field(self, bf: forms.BoundField) -> None:  # noqa: ARG002
        return None
