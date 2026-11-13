"""The changelist's filter bar: a django-filter ``FilterSet`` built from ``list_filter``.

The filters read and write the query parameters of Django's list filters, such as
``status__exact`` and ``published__gte``, so a link filters the same rows in both admins."""

from __future__ import annotations

import copy
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, cast

import django_filters
from django import forms
from django.conf import settings
from django.contrib.admin.filters import (
    BooleanFieldListFilter,
    ChoicesFieldListFilter,
    DateFieldListFilter,
    EmptyFieldListFilter,
    FieldListFilter,
    RelatedFieldListFilter,
    RelatedOnlyFieldListFilter,
    SimpleListFilter,
)
from django.contrib.admin.utils import get_fields_from_path, lookup_spawns_duplicates
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related import RelatedField
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django_filters.widgets import RangeWidget, SuffixedMultiWidget

from django_formwork.admin.widgets import date_input_format, relation_widget
from django_formwork.forms import FormworkForm
from django_formwork.widgets import DateRangePicker, SearchInput, Select

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, QueryDict
    from django.utils.safestring import SafeString

__all__ = ["NULL_VALUE", "SEARCH_VAR", "AdminFilterSet", "build_filterset", "list_filter_path"]

SEARCH_VAR = "q"

# The option that picks rows without a value; the URL carries Django's "__isnull=True" instead.
NULL_VALUE = "null"


def _floating(label: object) -> dict[str, Any]:
    return {"attrs": {"placeholder": capfirst(str(label))}, "allow_clear": True, "floating": True}


def _truthy(value: str) -> bool:
    """An ``__isnull`` value as Django's ``prepare_lookup_value`` reads it."""
    return value.lower() not in {"", "false", "0"}


class _FloatingDateRangePicker(DateRangePicker):
    """The range picker with the filter's name on its border, and the presets of Django's date filter.

    The inputs post the first and the last day as ``__gte`` and ``__lte``, and a choice as ``__isnull``."""

    def __init__(self, label: object, choices: list[tuple[str, Any]]) -> None:
        super().__init__(format=date_input_format()[1], presets=True, choices=choices)
        self.widgets_names = ["__gte", "__lte", "__isnull"][: len(self.widgets)]
        self.label = capfirst(str(label))

    def render(self, name: str, value: Any, attrs: dict[str, Any] | None = None, renderer: Any = None) -> SafeString:
        attrs = dict(attrs or {})
        label_id = f"{attrs['id']}_floating_label" if attrs.get("id") else ""
        if label_id:
            attrs["aria-labelledby"] = label_id
        return format_html(
            '<div class="floating-label formwork-floating-select date-range-filter"><span{}>{}</span>{}</div>',
            format_html(' id="{}"', label_id) if label_id else "",
            self.label,
            super().render(name, value, attrs, renderer),
        )


# The min and max inputs sit bare inside the .input wrapper, which draws the field.
_RANGE_INPUT = "min-w-0 px-0 shadow-none"


class _FloatingRangeWidget(RangeWidget):
    """django-filter's min and max inputs drawn as one field, with the filter's name on its border.

    The inputs post ``__gte`` and ``__lte``, the lookups of Django's query string."""

    suffixes = ("_gte", "_lte")

    def __init__(self, label: object) -> None:
        super().__init__()
        self.label = capfirst(str(label))
        self.widgets = [
            forms.NumberInput(attrs={"step": "any", "placeholder": _("Min"), "class": _RANGE_INPUT}),
            forms.NumberInput(attrs={"step": "any", "placeholder": _("Max"), "class": _RANGE_INPUT}),
        ]

    def render(self, name: str, value: Any, attrs: dict[str, Any] | None = None, renderer: Any = None) -> SafeString:
        attrs = dict(attrs or {})
        label_id = f"{attrs['id']}_floating_label" if attrs.get("id") else ""
        subwidgets = self.get_context(name, value, attrs)["widget"]["subwidgets"]
        bounds = [_("%(name)s, minimum") % {"name": self.label}, _("%(name)s, maximum") % {"name": self.label}]
        start, end = (
            widget.render(sub["name"], sub["value"], {**sub["attrs"], "aria-label": bound}, renderer)
            for widget, sub, bound in zip(self.widgets, subwidgets, bounds, strict=True)
        )
        return format_html(
            '<div class="floating-label formwork-floating-select"><span{}>{}</span>'
            '<div class="input w-full" role="group"{}>{}'
            '<span class="shrink-0 opacity-50" aria-hidden="true">&#8211;</span>{}</div></div>',
            format_html(' id="{}"', label_id) if label_id else "",
            self.label,
            format_html(' aria-labelledby="{}"', label_id) if label_id else "",
            start,
            end,
        )


