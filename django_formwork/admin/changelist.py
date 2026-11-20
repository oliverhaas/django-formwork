"""The state of one changelist request, read from ``request.GET``.

The parameters keep Django's names and lookups. ``o`` numbers the columns as Django's does,
so ``o=2.-1`` sorts by column 2, then by column 1 descending. A lookup that no filter reads
narrows the rows, as in Django's changelist."""

from __future__ import annotations

import hashlib
from functools import cached_property
from typing import TYPE_CHECKING, Any, NamedTuple

from django.contrib.admin.exceptions import DisallowedModelAdminLookup, DisallowedModelAdminToField
from django.contrib.admin.options import IS_FACETS_VAR, IncorrectLookupParameters, ShowFacets
from django.contrib.admin.utils import (
    build_q_object_from_lookup_parameters,
    label_for_field,
    lookup_field,
    lookup_spawns_duplicates,
    prepare_lookup_value,
    quote,
)
from django.contrib.admin.views.main import ERROR_FLAG, IGNORED_PARAMS
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured, SuspiciousOperation
from django.core.paginator import InvalidPage
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import Combinable, F, OrderBy, OuterRef, Subquery
from django.http import QueryDict
from django.urls import reverse
from django.utils.formats import number_format
from django.utils.html import strip_tags
from django.utils.http import urlencode
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from django_formwork.admin.cells import annotate_rows, display_annotations, display_attr, list_cell, list_field
from django_formwork.admin.filters import SEARCH_VAR
from django_formwork.admin.paginator import EstimatedCountPaginator, PageLink, page_links
from django_formwork.admin.widgets import IS_POPUP_VAR, TO_FIELD_VAR
from django_formwork.widgets import Select

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from django.core.paginator import Page
    from django.forms import BoundField
    from django.http import HttpRequest

    from django_formwork.admin.filters import AdminFilterSet

__all__ = [
    "ALL_VAR",
    "ERROR_FLAG",
    "IS_FACETS_VAR",
    "ORDER_VAR",
    "PAGE_VAR",
    "PER_PAGE_VAR",
    "PRESERVED_FILTERS_VAR",
    "SEARCH_VAR",
    "BarFilter",
    "ChangeList",
]

ALL_VAR = "all"
ORDER_VAR = "o"
PAGE_VAR = "p"
PER_PAGE_VAR = "per_page"
PRESERVED_FILTERS_VAR = "_changelist_filters"

# Characters of text after which a changelist column can wrap.
WRAP_AFTER = 40

# What a filter's cleaned value is while it does not narrow the list.
_EMPTY: tuple[object, ...] = (None, "", [], ())


