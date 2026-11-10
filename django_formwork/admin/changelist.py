"""The state of one changelist request, read from ``request.GET``.

The parameters keep Django's names: ``q`` searches, ``p`` pages from 1, ``all`` shows
every row, ``o`` orders. ``o`` names a column (``-name`` descends), not a column index.
"""

from __future__ import annotations

import hashlib
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.contrib.admin.options import IS_FACETS_VAR, ShowFacets
from django.contrib.admin.utils import label_for_field, lookup_field, quote
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import InvalidPage
from django.db import models
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.http import urlencode
from django.utils.text import capfirst

from django_formwork.admin.cells import list_cell
from django_formwork.admin.filters import SEARCH_VAR, list_filter_params
from django_formwork.admin.paginator import EstimatedCountPaginator

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.core.paginator import Page
    from django.forms import BoundField
    from django.http import HttpRequest

    from django_formwork.admin.filters import AdminFilterSet

__all__ = ["ALL_VAR", "IS_FACETS_VAR", "ORDER_VAR", "PAGE_VAR", "PRESERVED_FILTERS_VAR", "SEARCH_VAR", "ChangeList"]

ALL_VAR = "all"
ORDER_VAR = "o"
PAGE_VAR = "p"
PRESERVED_FILTERS_VAR = "_changelist_filters"

# Characters of text after which a changelist column can wrap.
WRAP_AFTER = 40