def _count() -> models.Count:
    # Distinct, so a row that a join repeats counts once.
    return models.Count("pk", distinct=True)


def _value_key(value: Any) -> str:
    return NULL_VALUE if value is None else str(value)


class _FieldFilterMixin:
    """Picks the control from the model field it filters, after the label is known."""

    model: type[models.Model]
    field_name: str
    label: Any
    extra: dict[str, Any]
    parent: AdminFilterSet
    null_param: str | None

    @property
    def model_field(self) -> Any:
        return get_fields_from_path(self.model, self.field_name)[-1]

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        return {}

    @property
    def field(self) -> forms.Field:
        if not hasattr(self, "_field"):
            model_field = self.model_field
            if self.label is None:
                # A reverse relation has no verbose_name; Django's filter names its model.
                self.label = getattr(model_field, "verbose_name", None) or model_field.related_model._meta.verbose_name
            self.extra = self.field_defaults(model_field) | self.extra
            field = super().field  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
            # The control floats the filter's name, so the field draws no label row.
            field.label = ""
            return field
        return super().field  # type: ignore[misc]  # ty: ignore[unresolved-attribute]


class BooleanFilter(_FieldFilterMixin, django_filters.ChoiceFilter):
    """Yes, No and, for a nullable field, Unknown, with the titles ``BooleanFieldListFilter`` shows."""

    # The values Django's BooleanField reads, to the two the options post.
    _VALUES: ClassVar[dict[str, str]] = {"1": "1", "t": "1", "True": "1", "0": "0", "f": "0", "False": "0"}

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        titles = dict(model_field.flatchoices)
        choices = [("1", titles.get(True, _("Yes"))), ("0", titles.get(False, _("No")))]
        if model_field.null:
            choices.append((NULL_VALUE, titles.get(None, _("Unknown"))))
        return {
            "choices": choices,
            "empty_label": _("All"),
            "widget": Select(show_search=False, **_floating(self.label)),
        }

    def read_params(self, name: str, data: QueryDict, form_data: QueryDict) -> None:
        value = data.get(name)
        if value in self._VALUES:
            form_data[name] = self._VALUES[value]

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        rows = qs.order_by().values_list(self.field_name).annotate(count=_count())
        return {_value_key(value if value is None else int(value)): count for value, count in rows}


class ChoiceFilter(_FieldFilterMixin, django_filters.ChoiceFilter):
    """The field's choices; a choice for None, as Django's filter does, comes last."""

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        choices = [(value, title) for value, title in model_field.flatchoices if value is not None]
        none_title = dict(model_field.flatchoices).get(None)
        if none_title and self.null_param:
            choices.append((NULL_VALUE, none_title))
        return {"choices": choices, "empty_label": _("All"), "widget": Select(**_floating(self.label))}

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        rows = qs.order_by().values_list(self.field_name).annotate(count=_count())
        return {_value_key(value): count for value, count in rows}