class BarFilter(NamedTuple):
    """One filter of the bar."""

    name: str
    label: str
    field: BoundField
    # It has a value, so it narrows the list.
    active: bool


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
        self.list_max_show_all = model_admin.list_max_show_all
        # The page sizes a viewer can pick; the admin's own size is always one of them.
        options = model_admin.list_per_page_options
        self.list_per_page_options = sorted({*options, model_admin.list_per_page}) if options else []
        per_page = request.GET.get(PER_PAGE_VAR, "")
        picked = per_page.isdigit() and int(per_page) in self.list_per_page_options
        self.list_per_page = int(per_page) if picked else model_admin.list_per_page
        # A size the admin does not offer is dropped, so the list's links don't carry it on.
        self.per_page_param = per_page if picked or (per_page == ALL_VAR and self.list_per_page_options) else None
        # A list in the related-object dialog picks a row for the relation that opened it, and edits none.
        self.is_popup = IS_POPUP_VAR in request.GET
        self.to_field = request.GET.get(TO_FIELD_VAR) or None
        if self.to_field and not model_admin.to_field_allowed(request, self.to_field):
            msg = f"The field {self.to_field} cannot be referenced."
            raise DisallowedModelAdminToField(msg)
        self.list_editable = () if self.is_popup else model_admin.list_editable
        self.search_help_text = model_admin.search_help_text
        self.root_queryset = model_admin.get_queryset(request)
        self.formset = formset
        self.title = capfirst(self.opts.verbose_name_plural)

    # Parameters

    @cached_property
    def filterset_class(self) -> type[AdminFilterSet] | None:
        return self.model_admin.get_filterset_class(request=self.request)

    @cached_property
    def lookup_params(self) -> dict[str, list[str]]:
        """Every parameter but the list's own, each checked with ``lookup_allowed`` as Django's changelist does."""
        params = {
            key: values
            for key, values in self.request.GET.lists()
            if key not in IGNORED_PARAMS and key not in {PAGE_VAR, PER_PAGE_VAR, ERROR_FLAG}
        }
        for key, values in params.items():
            for value in values:
                if not self.model_admin.lookup_allowed(key, value, self.request):
                    msg = f"Filtering by {key} not allowed"
                    raise DisallowedModelAdminLookup(msg)
        return params

    @cached_property
    def remaining_lookups(self) -> dict[str, list[str]]:
        """The lookups no filter reads, such as ``?author__id__exact=3`` from a link elsewhere."""
        claimed = self.filterset_class.claimed_params(self.request.GET) if self.filterset_class else set()
        return {key: values for key, values in self.lookup_params.items() if key not in claimed}

    @cached_property
    def lookups_may_have_duplicates(self) -> bool:
        return any(lookup_spawns_duplicates(self.opts, key) for key in self.remaining_lookups)

    @cached_property
    def lookup_queryset(self) -> models.QuerySet[Any]:
        """The admin's rows narrowed by the remaining lookups; the filters start from these.

        A lookup that names no field or takes no such value raises ``IncorrectLookupParameters``."""
        if not self.remaining_lookups:
            return self.root_queryset
        lookups: dict[str, Iterable[object]] = {
            key: prepare_lookup_value(key, values) for key, values in self.remaining_lookups.items()
        }
        try:
            return self.root_queryset.filter(build_q_object_from_lookup_parameters(lookups))
        except SuspiciousOperation, ImproperlyConfigured:
            raise
        except Exception as error:
            # Django's changelist validates the lookups the same way: any other error means a bad URL.
            raise IncorrectLookupParameters(error) from error

    @cached_property
    def params(self) -> QueryDict:
        """The list's state as Django's changelist writes it: filters, other lookups, sort, page and search."""
        params = QueryDict(mutable=True)
        if self.filterset is not None:
            for key, value in self.filterset.written_params():
                params.appendlist(key, value)
        for key, values in self.remaining_lookups.items():
            params.setlist(key, values)
        own = [ORDER_VAR, PAGE_VAR, ALL_VAR, IS_FACETS_VAR, *([SEARCH_VAR] if self.search_fields else [])]
        for key in own:
            if key in self.request.GET:
                params.setlist(key, self.request.GET.getlist(key))
        if self.per_page_param:
            params[PER_PAGE_VAR] = self.per_page_param
        for key, value in self.popup_params.items():
            params[key] = value
        return params

    @cached_property
    def popup_params(self) -> dict[str, str]:
        """``_popup`` and ``_to_field`` of a list in the related-object dialog; its links and its add page keep them."""
        if not self.is_popup:
            return {}
        return {IS_POPUP_VAR: "1", **({TO_FIELD_VAR: self.to_field} if self.to_field else {})}

    @staticmethod
    def encode(params: QueryDict) -> str:
        """The query string of ``params``, sorted by key as Django's ``get_query_string`` writes it."""
        return urlencode(sorted(params.lists()), doseq=True)

    @cached_property
    def encoded_params(self) -> str:
        return self.encode(self.params)

    @cached_property
    def state_key(self) -> str:
        """Changes with the parameters, so a filtered or sorted list starts with nothing selected."""
        params = self.params.copy()
        params.pop(IS_FACETS_VAR, None)
        return hashlib.blake2s(self.encode(params).encode(), digest_size=4).hexdigest()

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
        query = self.encode(params)
        return f"?{query}" if query else self.request.path

    # Filtering

    @cached_property
    def filterset(self) -> AdminFilterSet | None:
        if self.filterset_class is None:
            return None
        return self.filterset_class(
            self.request.GET,
            self.lookup_queryset,
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
    def filter_names(self) -> list[str]:
        """The form fields of the filter bar, in ``list_filter`` order."""
        if self.filterset_class is None:
            return []
        return [name for name in self.filterset_class.base_filters if name != SEARCH_VAR]

    @cached_property
    def filter_fields(self) -> list[BoundField]:
        form = self.filter_form
        if form is None:
            return []
        names = self.filter_names
        if self.add_facets and self.filterset is not None:
            for name in names:
                counts = self.filterset.facet_counts(name)
                if counts is not None:
                    form.fields[name].widget.counts = counts
        return [form[name] for name in names]

    @cached_property
    def bar_filters(self) -> list[BarFilter]:
        """The filters of the bar in ``list_filter`` order, each with the name the More menu lists it under."""
        fields = self.filter_fields
        if not fields or self.filterset is None:
            return []
        form = self.filter_form
        form.is_valid()
        filters = self.filterset.filters
        return [
            BarFilter(
                name=field.name,
                label=capfirst(str(filters[field.name].label)),
                field=field,
                active=form.cleaned_data.get(field.name) not in _EMPTY,
            )
            for field in fields
        ]

    @cached_property
    def query(self) -> str:
        return self.request.GET.get(SEARCH_VAR, "").strip() if self.search_fields else ""

    @cached_property
    def active_filter_count(self) -> int:
        """How many filters narrow the list; the search box does not count."""
        return sum(filter_.active for filter_ in self.bar_filters)

    @property
    def has_filters(self) -> bool:
        return bool(self.filter_fields)

    @property
    def has_active_filters(self) -> bool:
        return bool(self.active_filter_count)

    @property
    def is_filtered(self) -> bool:
        """Whether the list shows fewer rows than the admin has: a filter, the search or another lookup narrows it."""
        return self.has_active_filters or bool(self.query) or bool(self.remaining_lookups)

    @cached_property
    def export_query(self) -> str:
        """The filters, search and ordering an export of this list keeps; the page goes."""
        params = self.params.copy()
        for key in (PAGE_VAR, ALL_VAR, IS_FACETS_VAR):
            params.pop(key, None)
        return self.encode(params)

    @cached_property
    def slot_query(self) -> str:
        """The filters and the search that a slot of this list reads; a new sort or page leaves it as it is."""
        params = self.params.copy()
        for key in (ORDER_VAR, PAGE_VAR, ALL_VAR, IS_FACETS_VAR, PER_PAGE_VAR):
            params.pop(key, None)
        return self.encode(params)

    @cached_property
    def clear_all_filters_qs(self) -> str:
        """The list without the bar's filters; the other lookups, the search and the sort stay, as in Django."""
        written = [key for key, _value in self.filterset.written_params()] if self.filterset is not None else []
        return self.get_query_string(remove=[*written, PAGE_VAR])

    @cached_property
    def clear_search_qs(self) -> str:
        """The list without the search; the filters, the other lookups and the sort stay."""
        return self.get_query_string(remove=[SEARCH_VAR, PAGE_VAR])

    @cached_property
    def queryset(self) -> models.QuerySet[Any]:
        """The filtered, searched and ordered rows, before paging."""
        queryset = self.lookup_queryset
        duplicates = self.lookups_may_have_duplicates
        if self.filterset is not None:
            queryset = self.filterset.qs
            duplicates |= self.filterset.may_have_duplicates
        if duplicates:
            # A pk subquery keeps the rows unique without DISTINCT over every selected column.
            queryset = self.root_queryset.filter(pk__in=queryset.values("pk"))
        queryset = self.model_admin.get_changelist_queryset(self.request, queryset)
        return queryset.order_by(*self.ordering)

    # Ordering

    def order_field(self, name: str | Callable[..., Any] | None) -> str | models.expressions.BaseExpression | None:
        """What a column sorts by, None when it cannot sort."""
        if name is None:
            return None
        if self.sortable_by is not None and name not in self.sortable_by:
            return None
        if isinstance(name, str):
            try:
                field = self.opts.get_field(name)
            except FieldDoesNotExist:
                if LOOKUP_SEP in name and display_attr(name, self.model_admin) is None:
                    # A column that follows a relation, such as "author__name", sorts by that path.
                    return name
            else:
                # A to-many column joins rows and repeats objects.
                return None if field.many_to_many or field.one_to_many else field.name
        attr = display_attr(name, self.model_admin)
        ordering = getattr(attr, "admin_order_field", None)
        annotations = getattr(attr, "admin_annotations", {})
        if isinstance(ordering, str) and (annotation := ordering.removeprefix("-")) in annotations:
            # A subquery per row: an aggregate in order_by() needs annotate(), whose join the count would keep.
            rows = self.model._base_manager.filter(pk=OuterRef("pk")).order_by().values("pk")
            expression = Subquery(rows.annotate(**{annotation: annotations[annotation]}).values(annotation))
            return expression.desc() if ordering.startswith("-") else expression.asc()
        return ordering

    @cached_property
    def column_names(self) -> dict[str, str | Callable[..., Any]]:
        """``o`` values to the ``list_display`` entry they sort."""
        names: dict[str, str | Callable[..., Any]] = {}
        for entry in self.list_display:
            key = entry if isinstance(entry, str) else entry.__name__  # ty: ignore[unresolved-attribute]
            names[key] = entry
        return names

    @cached_property
    def column_offset(self) -> int:
        """Django counts the action checkbox as column 0, so ``o`` numbers the other columns from 1 while it shows."""
        return 1 if self.model_admin.get_actions(self.request) else 0

    def column_at(self, index: int) -> str | Callable[..., Any] | None:
        position = index - self.column_offset
        return self.list_display[position] if 0 <= position < len(self.list_display) else None

    @cached_property
    def sorted_columns(self) -> dict[int, str]:
        """The sorted columns as ``o`` numbers them, each ``asc`` or ``desc``, the first sort first.

        Without ``o``, the columns of the admin's ordering, which Django's changelist marks the same way.
        A blank ``o`` marks none, as in Django, while the rows keep the admin's ordering."""
        columns: dict[int, str] = {}
        if ORDER_VAR in self.request.GET:
            for part in self.request.GET[ORDER_VAR].split("."):
                _, sign, number = part.rpartition("-")
                try:
                    index = int(number)
                except ValueError:
                    continue
                column = self.column_at(index)
                if column is not None and self.order_field(column) is not None:
                    columns.setdefault(index, "desc" if sign else "asc")
            return columns
        for item in self.model_admin.get_ordering(self.request) or self.opts.ordering or ():
            if isinstance(item, Combinable | OrderBy):
                term: Any = item if isinstance(item, OrderBy) else item.asc()  # type: ignore[attr-defined]
                if not isinstance(term.expression, F):
                    continue
                name, direction = term.expression.name, "desc" if term.descending else "asc"  # type: ignore[attr-defined]
            else:
                name, direction = item.removeprefix("-"), "desc" if item.startswith("-") else "asc"
            for position, entry in enumerate(self.list_display):
                if self.order_field(entry) == name:
                    columns.setdefault(position + self.column_offset, direction)
                    break
        return columns

    @cached_property
    def current_order(self) -> str | None:
        """The requested ``o`` with the columns it can sort, None without one."""
        if ORDER_VAR not in self.request.GET:
            return None
        return ".".join(
            f"{'-' if direction == 'desc' else ''}{index}" for index, direction in self.sorted_columns.items()
        )

    def sort_term(self, index: int, direction: str) -> Any:
        """The ``order_by()`` term of a column, as Django's changelist builds it."""
        field: Any = self.order_field(self.column_at(index))
        descending = direction == "desc"
        if isinstance(field, OrderBy):
            if not descending:
                return field
            field = field.copy()
            field.reverse_ordering()
            return field
        if isinstance(field, str):
            # An admin_order_field of "-name" sorts descending first, so a click flips it.
            if descending and field.startswith("-"):
                return field.removeprefix("-")
            return f"-{field}" if descending else field
        return field.desc() if descending else field.asc()

    @cached_property
    def ordering(self) -> list[Any]:
        """The sorted columns, else the admin's ordering, then the queryset's own; the primary key ends a partial order."""
        if self.request.GET.get(ORDER_VAR):
            ordering = [self.sort_term(index, direction) for index, direction in self.sorted_columns.items()]
        else:
            ordering = [*(self.model_admin.get_ordering(self.request) or self.opts.ordering or ())]
        ordering.extend(self.root_queryset.query.order_by)
        if not self.root_queryset.order_by(*ordering).totally_ordered:
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
        if not self.model_admin.show_full_result_count or not self.is_filtered:
            return None
        # An order keeps the paginator from warning; COUNT(*) drops it again.
        return EstimatedCountPaginator(self.root_queryset.order_by("pk"), self.list_per_page).count

    @cached_property
    def show_all(self) -> bool:
        """``all`` as Django's admin writes it, or All from the page size menu."""
        return (ALL_VAR in self.request.GET or self.per_page_param == ALL_VAR) and self.can_show_all

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
        rows = list(self.page.object_list)
        annotate_rows(rows, display_annotations(self.list_display, self.model_admin))
        self.model_admin.prepare_rows(self.request, rows)
        return rows

    def page_url(self, number: int) -> str:
        return self.get_query_string({PAGE_VAR: number if number > 1 else None, ALL_VAR: None})

    @cached_property
    def per_page_select(self) -> str | None:
        """The page size menu, with All while every row fits on one page; None where no size changes the page."""
        if not self.list_per_page_options or self.result_count <= self.list_per_page_options[0]:
            return None
        choices = [(str(size), number_format(size, force_grouping=True)) for size in self.list_per_page_options]
        if self.can_show_all:
            choices.append((ALL_VAR, _("All")))
        widget = Select(
            choices=choices, show_search=False, attrs={"aria-label": _("Rows per page"), "class": "select-sm min-w-20"}
        )
        return widget.render(PER_PAGE_VAR, ALL_VAR if self.show_all else str(self.list_per_page))

    @cached_property
    def per_page_inputs(self) -> list[tuple[str, str]]:
        """The list's state that a new page size keeps: all but the page."""
        return [
            (key, value)
            for key, values in self.params.lists()
            if key not in {PAGE_VAR, PER_PAGE_VAR, ALL_VAR}
            for value in values
        ]

    @cached_property
    def page_links(self) -> list[PageLink]:
        """The pager's links around the current page; none while one page shows every row."""
        if self.show_all or not self.multi_page:
            return []
        return page_links(self.paginator, self.page.number)

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
        """One header per ``list_display`` entry, with its sort link and direction.

        Like Django's header, a click sorts by the column first and keeps the other sorted columns after it.
        A sorted column also links to the order without it, Django's "Remove from sorting"."""
        sorted_columns = self.sorted_columns
        columns = []
        for position, (key, entry) in enumerate(self.column_names.items()):
            column: dict[str, Any] = {
                "name": key,
                "label": self.header_label(entry),
                "sort_url": "",
                "remove_url": "",
                "direction": "",
                "priority": None,
                "numeric": self.is_numeric(entry),
                "linked": entry in self.links,
                "indent": key in self.boxed_fields,
            }
            index = position + self.column_offset
            if self.order_field(entry) is not None:
                direction = sorted_columns.get(index, "")
                first = f"-{index}" if direction == "asc" else str(index)
                rest = [
                    f"{'-' if d == 'desc' else ''}{number}" for number, d in sorted_columns.items() if number != index
                ]
                column["sort_url"] = self.get_query_string({ORDER_VAR: ".".join([first, *rest]), PAGE_VAR: None})
                column["direction"] = direction
                if direction:
                    column["remove_url"] = self.get_query_string({ORDER_VAR: ".".join(rest), PAGE_VAR: None})
                if direction and len(sorted_columns) > 1:
                    column["priority"] = list(sorted_columns).index(index) + 1
            columns.append(column)
        return columns

    def is_numeric(self, entry: str | Callable[..., Any]) -> bool:
        field = list_field(self.model, entry)
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
        query = self.encoded_params
        return urlencode({PRESERVED_FILTERS_VAR: query}) if query else ""

    def change_url(self, result: models.Model) -> str:
        url = self.url_for_result(result)
        return f"{url}?{self.preserved_filters}" if self.preserved_filters else url

    @cached_property
    def boxed_fields(self) -> set[str]:
        """The editable columns whose field draws a box, which sets the value in from the cell's edge."""
        if self.formset is None:
            return set()
        fields = self.formset.form.base_fields
        return {
            key
            for key in self.list_editable
            if key in fields and getattr(fields[key].widget, "input_type", None) not in {"checkbox", "radio"}
        }

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
                    # After a failed save, a value the user changed still counts as changed, valid or not.
                    cell["changed"] = form.is_bound and key in form.changed_data
                else:
                    cell.update(list_cell(entry, obj, self.model_admin))
                cell["numeric"] = self.is_numeric(entry)
                cell["indent"] = cell["field"] is not None and key in self.boxed_fields
                cells.append(cell)
            row = {"pk": obj.pk, "value": str(obj.pk), "index": index, "cells": cells, "form": form, "pick": None}
            if self.is_popup:
                # What a click on the row's link hands to the relation: the value it posts and the row's name.
                value = obj.serializable_value(self.to_field or self.pk_attname)
                row["pick"] = {"value": str(value), "obj": str(obj)}
            rows.append(row)
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