class ChangeList:
    """One page of a model's list: its filters, ordering, rows and counts."""

    def __init__(self, request: HttpRequest, model_admin: Any, *, formset: Any = None) -> None:
        self.request = request
        self.model_admin = model_admin
        self.model = model_admin.model
        self.opts = self.model._meta
        self.list_display: list[str | Callable[..., Any]] = list(model_admin.get_list_display(request))
        self.list_display_links = model_admin.get_list_display_links(request, self.list_display)
        self.list_filter = model_admin.get_list_filter(request)
        self.search_fields = model_admin.get_search_fields(request)
        self.sortable_by = model_admin.get_sortable_by(request)
        self.list_per_page = model_admin.list_per_page
        self.list_max_show_all = model_admin.list_max_show_all
        self.list_editable = model_admin.list_editable
        self.search_help_text = model_admin.search_help_text
        self.root_queryset = model_admin.get_queryset(request)
        self.formset = formset
        self.title = capfirst(self.opts.verbose_name_plural)

    # Parameters

    @cached_property
    def filterset_class(self) -> type[AdminFilterSet] | None:
        return self.model_admin.get_filterset_class(request=self.request)

    @cached_property
    def filter_params(self) -> dict[str, tuple[str, ...]]:
        return list_filter_params(self.filterset_class)

    @cached_property
    def known_params(self) -> frozenset[str]:
        """Parameters this list reads; links and redirects drop every other one."""
        declared = {param for params in self.filter_params.values() for param in params}
        return frozenset({ORDER_VAR, PAGE_VAR, ALL_VAR, IS_FACETS_VAR, *declared})

    @cached_property
    def params(self) -> QueryDict:
        """``request.GET`` narrowed to the known parameters."""
        params = QueryDict(mutable=True)
        for key, values in self.request.GET.lists():
            if key in self.known_params:
                params.setlist(key, values)
        return params

    @cached_property
    def state_key(self) -> str:
        """Changes with the parameters, so a filtered or sorted list starts with nothing selected."""
        params = self.params.copy()
        params.pop(IS_FACETS_VAR, None)
        return hashlib.blake2s(params.urlencode().encode(), digest_size=4).hexdigest()

    def get_query_string(self, new_params: dict[str, Any] | None = None, remove: list[str] | None = None) -> str:
        """The list's query string with ``new_params`` set; a None value or a ``remove`` entry drops a key."""
        params = self.params.copy()
        for key in remove or ():
            params.pop(key, None)
        for key, value in (new_params or {}).items():
            if value is None:
                params.pop(key, None)
            elif isinstance(value, list | tuple):
                params.setlist(key, [str(item) for item in value])
            else:
                params[key] = str(value)
        query = params.urlencode()
        return f"?{query}" if query else self.request.path

    # Filtering

    @cached_property
    def filterset(self) -> AdminFilterSet | None:
        if self.filterset_class is None:
            return None
        return self.filterset_class(
            self.request.GET,
            self.root_queryset,
            request=self.request,
            model_admin=self.model_admin,
        )

    @property
    def filter_form(self) -> Any:
        return self.filterset.form if self.filterset is not None else None

    @cached_property
    def search_field(self) -> BoundField | None:
        form = self.filter_form
        return form[SEARCH_VAR] if form is not None and SEARCH_VAR in form.fields else None

    @cached_property
    def add_facets(self) -> bool:
        """Whether each filter option shows its row count, after ``show_facets`` and ``_facets``."""
        show_facets = self.model_admin.show_facets
        return show_facets is ShowFacets.ALWAYS or (
            show_facets is ShowFacets.ALLOW and IS_FACETS_VAR in self.request.GET
        )

    @property
    def is_facets_optional(self) -> bool:
        return self.model_admin.show_facets is ShowFacets.ALLOW

    @cached_property
    def filter_fields(self) -> list[BoundField]:
        form = self.filter_form
        if form is None:
            return []
        names = [name for name in self.filter_params if name != SEARCH_VAR]
        if self.add_facets and self.filterset is not None:
            for name in names:
                counts = self.filterset.facet_counts(name)
                if counts is not None:
                    form.fields[name].widget.counts = counts
        return [form[name] for name in names]

    @cached_property
    def query(self) -> str:
        return self.request.GET.get(SEARCH_VAR, "").strip() if self.search_fields else ""

    @cached_property
    def active_filter_count(self) -> int:
        """How many filters narrow the list; the search box does not count."""
        if self.filterset is None:
            return 0
        form = self.filter_form
        form.is_valid()
        return sum(
            form.cleaned_data.get(name) not in (None, "", [], ()) for name in self.filter_params if name != SEARCH_VAR
        )

    @property
    def has_filters(self) -> bool:
        return bool(self.filter_fields)

    @property
    def has_active_filters(self) -> bool:
        return bool(self.active_filter_count)

    @cached_property
    def export_query(self) -> str:
        """The filters, search and ordering an export of this list keeps; the page goes."""
        params = self.params.copy()
        for key in (PAGE_VAR, ALL_VAR, IS_FACETS_VAR):
            params.pop(key, None)
        return params.urlencode()

    @cached_property
    def clear_all_filters_qs(self) -> str:
        """The list without its filters; the search and the sort stay, as in Django."""
        filter_keys = [param for name, params in self.filter_params.items() if name != SEARCH_VAR for param in params]
        return self.get_query_string(remove=[*filter_keys, PAGE_VAR])

    @cached_property
    def queryset(self) -> models.QuerySet[Any]:
        """The filtered, searched and ordered rows, before paging."""
        queryset = self.root_queryset
        duplicates = False
        if self.filterset is not None:
            queryset = self.filterset.qs
            duplicates = self.filterset.may_have_duplicates
        if duplicates:
            # A pk subquery keeps the rows unique without DISTINCT over every selected column.
            queryset = self.root_queryset.filter(pk__in=queryset.values("pk"))
        queryset = self.apply_select_related(self.model_admin.get_changelist_queryset(self.request, queryset))
        return queryset.order_by(*self.ordering)

    def apply_select_related(self, queryset: models.QuerySet[Any]) -> models.QuerySet[Any]:
        """Join the relations the columns read.

        Django calls ``select_related()`` without arguments for a bare foreign key column,
        which follows every non-null relation five levels deep. This names each column's relation.
        """
        select_related = self.model_admin.list_select_related
        if select_related is True:
            return queryset.select_related()
        if select_related:
            return queryset.select_related(*select_related)
        related = []
        for name in self.list_display:
            if not isinstance(name, str):
                continue
            try:
                field = self.opts.get_field(name)
            except FieldDoesNotExist:
                continue
            if field.many_to_one or (field.one_to_one and field.concrete):
                related.append(name)
        return queryset.select_related(*related) if related else queryset

    # Ordering

    def order_field(self, name: str | Callable[..., Any]) -> str | models.expressions.BaseExpression | None:
        """What a column sorts by, None when it cannot sort."""
        if self.sortable_by is not None and name not in self.sortable_by:
            return None
        if callable(name):
            return getattr(name, "admin_order_field", None)
        try:
            field = self.opts.get_field(name)
        except FieldDoesNotExist:
            if name == "__str__":
                return None
            attr = getattr(self.model_admin, name, None) or getattr(self.model, name, None)
            if isinstance(attr, property) and hasattr(attr, "fget"):
                attr = attr.fget
            return getattr(attr, "admin_order_field", None)
        # A to-many column joins rows and repeats objects.
        if field.many_to_many or field.one_to_many:
            return None
        return field.name

    @cached_property
    def column_names(self) -> dict[str, str | Callable[..., Any]]:
        """``o`` values to the ``list_display`` entry they sort."""
        names: dict[str, str | Callable[..., Any]] = {}
        for entry in self.list_display:
            key = entry if isinstance(entry, str) else entry.__name__  # ty: ignore[unresolved-attribute]
            names[key] = entry
        return names

    @cached_property
    def current_order(self) -> str:
        """The requested ``o`` when a column sorts by it, else blank."""
        requested = self.request.GET.get(ORDER_VAR, "")
        column = self.column_names.get(requested.removeprefix("-"))
        if column is None or self.order_field(column) is None:
            return ""
        return requested

    @cached_property
    def ordering(self) -> list[Any]:
        """The requested column, then the admin's ordering, then the primary key so pages never overlap."""
        ordering: list[Any] = []
        if self.current_order:
            field = self.order_field(self.column_names[self.current_order.removeprefix("-")])
            descending = self.current_order.startswith("-")
            if isinstance(field, str):
                # An admin_order_field of "-name" sorts descending first, so a click flips it.
                flipped = descending != field.startswith("-")
                ordering.append(f"-{field.removeprefix('-')}" if flipped else field.removeprefix("-"))
            elif field is not None:
                ordering.append(field.desc() if descending else field.asc())
        ordering.extend(self.model_admin.get_ordering(self.request) or self.opts.ordering or ())
        pk_names = {"pk", "-pk", self.opts.pk.name, f"-{self.opts.pk.name}"}
        if not any(isinstance(item, str) and item in pk_names for item in ordering):
            ordering.append("-pk")
        return ordering

    # Paging and counts

    @cached_property
    def paginator(self) -> Any:
        return self.model_admin.get_paginator(self.request, self.queryset, self.list_per_page)

    @cached_property
    def result_count(self) -> int:
        return self.paginator.count

    @property
    def is_estimate(self) -> bool:
        return getattr(self.paginator, "is_estimate", False)

    @cached_property
    def full_result_count(self) -> int | None:
        """Every row before the filters, when the admin shows it and something filters."""
        if not self.model_admin.show_full_result_count or not (self.has_active_filters or self.query):
            return None
        # An order keeps the paginator from warning; COUNT(*) drops it again.
        return EstimatedCountPaginator(self.root_queryset.order_by("pk"), self.list_per_page).count

    @cached_property
    def show_all(self) -> bool:
        return ALL_VAR in self.request.GET and self.can_show_all

    @cached_property
    def can_show_all(self) -> bool:
        return not self.is_estimate and self.result_count <= self.list_max_show_all

    @cached_property
    def multi_page(self) -> bool:
        return self.result_count > self.list_per_page

    @cached_property
    def page(self) -> Page[Any]:
        if self.show_all:
            return self.model_admin.get_paginator(self.request, self.queryset, max(self.result_count, 1)).page(1)
        try:
            number = int(self.request.GET.get(PAGE_VAR, 1))
            return self.paginator.page(number)
        except ValueError, InvalidPage:
            return self.paginator.page(self.paginator.num_pages if self.request.GET.get(PAGE_VAR) else 1)

    @property
    def page_num(self) -> int:
        return self.page.number

    @cached_property
    def result_list(self) -> list[models.Model]:
        return list(self.page.object_list)

    def page_url(self, number: int) -> str:
        return self.get_query_string({PAGE_VAR: number if number > 1 else None, ALL_VAR: None})

    @cached_property
    def page_links(self) -> list[int | None]:
        """Page numbers around the current one, None where the run skips pages."""
        if self.show_all or not self.multi_page:
            return []
        return list(self.paginator.get_elided_page_range(self.page.number, on_each_side=2, on_ends=1))

    # Columns and rows

    @cached_property
    def links(self) -> set[str | Callable[..., Any]]:
        if self.list_display_links is None:
            return set()
        return set(self.list_display_links)

    def header_label(self, entry: str | Callable[..., Any]) -> str:
        if entry == "action_checkbox":
            return ""
        return str(capfirst(label_for_field(entry, self.model, self.model_admin, return_attr=False)))

    @cached_property
    def columns(self) -> list[dict[str, Any]]:
        """One header per ``list_display`` entry, with its sort link and direction."""
        current = self.current_order.removeprefix("-")
        columns = []
        for key, entry in self.column_names.items():
            column: dict[str, Any] = {
                "name": key,
                "label": self.header_label(entry),
                "sort_url": "",
                "direction": "",
                "numeric": self.is_numeric(entry),
                "linked": entry in self.links,
            }
            if self.order_field(entry) is not None:
                ascending = current == key and not self.current_order.startswith("-")
                column["sort_url"] = self.get_query_string({ORDER_VAR: f"-{key}" if ascending else key, PAGE_VAR: None})
                if current == key:
                    column["direction"] = "asc" if ascending else "desc"
            columns.append(column)
        return columns

    def is_numeric(self, entry: str | Callable[..., Any]) -> bool:
        if not isinstance(entry, str):
            return False
        try:
            field = self.opts.get_field(entry)
        except FieldDoesNotExist:
            return False
        numeric = (models.IntegerField, models.FloatField, models.DecimalField)
        return isinstance(field, numeric) and not getattr(field, "flatchoices", None) and not field.primary_key

    def url_for_result(self, result: models.Model) -> str:
        return reverse(
            f"{self.model_admin.admin_site.name}:{self.opts.app_label}_{self.opts.model_name}_change",
            args=(quote(result.pk),),
        )

    @cached_property
    def preserved_filters(self) -> str:
        """The list state a change page carries, so saving returns here."""
        if not self.model_admin.preserve_filters:
            return ""
        query = self.params.urlencode()
        return urlencode({PRESERVED_FILTERS_VAR: query}) if query else ""

    def change_url(self, result: models.Model) -> str:
        url = self.url_for_result(result)
        return f"{url}?{self.preserved_filters}" if self.preserved_filters else url

    @cached_property
    def editable_forms(self) -> dict[Any, Any]:
        if self.formset is None:
            return {}
        return {form.instance.pk: form for form in self.formset.forms}

    @cached_property
    def rows(self) -> list[dict[str, Any]]:
        """The page, one entry per object with its cells and its link."""
        rows: list[dict[str, Any]] = []
        can_link = self.model_admin.has_view_or_change_permission(self.request)
        for index, obj in enumerate(self.result_list):
            url = self.change_url(obj) if can_link else ""
            form = self.editable_forms.get(obj.pk)
            cells: list[dict[str, Any]] = []
            for key, entry in self.column_names.items():
                linked = bool(url) and entry in self.links
                cell: dict[str, Any] = {"name": key, "link": url if linked else "", "field": None}
                if form is not None and key in self.list_editable and not linked:
                    cell["field"] = form[key]
                else:
                    cell.update(list_cell(entry, obj, self.model_admin))
                cell["numeric"] = self.is_numeric(entry)
                cells.append(cell)
            rows.append({"pk": obj.pk, "value": str(obj.pk), "index": index, "cells": cells, "form": form})
        # Only a column with long text on this page wraps; names, dates and badges keep one line.
        wrapping = {
            cell["name"]
            for row in rows
            for cell in row["cells"]
            if cell.get("kind") in {"text", "html"} and len(strip_tags(cell["text"])) > WRAP_AFTER
        }
        for row in rows:
            for cell in row["cells"]:
                cell["wrap"] = cell["name"] in wrapping
        return rows

    @cached_property
    def pk_attname(self) -> str:
        return self.opts.pk.attname

    def lookup_field(self, entry: str | Callable[..., Any], obj: models.Model) -> Any:
        return lookup_field(entry, obj, self.model_admin)