class RelatedFilter(_FieldFilterMixin, django_filters.ModelChoiceFilter):
    """One related row, paged from the server when the related admin can search."""

    related_only = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Before django-filter sets its "---------".
        kwargs.setdefault("empty_label", _("All"))
        super().__init__(*args, **kwargs)

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        related = model_field.related_model
        model_admin = self.parent.model_admin
        request = self.parent.request
        if self.related_only:
            # Only rows the list points at, as RelatedOnlyFieldListFilter offers.
            used = model_admin.get_queryset(request).values(f"{self.field_name}{LOOKUP_SEP}pk")
            queryset = related._default_manager.filter(pk__in=used)
        elif isinstance(model_field, RelatedField):
            queryset = related._default_manager.complex_filter(model_field.get_limit_choices_to())
        else:
            queryset = related._default_manager.all()
        # In the related admin's order, as Django's filter lists them.
        related_admin = model_admin.admin_site.get_model_admin_or_none(related)
        if related_admin is not None and (ordering := related_admin.get_ordering(request)):
            queryset = queryset.order_by(*ordering)
        direct = LOOKUP_SEP not in self.field_name and isinstance(model_field, RelatedField)
        searchable = direct and not self.related_only and model_admin.admin_site.is_searchable(related)
        # One row, as Django's related filter picks, a many-to-many relation included.
        widget = relation_widget(
            model_field, model_admin.admin_site, searchable=searchable, multiple=False, **_floating(self.label)
        )
        defaults: dict[str, Any] = {"queryset": queryset, "widget": widget}
        target = model_field.target_field.name
        if target != related._meta.pk.name:
            defaults["to_field_name"] = target
        if self.null_param:
            defaults["null_label"] = model_admin.get_empty_value_display()
        return defaults

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        target = self.model_field.target_field.name
        rows = qs.order_by().values_list(f"{self.field_name}{LOOKUP_SEP}{target}").annotate(count=_count())
        return {_value_key(value): count for value, count in rows}


class EmptyFilter(_FieldFilterMixin, django_filters.ChoiceFilter):
    """Whether the field is empty, as ``EmptyFieldListFilter`` asks."""

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        return {
            "choices": [("1", _("Empty")), ("0", _("Not empty"))],
            "empty_label": _("All"),
            "widget": Select(show_search=False, **_floating(self.label)),
        }

    def _empty(self) -> models.Q:
        model_field = self.model_field
        empty = models.Q(**{f"{self.field_name}__isnull": True})
        if getattr(model_field, "empty_strings_allowed", False) and not model_field.is_relation:
            empty |= models.Q(**{self.field_name: ""})
        return empty

    def filter(self, qs: QuerySet[Any], value: str) -> QuerySet[Any]:
        if value not in {"1", "0"}:
            return qs
        empty = self._empty()
        return qs.filter(empty) if value == "1" else qs.exclude(empty)

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        empty = self._empty()
        counts = qs.aggregate(
            empty=models.Count("pk", filter=empty, distinct=True),
            filled=models.Count("pk", filter=~empty, distinct=True),
        )
        return {"1": counts["empty"], "0": counts["filled"]}


def _day(value: str, *, exclusive: bool = False) -> date | None:
    """The local day of a date or a moment in the query; an exclusive bound at midnight ends the day before."""
    try:
        moment = parse_datetime(value.strip())
    except ValueError:
        return None
    if moment is None:
        return None
    if timezone.is_aware(moment):
        moment = timezone.localtime(moment)
    if exclusive and moment.time() == time.min:
        return moment.date() - timedelta(days=1)
    return moment.date()


def _hierarchy(data: QueryDict, name: str) -> tuple[date, date] | None:
    """The first and last day of ``date_hierarchy``'s ``__year``, ``__month`` and ``__day``."""
    year = data.get(f"{name}__year")
    if year is None:
        return None
    month, day = data.get(f"{name}__month"), data.get(f"{name}__day")
    try:
        start = date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        return None
    if day:
        return start, start
    if month:
        return start, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return start, start.replace(month=12, day=31)


class _DateFilterValue(NamedTuple):
    start: date | None
    end: date | None
    isnull: bool | None


