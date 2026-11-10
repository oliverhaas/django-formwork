"""The changelist's filter bar: a django-filter ``FilterSet`` built from ``list_filter``.

An entry is a field name, a ``django_filters.Filter`` with its ``field_name`` set, a
``SimpleListFilter`` subclass, or ``(field_name, EmptyFieldListFilter)`` and the like.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, ClassVar, cast

import django_filters
from django import forms
from django.contrib.admin.filters import (
    EmptyFieldListFilter,
    ListFilter,
    RelatedOnlyFieldListFilter,
    SimpleListFilter,
)
from django.contrib.admin.utils import get_fields_from_path
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django_filters.widgets import RangeWidget, SuffixedMultiWidget

from django_formwork.admin.widgets import date_input_format, relation_widget
from django_formwork.forms import FormworkForm
from django_formwork.widgets import DateRangePicker, SearchInput, Select

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet
    from django.http import HttpRequest, QueryDict
    from django.utils.safestring import SafeString

__all__ = ["SEARCH_VAR", "AdminFilterSet", "build_filterset", "list_filter_params"]

SEARCH_VAR = "q"


def _floating(label: object) -> dict[str, Any]:
    return {"attrs": {"placeholder": capfirst(str(label))}, "allow_clear": True, "floating": True}


class _FloatingDateRangePicker(DateRangePicker):
    """The range picker with the filter's name on its border, as the select filters show theirs.

    The dates show as the date fields of the change form write them. The calendar offers the
    ranges of Django's date filter: today, the past 7 days, this month and this year.
    """

    def __init__(self, label: object) -> None:
        super().__init__(format=date_input_format()[1], presets=True)
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
    """django-filter's min and max inputs drawn as one field, with the filter's name on its border."""

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


class _FieldFilterMixin:
    """Picks the control from the model field it filters, after the label is known."""

    model: type[models.Model]
    field_name: str
    label: Any
    extra: dict[str, Any]
    parent: AdminFilterSet

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        return {}

    @property
    def field(self) -> forms.Field:
        if not hasattr(self, "_field"):
            model_field = get_fields_from_path(self.model, self.field_name)[-1]
            if self.label is None:
                self.label = getattr(model_field, "verbose_name", self.field_name)
            self.extra = self.field_defaults(model_field) | self.extra
            field = super().field  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
            # The control floats the filter's name, so the field draws no label row.
            field.label = ""
            return field
        return super().field  # type: ignore[misc]  # ty: ignore[unresolved-attribute]


class BooleanFilter(_FieldFilterMixin, django_filters.BooleanFilter):
    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        choices = [("", _("All")), ("true", _("Yes")), ("false", _("No"))]
        return {"widget": Select(choices=choices, show_search=False, **_floating(self.label))}

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        rows = qs.order_by().values_list(self.field_name).annotate(count=_count())
        return {"true" if value else "false": count for value, count in rows if value is not None}


class ChoiceFilter(_FieldFilterMixin, django_filters.ChoiceFilter):
    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        return {"choices": model_field.flatchoices, "empty_label": _("All"), "widget": Select(**_floating(self.label))}

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        rows = qs.order_by().values_list(self.field_name).annotate(count=_count())
        return {str(value): count for value, count in rows if value is not None}


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
        queryset = related._default_manager.all()
        if self.related_only:
            # Only rows the list points at, as RelatedOnlyFieldListFilter offers.
            used = model_admin.get_queryset(self.parent.request).values(self.field_name)
            queryset = queryset.filter(pk__in=used)
        direct = LOOKUP_SEP not in self.field_name
        searchable = direct and not self.related_only and model_admin.admin_site.is_searchable(related)
        # One row, as Django's related filter picks, a many-to-many relation included.
        widget = relation_widget(
            model_field, model_admin.admin_site, searchable=searchable, multiple=False, **_floating(self.label)
        )
        return {"queryset": queryset, "widget": widget}

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        rows = qs.order_by().values_list(f"{self.field_name}{LOOKUP_SEP}pk").annotate(count=_count())
        return {str(value): count for value, count in rows if value is not None}


class EmptyFilter(_FieldFilterMixin, django_filters.BooleanFilter):
    """Whether the field is empty, as ``EmptyFieldListFilter`` asks."""

    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        choices = [("", _("All")), ("true", _("Empty")), ("false", _("Not empty"))]
        return {"widget": Select(choices=choices, show_search=False, **_floating(self.label))}

    def _empty(self) -> models.Q:
        model_field = get_fields_from_path(self.model, self.field_name)[-1]
        empty = models.Q(**{f"{self.field_name}__isnull": True})
        if getattr(model_field, "empty_strings_allowed", False) and not model_field.is_relation:
            empty |= models.Q(**{self.field_name: ""})
        return empty

    def filter(self, qs: QuerySet[Any], value: bool | None) -> QuerySet[Any]:
        if value is None:
            return qs
        empty = self._empty()
        return qs.filter(empty) if value else qs.exclude(empty)

    def facet_counts(self, qs: QuerySet[Any]) -> dict[str, int]:
        empty = self._empty()
        return qs.aggregate(
            true=models.Count("pk", filter=empty, distinct=True),
            false=models.Count("pk", filter=~empty, distinct=True),
        )


class DateRangeFilter(_FieldFilterMixin, django_filters.DateFromToRangeFilter):
    def field_defaults(self, model_field: Any) -> dict[str, Any]:
        return {"widget": _FloatingDateRangePicker(self.label)}


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
    """The search box and the filters of one changelist, bound to its request."""

    FILTER_DEFAULTS: Mapping[Any, dict[str, Any]] = {
        **django_filters.FilterSet.FILTER_DEFAULTS,
        models.BooleanField: {"filter_class": BooleanFilter},
        models.DateField: {"filter_class": DateRangeFilter},
        models.DateTimeField: {"filter_class": DateRangeFilter},
        models.ForeignKey: {"filter_class": RelatedFilter},
        models.OneToOneField: {"filter_class": RelatedFilter},
        models.ManyToManyField: {"filter_class": RelatedFilter},
    }

    may_have_duplicates = False
    base_filters: ClassVar[dict[str, django_filters.Filter]]
    request: HttpRequest

    def __init__(self, data: QueryDict, queryset: QuerySet[Any], *, request: HttpRequest, model_admin: Any) -> None:
        self.model_admin = model_admin
        super().__init__(data, queryset, request=request)
        for filter_ in self.filters.values():
            if isinstance(filter_, SimpleFilter):
                filter_.bind(request, data, model_admin)

    @classmethod
    def filter_for_lookup(cls, field: models.Field[Any, Any], lookup_type: str) -> tuple[Any, dict[str, Any]]:
        if getattr(field, "flatchoices", None) and lookup_type == "exact":
            return ChoiceFilter, {}
        return super().filter_for_lookup(field, lookup_type)

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
            if isinstance(filter_, SimpleFilter):
                queryset = filter_.filter(queryset, value)
                continue
            if getattr(filter_, "distinct", False) and value not in (None, "", [], ()):
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


def _declared(item: Any, model_admin: Any) -> tuple[str, django_filters.Filter | None]:
    """The parameter name of a ``list_filter`` entry, and its filter unless picked by field type."""
    if isinstance(item, str):
        return item, None
    if isinstance(item, django_filters.Filter):
        return item.field_name, copy.deepcopy(item)
    if isinstance(item, type) and issubclass(item, SimpleListFilter):
        return cast("str", item.parameter_name), SimpleFilter(item)
    if isinstance(item, tuple) and len(item) == 2:  # noqa: PLR2004
        name, kind = item
        if kind is EmptyFieldListFilter or (isinstance(kind, type) and issubclass(kind, EmptyFieldListFilter)):
            return f"{name}__isempty", EmptyFilter(field_name=name)
        if kind is RelatedOnlyFieldListFilter:
            filter_ = RelatedFilter(field_name=name)
            filter_.related_only = True
            return name, filter_
        if isinstance(kind, type) and issubclass(kind, django_filters.Filter):
            return name, kind(field_name=name)
        if isinstance(kind, type) and issubclass(kind, ListFilter):
            # Django's field list filters render their own choices; the field's type picks ours.
            return name, None
    msg = f"{type(model_admin).__name__}.list_filter: {item!r} is not a field name, Filter or SimpleListFilter."
    raise TypeError(msg)


def build_filterset(model_admin: Any, list_filter: Any, search_fields: Any) -> type[AdminFilterSet] | None:
    """The filterset class of one admin; None for a list that neither searches nor filters."""
    declared: dict[str, Any] = {}
    fields: list[str] = []
    order: list[str] = [SEARCH_VAR] if search_fields else []
    if search_fields:
        declared[SEARCH_VAR] = django_filters.CharFilter(
            method="search",
            label=_("Search"),
            widget=SearchInput(attrs={"placeholder": _("Search"), "aria-label": _("Search")}),
        )
    for item in list_filter:
        name, filter_ = _declared(item, model_admin)
        order.append(name)
        if filter_ is None:
            fields.append(name)
        else:
            declared[name] = filter_
    if not declared and not fields:
        return None
    meta = type("Meta", (), {"model": model_admin.model, "fields": fields, "form": FormworkForm})
    attrs = {**declared, "Meta": meta, "__module__": type(model_admin).__module__}
    filterset = cast("type[AdminFilterSet]", type(f"{type(model_admin).__name__}FilterSet", (AdminFilterSet,), attrs))
    # django-filter puts the Meta fields before the declared filters; the bar keeps list_filter's order.
    filterset.base_filters = {name: filterset.base_filters[name] for name in order}
    return filterset


def list_filter_params(filterset_class: type[AdminFilterSet] | None) -> dict[str, tuple[str, ...]]:
    """Each filter's name to the query parameters its control submits."""
    if filterset_class is None:
        return {}
    params: dict[str, tuple[str, ...]] = {}
    for name, filter_ in filterset_class.base_filters.items():
        params[name] = tuple(f"{name}{suffix}" for suffix in _param_suffixes(filter_))
    return params


def _param_suffixes(filter_: django_filters.Filter) -> tuple[str, ...]:
    if isinstance(filter_, DateRangeFilter):
        return ("_0", "_1")
    widget = filter_.extra.get("widget") or filter_.field_class.widget
    widget_class: Any = widget if isinstance(widget, type) else type(widget)
    if issubclass(widget_class, SuffixedMultiWidget):
        return tuple(f"_{suffix}" if suffix else "" for suffix in widget_class.suffixes)
    return ("",)