class _DateFilterField(forms.MultiValueField):
    """The first and the last day of a date filter, and its ``__isnull`` choice."""

    def __init__(self, **kwargs: Any) -> None:
        fields = (
            forms.DateField(required=False),
            forms.DateField(required=False),
            forms.NullBooleanField(required=False),
        )
        super().__init__(fields, require_all_fields=False, **kwargs)

    def compress(self, data_list: list[Any]) -> _DateFilterValue | None:
        if not any(value is not None for value in data_list):
            return None
        return _DateFilterValue(*data_list)


class DateRangeFilter(_FieldFilterMixin, django_filters.DateFromToRangeFilter):
    """A range of days, read from and written as the ``__gte`` and ``__lt`` bounds of Django's date filter.

    It also reads an inclusive ``__lte`` and the ``__year``, ``__month`` and ``__day`` of ``date_hierarchy``.
    A nullable field adds Django's "No date" and "Has date" as ``__isnull``.
    """

    field_class = _DateFilterField

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        choices = [("True", _("No date")), ("False", _("Has date"))] if self.null_param else []
        return {"widget": _FloatingDateRangePicker(self.label, choices)}

    def bound(self, day: date) -> date | datetime:
        """The value Django's filter compares with: the day, or its local midnight on a date and time field."""
        if not isinstance(self.model_field, models.DateTimeField):
            return day
        midnight = datetime.combine(day, time.min)
        return timezone.make_aware(midnight) if settings.USE_TZ else midnight

    def claimed_params(self, name: str, data: QueryDict) -> set[str]:
        keys = {f"{name}__{lookup}" for lookup in ("gte", "lt", "lte")}
        if f"{name}__year" in data:
            keys |= {f"{name}__{part}" for part in ("year", "month", "day")}
        if self.null_param:
            keys.add(self.null_param)
        return keys & set(data)

    def read_params(self, name: str, data: QueryDict, form_data: QueryDict) -> None:
        starts = [_day(value) for value in data.getlist(f"{name}__gte")]
        ends = [_day(value, exclusive=True) for value in data.getlist(f"{name}__lt")]
        ends += [_day(value) for value in data.getlist(f"{name}__lte")]
        if span := _hierarchy(data, name):
            starts.append(span[0])
            ends.append(span[1])
        # Every bound applies, as Django's lookups do.
        start = max((day for day in starts if day), default=None)
        end = min((day for day in ends if day), default=None)
        form_data.setlist(f"{name}__gte", [start.isoformat()] if start else [])
        form_data.setlist(f"{name}__lte", [end.isoformat()] if end else [])
        if self.null_param and (isnull := data.get(self.null_param)) is not None:
            form_data[self.null_param] = str(_truthy(isnull))

    def written_params(self, name: str, form_data: QueryDict) -> list[tuple[str, str]]:
        pairs = []
        if start := parse_date(form_data.get(f"{name}__gte") or ""):
            pairs.append((f"{name}__gte", str(self.bound(start))))
        if end := parse_date(form_data.get(f"{name}__lte") or ""):
            pairs.append((f"{name}__lt", str(self.bound(end + timedelta(days=1)))))
        if self.null_param and (isnull := form_data.get(self.null_param)):
            pairs.append((self.null_param, isnull))
        return pairs

    def filter(self, qs: QuerySet[Any], value: _DateFilterValue | None) -> QuerySet[Any]:
        if not value:
            return qs
        lookups: dict[str, object] = {}
        if value.start is not None:
            lookups[f"{self.field_name}__gte"] = self.bound(value.start)
        if value.end is not None:
            lookups[f"{self.field_name}__lt"] = self.bound(value.end + timedelta(days=1))
        if value.isnull is not None:
            lookups[f"{self.field_name}__isnull"] = value.isnull
        return qs.filter(**lookups)


class SimpleFilter(django_filters.ChoiceFilter):
    """A Django ``SimpleListFilter``: its ``lookups()`` are the options, its ``queryset()`` filters."""

    parent: AdminFilterSet

    def __init__(self, list_filter: type[SimpleListFilter], **kwargs: Any) -> None:
        self.list_filter = list_filter
        self.instance: SimpleListFilter
        super().__init__(field_name=list_filter.parameter_name, label=list_filter.title, **kwargs)

    def bind(self, request: HttpRequest, data: QueryDict, model_admin: Any) -> None:
        params = {key: data.getlist(key) for key in data if key == self.field_name}
        self.instance = self.list_filter(request, params, model_admin.model, model_admin)
        label = str(self.label)
        self.extra.update(
            choices=[(str(value), title) for value, title in self.instance.lookup_choices],
            empty_label=_("All"),
            widget=Select(**_floating(label)),
        )

    @property
    def field(self) -> forms.Field:
        field = super().field
        field.label = ""
        return field

    def filter(self, qs: QuerySet[Any], value: str) -> QuerySet[Any]:
        # Django calls queryset() whether or not the filter has a value, so a filter can apply a default.
        return self.instance.queryset(self.parent.request, qs) or qs

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        # Django's own count of each lookup: rows of qs that queryset() keeps with that value set.
        expressions = self.instance.get_facet_counts("pk", qs)
        counts = qs.aggregate(**expressions) if expressions else {}
        return {
            str(value): counts[f"{index}__c"]
            for index, (value, _title) in enumerate(self.instance.lookup_choices)
            if f"{index}__c" in counts
        }


class AdminFilterSet(django_filters.FilterSet):
    """The search box and the filters of one changelist, bound to its request.

    Each filter has ``params`` (the keys it reads), ``null_param`` (the ``__isnull`` behind its
    option for rows without a value) and ``spawns_duplicates`` (its lookup crosses a to-many join)."""

    may_have_duplicates = False
    base_filters: ClassVar[dict[str, django_filters.Filter]]
    request: HttpRequest

    def __init__(self, data: QueryDict, queryset: QuerySet[Any], *, request: HttpRequest, model_admin: Any) -> None:
        self.model_admin = model_admin
        super().__init__(data, queryset, request=request)
        # The form reads its own inputs; Django's parameters turn into their values first.
        self.data = data.copy()
        for name, filter_ in self.filters.items():
            if isinstance(filter_, SimpleFilter):
                filter_.bind(request, data, model_admin)
            null_param = filter_.null_param
            if null_param and not data.get(name) and _truthy(data.get(null_param, "")):
                self.data[name] = NULL_VALUE
            if reader := getattr(filter_, "read_params", None):
                reader(name, data, self.data)

    @classmethod
    def claimed_params(cls, data: QueryDict) -> set[str]:
        """The keys of ``data`` that a filter reads; Django's changelist applies the rest as lookups.

        An ``__isnull`` counts only while true, the one value a filter's option writes."""
        keys: set[str] = set()
        for name, filter_ in cls.base_filters.items():
            if claimed := getattr(filter_, "claimed_params", None):
                keys |= claimed(name, data)
                continue
            keys |= {key for key in filter_.params if key in data}  # ty: ignore[unresolved-attribute]
            null_param = filter_.null_param  # ty: ignore[unresolved-attribute]
            if null_param and _truthy(data.get(null_param, "")):
                keys.add(null_param)
        return keys

    def written_params(self) -> list[tuple[str, str]]:
        """The filters' values as Django's list filters write them; a value the form rejects stays as given."""
        form = self.form
        form.is_valid()
        pairs: list[tuple[str, str]] = []
        for name, filter_ in self.filters.items():
            if name == SEARCH_VAR:
                continue
            writer = getattr(filter_, "written_params", None)
            if writer is not None and name not in form.errors:
                pairs += writer(name, self.data)
                continue
            null_param = filter_.null_param
            for key in filter_.params:
                for value in self.data.getlist(key):
                    if value == NULL_VALUE and null_param:
                        pairs.append((null_param, "True"))
                    elif value != "":
                        pairs.append((key, value))
        return pairs

    def search(self, queryset: QuerySet[Any], name: str, value: str) -> QuerySet[Any]:
        queryset, duplicates = self.model_admin.get_search_results(self.request, queryset, value)
        self.may_have_duplicates |= duplicates
        return queryset

    @property
    def form(self) -> forms.Form:
        if not hasattr(self, "_form"):
            form = super().form
            # A django-filter range the admin declares gets the same field as the date ranges.
            for field in form.fields.values():
                if type(field.widget) is RangeWidget:
                    field.widget = _FloatingRangeWidget(field.label)
                    field.label = ""
        return self._form

    def filter_queryset(self, queryset: QuerySet[Any], *, exclude: str | None = None) -> QuerySet[Any]:
        """The rows the search and the filters keep; ``exclude`` names one filter to skip."""
        for name, value in self.form.cleaned_data.items():
            if name == exclude:
                continue
            filter_ = self.filters[name]
            if filter_.spawns_duplicates and value not in (None, "", [], ()):
                self.may_have_duplicates = True
            queryset = filter_.filter(queryset, value)
        return queryset

    def facet_counts(self, name: str) -> dict[str, int] | None:
        """Rows per option of one filter, with the search and the other filters applied, as Django's facets count.

        None for a filter without counts, such as a date range, and for a form with errors.
        """
        counter = getattr(self.filters[name], "facet_counts", None)
        if counter is None or not self.is_valid():
            return None
        duplicates, self.may_have_duplicates = self.may_have_duplicates, False
        queryset = self.filter_queryset(self.queryset.all(), exclude=name)
        if self.may_have_duplicates:
            queryset = self.queryset.filter(pk__in=queryset.values("pk"))
        self.may_have_duplicates = duplicates
        return counter(queryset)


def _bind(
    filter_: django_filters.Filter, params: tuple[str, ...], *, null_param: str | None = None, spawns: bool = False
) -> django_filters.Filter:
    filter_.params = params  # ty: ignore[unresolved-attribute]
    filter_.null_param = null_param  # ty: ignore[unresolved-attribute]
    filter_.spawns_duplicates = spawns  # ty: ignore[unresolved-attribute]
    return filter_


def _list_filter_class(model_field: Any) -> type[FieldListFilter]:
    """The filter Django's admin picks for a field name, tested in the order Django registers them."""
    if model_field.remote_field:
        return RelatedFieldListFilter
    if isinstance(model_field, models.BooleanField):
        return BooleanFieldListFilter
    if model_field.choices:
        return ChoicesFieldListFilter
    if isinstance(model_field, models.DateField):
        return DateFieldListFilter
    return FieldListFilter


def _field_filter(model: type[models.Model], path: str, kind: type[FieldListFilter] | None) -> tuple[str, Any]:
    """The filter of a field path, under the parameter names of Django's filter of that kind."""
    model_field: Any = get_fields_from_path(model, path)[-1]
    kind = kind or _list_filter_class(model_field)
    spawns = lookup_spawns_duplicates(model._meta, path)
    isnull = f"{path}__isnull"
    if issubclass(kind, EmptyFieldListFilter):
        name = f"{path}__isempty"
        return name, _bind(EmptyFilter(field_name=path), (name,), spawns=spawns)
    if issubclass(kind, RelatedFieldListFilter):
        name = f"{path}__{model_field.target_field.name}__exact"
        filter_ = RelatedFilter(field_name=path)
        filter_.related_only = issubclass(kind, RelatedOnlyFieldListFilter)
        empty = model_field.null or model_field.many_to_many
        return name, _bind(filter_, (name,), null_param=isnull if empty else None, spawns=spawns)
    if issubclass(kind, BooleanFieldListFilter):
        name = f"{path}__exact"
        return name, _bind(BooleanFilter(field_name=path), (name,), null_param=isnull if model_field.null else None)
    if issubclass(kind, ChoicesFieldListFilter):
        name = f"{path}__exact"
        has_none = bool(dict(model_field.flatchoices).get(None))
        return name, _bind(ChoiceFilter(field_name=path), (name,), null_param=isnull if has_none else None)
    if issubclass(kind, DateFieldListFilter):
        lookups = ("gte", "lt", "lte", "year", "month", "day")
        params = tuple(f"{path}__{lookup}" for lookup in lookups)
        return path, _bind(DateRangeFilter(field_name=path), params, null_param=isnull if model_field.null else None)
    # AllValuesFieldListFilter and the like: the field's value under its own name.
    if model_field.flatchoices:
        filter_ = ChoiceFilter(field_name=path)
    else:
        filter_ = AdminFilterSet.filter_for_field(model_field, path, "exact")
    return path, _bind(filter_, (path,), spawns=spawns)


def _declared(filter_: Any, model: type[models.Model]) -> tuple[str, Any]:
    """A django-filter ``Filter``, named by its lookup; its inputs carry the widget's suffixes."""
    path = filter_.field_name
    name = path if filter_.lookup_expr == "exact" else f"{path}{LOOKUP_SEP}{filter_.lookup_expr}"
    widget = filter_.extra.get("widget") or filter_.field_class.widget
    widget_class: Any = widget if isinstance(widget, type) else type(widget)
    if widget_class is RangeWidget:
        widget_class = _FloatingRangeWidget
    params: tuple[str, ...] = (name,)
    if issubclass(widget_class, SuffixedMultiWidget):
        params = tuple(f"{name}_{suffix}" if suffix else name for suffix in widget_class.suffixes)
    return name, _bind(filter_, params, spawns=lookup_spawns_duplicates(model._meta, path))


def _filter_for(item: Any, model_admin: Any) -> tuple[str, Any]:
    """The parameter name of a ``list_filter`` entry and its filter."""
    model = model_admin.model
    if isinstance(item, str):
        return _field_filter(model, item, None)
    if isinstance(item, django_filters.Filter):
        return _declared(copy.deepcopy(item), model)
    if isinstance(item, type) and issubclass(item, SimpleListFilter):
        name = cast("str", item.parameter_name)
        return name, _bind(SimpleFilter(item), (name,))
    if isinstance(item, tuple | list) and len(item) == 2:  # noqa: PLR2004
        path, kind = item
        if isinstance(kind, type) and issubclass(kind, django_filters.Filter):
            return _declared(kind(field_name=path), model)
        if isinstance(kind, type) and issubclass(kind, FieldListFilter):
            return _field_filter(model, path, kind)
    msg = f"{type(model_admin).__name__}.list_filter: {item!r} is not a field name, Filter or SimpleListFilter."
    raise TypeError(msg)


def list_filter_path(item: Any) -> Any:
    """What Django's ``lookup_allowed`` reads from a ``list_filter`` entry: a ``Filter`` gives its field path."""
    return item.field_name if isinstance(item, django_filters.Filter) else item


def build_filterset(model_admin: Any, list_filter: Any, search_fields: Any) -> type[AdminFilterSet] | None:
    """The filterset class of one admin; None for a list that neither searches nor filters."""
    declared: dict[str, Any] = {}
    if search_fields:
        search = django_filters.CharFilter(
            method="search",
            label=_("Search"),
            widget=SearchInput(attrs={"placeholder": _("Search"), "aria-label": _("Search")}),
        )
        declared[SEARCH_VAR] = _bind(search, ())
    for item in list_filter:
        name, filter_ = _filter_for(item, model_admin)
        declared[name] = filter_
    if not declared:
        return None
    meta = type("Meta", (), {"model": model_admin.model, "fields": [], "form": FormworkForm})
    attrs = {**declared, "Meta": meta, "__module__": type(model_admin).__module__}
    filterset = cast("type[AdminFilterSet]", type(f"{type(model_admin).__name__}FilterSet", (AdminFilterSet,), attrs))
    # django-filter sorts declared filters by creation; the bar keeps list_filter's order.
    filterset.base_filters = {name: filterset.base_filters[name] for name in declared}
    return filterset
