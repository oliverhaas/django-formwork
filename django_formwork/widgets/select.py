"""Single-select dropdown widget, the shared select mixin and ``ChoiceLabel``."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, Literal
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import EmptyResultSet, ImproperlyConfigured, ValidationError
from django.db.models import FETCH_ONE, FETCH_PEERS
from django.db.models import fields as model_fields
from django.forms.models import ModelChoiceIterator
from django.utils.choices import flatten_choices
from django.utils.formats import number_format
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext

from django_formwork.search import SEARCH_PAGE_SIZE, check_search_params, search_url

from ._base import _FormworkTemplatesMixin, _ModuleScript, _StubMixin, widget_of

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator, Iterable, Iterator, Mapping, Sequence

    from django.db.models import QuerySet
    from django.forms.formsets import BaseFormSet
    from django.forms.renderers import BaseRenderer
    from django.http import HttpRequest
    from django.utils.choices import _Choices
    from django.utils.safestring import SafeString

    # Typed base so mypy resolves the cooperative super() calls. At runtime the
    # mixin inherits object and is placed in front of a concrete select widget.
    _SelectBase = forms.Select
else:
    _SelectBase = object

__all__ = [
    "BadgeColor",
    "ChoiceLabel",
    "SearchableSelectMixin",
    "Select",
    "label_extras",
    "share_choices",
    "shared_pages",
]

# The rows that the selects of one render have loaded, by their query.
_pages: ContextVar[dict[tuple[Any, ...], list[Any]] | None] = ContextVar("formwork_select_pages", default=None)


@contextmanager
def shared_pages() -> Generator[None]:
    """Selects that render inside load the same rows, a first page or a selected row, with one query."""
    token = _pages.set({})
    try:
        yield
    finally:
        _pages.reset(token)


def with_peers(queryset: QuerySet[Any]) -> QuerySet[Any]:
    """``queryset`` with ``FETCH_PEERS`` in place of Django's default ``FETCH_ONE``, as each label can read a relation.

    A mode that the queryset sets otherwise, such as ``FETCH_RAISE``, stays.
    """
    if queryset._fetch_mode is FETCH_ONE:  # type: ignore[attr-defined]  # noqa: SLF001
        return queryset.fetch_mode(FETCH_PEERS)
    return queryset


def _load(queryset: QuerySet[Any]) -> list[Any]:
    """The rows of ``queryset``, which ``shared_pages()`` keeps for the next select that asks for them."""
    queryset = with_peers(queryset)
    pages = _pages.get()
    if pages is None:
        return list(queryset)
    try:
        sql, params = queryset.query.sql_with_params()
    except EmptyResultSet:
        return []
    # The fetch mode and the prefetches load the rows' relations, and the SQL does not show them.
    loading = (queryset._fetch_mode, queryset._prefetch_related_lookups)  # type: ignore[attr-defined]  # noqa: SLF001
    key = (queryset.db, sql, repr(params), *loading)
    if key not in pages:
        pages[key] = list(queryset)
    return pages[key]


def _rows_of(queryset: QuerySet[Any], key: str, values: Iterable[str]) -> list[Any]:
    """The rows that have one of ``values`` in ``key``. A value the column cannot hold does not drop the others."""
    wanted = []
    for value in values:
        # filter() converts the value without a query, as ModelMultipleChoiceField checks.
        try:
            queryset.filter(**{key: value})
        except ValueError, TypeError, ValidationError:
            continue
        wanted.append(value)
    # Sorted, so two selects with the same values ask for the same rows.
    return _load(queryset.filter(**{f"{key}__in": sorted(wanted)})) if wanted else []


# The methods with which a form or a formset can give one row other choices than the next.
_FORM_ROW_HOOKS = ("__init__",)
_FORMSET_ROW_HOOKS = ("__init__", "get_form_kwargs", "add_fields", "_construct_form")
_OWN_MODULES = frozenset({"builtins", "typing", "django", "django_formwork"})


def _project_methods(klass: type, names: Sequence[str]) -> list[str]:
    """``Class.method`` for each of ``names`` that a class outside Django and formwork defines for ``klass``."""
    return [
        f"{base.__qualname__}.{name}"
        for base in klass.__mro__
        if base.__module__.partition(".")[0] not in _OWN_MODULES
        for name in names
        if name in vars(base)
    ]


def row_choice_hooks(form_class: type, formset_class: type) -> list[str]:
    """The methods with which the rows of a formset can get choices of their own."""
    return [*_project_methods(form_class, _FORM_ROW_HOOKS), *_project_methods(formset_class, _FORMSET_ROW_HOOKS)]


class _SharedChoices:
    """A relation's first page and the selected rows of all rows of a formset, loaded when the first row renders."""

    def __init__(
        self, queryset: QuerySet[Any], key: str, rows: list[tuple[forms.BoundField, SearchableSelectMixin]]
    ) -> None:
        self.queryset = queryset
        self.key = key
        self.rows = rows
        self._every: list[tuple[Any, Any]] | None = None

    def every(self, choices: ModelChoiceIterator) -> list[tuple[Any, Any]]:
        """Every choice of a select without a server search, listed by the first row that renders for all rows."""
        if self._every is None:
            choices.queryset = with_peers(choices.queryset)
            self._every = list(choices)
        return self._every

    @cached_property
    def page(self) -> list[Any]:
        # One extra row tells whether more exist, so no COUNT runs.
        return _load(self.queryset[: SEARCH_PAGE_SIZE + 1])

    @cached_property
    def values(self) -> set[str]:
        return {str(value) for bound, select in self.rows for value in select.format_value(bound.value()) if value}

    @cached_property
    def shown(self) -> dict[str, Any]:
        """The rows of the first page, by their value."""
        return {str(getattr(obj, self.key)): obj for obj in self.page[:SEARCH_PAGE_SIZE]}

    @cached_property
    def selected(self) -> dict[str, Any]:
        """The rows past the first page that a row has selected, by their value."""
        past = self.values - self.shown.keys()
        return {str(getattr(obj, self.key)): obj for obj in _rows_of(self.queryset, self.key, past)}

    @cached_property
    def chosen(self) -> dict[str, Any]:
        """The rows that any row of the formset has selected, by their value, from ``shown`` and ``selected``."""
        return {**{value: obj for value, obj in self.shown.items() if value in self.values}, **self.selected}


def rows_share_choices(formset: BaseFormSet[Any], field: forms.Field, *, share: bool | None = None) -> bool:
    """Whether the rows of ``formset`` get the same choices for ``field``.

    ``share`` answers for every field; ``None`` says no when a row can get choices of its own."""
    if share is not None:
        return share
    # Django calls a callable limit_choices_to again for every form.
    if callable(getattr(field, "limit_choices_to", None)):
        return False
    return not row_choice_hooks(formset.form, type(formset))


def share_choices(formset: BaseFormSet[Any], *, share: bool | None = None) -> None:
    """Let the selects of a formset's rows load a relation's choices once for all rows.

    ``None`` leaves out the fields whose rows can get choices of their own, ``True`` shares those too.
    The first call for a formset decides, so ``as_rows()`` keeps what the admin set before."""
    rows = formset.forms
    if not rows or getattr(formset, "_formwork_shared", False):
        return
    formset._formwork_shared = True  # type: ignore[attr-defined]  # noqa: SLF001
    for name, field in rows[0].fields.items():
        if not isinstance(field, forms.ModelChoiceField) or field.queryset is None:
            continue
        if not rows_share_choices(formset, field, share=share):
            continue
        selects = [
            (form[name], select) for form in rows if (select := widget_of(form.fields.get(name), SearchableSelectMixin))
        ]
        shared = _SharedChoices(field.queryset, field.to_field_name or "pk", selects)
        for _bound, select in selects:
            select.shared = shared


def column_options(formset: BaseFormSet[Any]) -> SafeString:
    """Let the selects of a table column copy their option rows from one ``<template>``, and return the templates.

    Call it after ``share_choices`` and ``stub_formset``, before the rows render. A column qualifies when its rows
    list the same choices, all of them, and a row renders in full. The row of Add another keeps its own options,
    as does the full widget that replaces a stub."""
    rows = formset.forms
    lists = []
    for bound in rows[0].visible_fields() if rows else ():
        select = widget_of(bound.field, SearchableSelectMixin)
        if select is None or bound.field.disabled:
            continue
        # A relation's rows share their choices where share_choices() said so, other choices where no hook changes them.
        if isinstance(bound.field, forms.ModelChoiceField):
            if select.shared is None:
                continue
        elif not rows_share_choices(formset, bound.field):
            continue
        selects = [
            row_select for form in rows if (row_select := widget_of(form.fields.get(bound.name), SearchableSelectMixin))
        ]
        if all(getattr(row_select, "stub_url", None) is not None for row_select in selects):
            continue
        options = select.option_list(bound.html_name, bound.build_widget_attrs({}), bound.form.renderer)
        # A list longer than one page loads its rows from the server search.
        if select.truncated:
            continue
        template_id = f"{formset.prefix}-{bound.name}-options"
        for row_select in selects:
            row_select.options_template_id = template_id
        lists.append(format_html('<template id="{}">{}</template>', template_id, options))
    return mark_safe("".join(lists))  # noqa: S308


def _defer_page(options: list[dict[str, Any]], pending: dict[str, Any]) -> list[dict[str, Any]]:
    """``options`` with the row that loads the first page in place of the page's rows, after the blank rows."""
    blank = [option for option in options if option.get("blank_row")]
    rest = [option for option in options if not option.get("blank_row") and not option.get("page_row")]
    return [*blank, pending, *rest]


class _UnsetDecorator:
    """Sentinel for `search_decorator` not being passed."""


_UNSET_DECORATOR = _UnsetDecorator()

# Attrs the select templates place themselves.
_TEMPLATE_ATTRS = frozenset(
    {
        "id",
        "class",
        "placeholder",
        "disabled",
        "aria-invalid",
        "aria-required",
        "aria-labelledby",
        "aria-label",
        "aria-describedby",
    }
)


def _trigger_context(widget: dict[str, Any]) -> None:
    """Spread the widget's attrs over the trigger and the hidden input."""
    attrs = widget["attrs"]
    widget["aria_invalid"] = attrs.get("aria-invalid")
    widget["aria_required"] = attrs.get("aria-required")
    # `<label for>` cannot target the <summary>, so the label and the
    # help/error rows are associated by id instead (see boundfield.py, field.html).
    widget["aria_labelledby"] = attrs.get("aria-labelledby")
    widget["aria_label"] = attrs.get("aria-label")
    widget["aria_describedby"] = attrs.get("aria-describedby")
    widget["disabled"] = bool(attrs.get("disabled"))
    # The hidden input holds the value and fires `change` on a pick. Data and
    # htmx attrs go there, the rest go on the trigger, which takes focus.
    rest = {key: val for key, val in attrs.items() if key not in _TEMPLATE_ATTRS}
    if widget["disabled"]:
        rest.pop("tabindex", None)
    widget["input_attrs"] = {key: val for key, val in rest.items() if key.startswith(("data-", "hx-"))}
    widget["trigger_attrs"] = {key: val for key, val in rest.items() if key not in widget["input_attrs"]}


BadgeColor = Literal["neutral", "primary", "secondary", "accent", "info", "success", "warning", "error"]


class ChoiceLabel:
    """Choice label whose ``__str__`` is its text; the extras are presentation only.

    ``icon``, ``description`` and ``label_html`` can hold HTML marked safe by the caller.
    ``Select`` puts ``selected_toggle_class`` on its trigger while the option is selected.
    """

    __slots__ = ("color", "description", "icon", "label", "label_html", "selected_toggle_class")

    def __init__(  # noqa: PLR0913
        self,
        label: str,
        *,
        icon: str = "",
        description: str = "",
        label_html: str = "",
        color: BadgeColor = "neutral",
        selected_toggle_class: str = "",
    ) -> None:
        self.label = label
        self.icon = icon
        self.description = description
        self.label_html = label_html
        self.color = color
        self.selected_toggle_class = selected_toggle_class

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        extras = ("icon", "description", "label_html", "selected_toggle_class")
        parts = [repr(self.label)]
        parts.extend(f"{name}={value!r}" for name in extras if (value := getattr(self, name)))
        if self.color != "neutral":
            parts.append(f"color={self.color!r}")
        return f"ChoiceLabel({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.label == other
        if isinstance(other, ChoiceLabel):
            return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.label)


def label_extras(label: object, *, badges: bool = False) -> dict[str, str]:
    """What an option row shows beside its text, blank for a plain label.

    With ``badges``, a label without ``label_html`` shows as a badge in its ``color``.
    """
    label_html = getattr(label, "label_html", "")
    if badges and not label_html:
        color = getattr(label, "color", "neutral")
        variant = "badge-ghost" if color == "neutral" else f"badge-soft badge-{color}"
        label_html = format_html('<span class="badge badge-sm {}">{}</span>', variant, str(label))
    return {
        "icon": getattr(label, "icon", ""),
        "description": getattr(label, "description", ""),
        "label_html": label_html,
        "selected_toggle_class": getattr(label, "selected_toggle_class", ""),
    }


class SearchableSelectMixin(_FormworkTemplatesMixin, _SelectBase):
    """Search and dropdown behavior shared by ``Select`` and ``SelectMultiple``."""

    option_inherits_attrs = False
    search_threshold = 10
    # Names the option markup the dispatch view renders for this widget.
    search_variant: ClassVar[str]
    #: The template of the option rows, which the search endpoint and a table column render.
    option_list_template_name: ClassVar[str]
    #: The option labels that size the stubs of rows that share their choices, set with ``stub_url``.
    stub_copy: Callable[[], str] | None = None
    #: The id of the ``<template>`` that holds the option rows of a table column, set by ``column_options()``.
    #: The select copies the rows from it when its list opens, so each row does not repeat them.
    options_template_id = ""

    def id_for_label(self, id_: str, index: str = "0") -> str:  # noqa: ARG002
        # The trigger is a <summary>, which `<label for>` cannot target.
        return ""

    def use_required_attribute(self, initial: object) -> bool:  # noqa: ARG002
        # No control renders `required` (the trigger gets aria-required), and
        # forms.Select would read the first choice for it: a query on a model field.
        return False

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: _Choices = (),
        *,
        show_search: bool | None = None,
        show_spinner: bool = True,
        search_key: str | None = None,
        search_params: Mapping[str, int | str] | None = None,
        search_fields: Sequence[str] | None = None,
        search_queryset: Callable[Concatenate[HttpRequest, ...], QuerySet[Any]] | None = None,
        search_decorator: Callable[..., Any] | _UnsetDecorator | None = _UNSET_DECORATOR,
        search_ranked: bool = False,
        search_label: Callable[..., object] | None = None,
        allow_clear: bool = False,
        floating: bool = False,
        counts: Mapping[Any, int] | None = None,
        badges: bool = False,
    ) -> None:
        if search_key is not None and search_fields:
            msg = "Pass either search_key or search_fields, not both."
            raise ImproperlyConfigured(msg)
        super().__init__(attrs=attrs, choices=choices)
        self.show_search = show_search
        self.show_spinner = show_spinner
        self.search_key = search_key
        self.search_params = dict(search_params or {})
        # A wrong key or param set fails where the widget is built, not on first render.
        if search_key is not None:
            check_search_params(search_key, self.search_params)
        self.search_fields: tuple[str, ...] = tuple(search_fields) if search_fields else ()
        self.search_queryset = search_queryset
        self.search_decorator = search_decorator
        self.search_ranked = search_ranked
        self.search_label = search_label
        self.allow_clear = allow_clear
        self.floating = floating
        self.counts = counts
        self.badges = badges
        # Set per render by optgroups().
        self.truncated = False
        self.selected_past_page: list[str] = []
        # Set by share_choices() for the rows of a formset.
        self.shared: _SharedChoices | None = None

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["options_template_id"] = self.options_template_id
        pending = self._search_context(widget)

        # One pass: annotate each option from its ChoiceLabel and collect the
        # options to render and the selected ones for the closed toggle.
        options: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        clear: dict[str, Any] | None = None
        total = 0
        # The server's pages of a long list carry no counts, so the first page shows none either.
        counts = None
        if self.counts is not None and not self.truncated:
            counts = {str(key): count for key, count in self.counts.items()}
        for group, group_options, _index in widget["optgroups"]:
            for option in group_options:
                # The empty choice is a placeholder or the clearing row, not a value.
                option.update(label_extras(option["label"], badges=self.badges and str(option["value"]) != ""))
                if counts is not None and str(option["value"]) != "":
                    count = counts.get(str(option["value"]), 0)
                    option["count"] = number_format(count, force_grouping=True)
                    option["count_zero"] = not count
                # A heading row precedes the first option of each named group.
                option["group"] = group or ""
                # The empty choice (e.g. ModelChoiceField's "---------") is a row
                # only when it clears; the placeholder covers it otherwise.
                if str(option["value"]) == "":
                    if self.allow_clear:
                        clear = self.clear_row(option, widget["attrs"])
                        options.append(clear)
                    continue
                options.append(option)
                total += 1
                if option["selected"]:
                    selected.append({**option, "label": str(option["label"])})
        if pending is not None:
            options = _defer_page(options, pending)
        widget["options"] = options
        widget["badges"] = self.badges
        widget["selected_options"] = selected
        _trigger_context(widget)
        widget["truncated"] = self.truncated
        widget["show_spinner"] = self.show_spinner
        widget["show_search"] = (
            self.show_search if self.show_search is not None else total > self.search_threshold or self.truncated
        )
        self._floating_context(widget, clear)
        return context

    def option_list(
        self, name: str, attrs: dict[str, Any] | None = None, renderer: BaseRenderer | None = None
    ) -> SafeString:
        """The option rows with nothing chosen, which the selects of a table column copy when they open."""
        widget = self.get_context(name, None, attrs)["widget"]
        context = {"widget": widget, "options": widget["options"], "truncated": False, "more_url": None}
        return self._render(self.option_list_template_name, context, renderer)

    def autowidth_copy(self, widget: Mapping[str, Any]) -> str:
        """The option labels that size the trigger, from the context of the full select."""
        # A list that loads its options from the server has no copy in the full select either.
        if widget["search_url"]:
            return ""
        if widget["badges"]:
            return format_html_join(
                "", "<span>{}</span>", ((option.get("label_html") or option["label"],) for option in widget["options"])
            )
        return format_html_join("\n", "{}", ((option["label"],) for option in widget["options"]))

    def _labels_of(self, values: Collection[str]) -> list[tuple[str, object]]:
        """The value and the label of each choice that holds one of ``values``, in the order of the choices."""
        choices = self.choices
        if not isinstance(choices, ModelChoiceIterator):
            flat: Iterator[tuple[Any, object]] = flatten_choices(choices)
            return [(str(choice), label) for choice, label in flat if str(choice) in values]
        if self.shared is not None:
            rows = [obj for value, obj in self.shared.chosen.items() if value in values]
        else:
            rows = _rows_of(choices.queryset, choices.field.to_field_name or "pk", values)
        return [(str(value), label) for value, label in map(choices.choice, rows)]

    def clear_row(self, option: dict[str, Any], attrs: Mapping[str, Any]) -> dict[str, Any]:
        """The row that clears the value. Django's default blank label gives way to the placeholder, muted."""
        # Django writes BLANK_CHOICE_LABEL, which a project can rename in ready(); code written before 6.1 "---------".
        defaults = (model_fields.BLANK_CHOICE_DASH[0][1], model_fields.BLANK_CHOICE_LABEL)
        if str(option["label"]) not in {str(label) for label in defaults}:
            return option
        # The text of the empty trigger: a floating label's placeholder is its label, not the empty text.
        placeholder = "" if self.floating else attrs.get("placeholder", "")
        return {**option, "label": placeholder or gettext("Select…"), "placeholder": True}

    def _search_context(self, widget: dict[str, Any]) -> dict[str, Any] | None:
        """Set the server search of a list longer than one page; return the row that loads its first page."""
        # A list that fits one page filters in the browser.
        widget["search_url"] = None
        widget["more_url"] = None
        key = self.search_key
        if not self.truncated or key is None:
            return None
        widget["search_url"] = search_url(
            key, self.search_params, widget=self.search_variant, allow_clear=self.allow_clear
        )
        more = {"offset": SEARCH_PAGE_SIZE, "exclude": self.selected_past_page}
        widget["more_url"] = f"{widget['search_url']}&{urlencode(more, doseq=True)}"
        # The first page loads when the list opens. The widget renders the blank row and the
        # selected rows past the page. The endpoint leaves them out, as it does on the next pages.
        page = search_url(key, self.search_params, widget=self.search_variant)
        first = {"page_only": 1, "exclude": self.selected_past_page}
        return {"pending_url": f"{page}&{urlencode(first, doseq=True)}", "group": ""}

    def optgroups(
        self, name: str, value: list[str], attrs: dict[str, Any] | None = None
    ) -> list[tuple[str | None, list[dict[str, Any]], int | None]]:
        """Every choice without a server search, else one page plus the selected ones."""
        if self.search_key is None:
            return self._every_optgroups(name, value, attrs)
        chosen = {str(subvalue) for subvalue in value if subvalue}
        limit = SEARCH_PAGE_SIZE
        choices = self.choices
        blank: list[tuple[Any, Any]] = []
        if isinstance(choices, ModelChoiceIterator):
            if choices.field.empty_label is not None:
                blank.append(("", choices.field.empty_label))
            # django-filter's option for rows without a related row.
            field: Any = choices.field
            if getattr(field, "null_label", None) is not None:
                blank.append((field.null_value, field.null_label))
            key = choices.field.to_field_name or "pk"
            shared = self.shared
            # One extra row tells whether more exist, so no COUNT runs.
            page = shared.page if shared is not None else _load(choices.queryset[: limit + 1])
            first = page[:limit]
            shown = {str(getattr(obj, key)) for obj in first}
            past = chosen - shown
            if shared is not None and past <= shared.selected.keys():
                rest = [obj for value, obj in shared.selected.items() if value in past]
            else:
                rest = _rows_of(choices.queryset, key, past)
            self.selected_past_page = [str(getattr(obj, key)) for obj in rest]
            if len(page) > limit:
                # The browser loads the page of a longer list, so only its selected rows need a label.
                first = [obj for obj in first if str(getattr(obj, key)) in chosen]
            pairs = [*blank, *(choices.choice(obj) for obj in [*first, *rest])]
            rows = len(first)
        else:
            flat: Iterator[tuple[Any, Any]] = flatten_choices(choices)
            every: list[tuple[Any, Any]] = []
            for pair in flat:
                (every if str(pair[0]) else blank).append(pair)
            page = every[: limit + 1]
            beyond = [pair for pair in every[limit:] if str(pair[0]) in chosen]
            self.selected_past_page = [str(pair[0]) for pair in beyond]
            pairs = [*blank, *every[:limit], *beyond]
            rows = len(every[:limit])
        # The endpoint caps its rows the same way, so the hint reads the same.
        self.truncated = len(page) > limit
        options = [
            self.create_option(name, choice, label, str(choice) in chosen, index, attrs=attrs)
            for index, (choice, label) in enumerate(pairs)
        ]
        for option in options[: len(blank)]:
            option["blank_row"] = True
        # The endpoint's first page, which get_context() can leave to the browser.
        for option in options[len(blank) : len(blank) + rows]:
            option["page_row"] = True
        return [(None, options, 0)] if options else []

    def _every_optgroups(
        self, name: str, value: list[str], attrs: dict[str, Any] | None
    ) -> list[tuple[str | None, list[dict[str, Any]], int | None]]:
        """Django's optgroups(). The rows of a formset list the choices of a relation once, from ``shared``."""
        choices = self.choices
        if not isinstance(choices, ModelChoiceIterator):
            return super().optgroups(name, value, attrs)
        if self.shared is None:
            choices.queryset = with_peers(choices.queryset)
            return super().optgroups(name, value, attrs)
        groups: list[tuple[str | None, list[dict[str, Any]], int | None]] = []
        has_selected = False
        # Django's loop, without its groups: a relation has none.
        for index, (choice, label) in enumerate(self.shared.every(choices)):
            selected = (not has_selected or self.allow_multiple_selected) and str(choice) in value
            has_selected |= selected
            groups.append((None, [self.create_option(name, choice, label, selected, index, attrs=attrs)], index))
        return groups

    def _floating_context(self, widget: dict[str, Any], clear: Mapping[str, Any] | None) -> None:
        """The floating label's id, the trigger's name and its empty text."""
        widget["floating"] = self.floating
        placeholder = widget["attrs"].get("placeholder", "")
        widget["floating_label_id"] = ""
        if not self.floating:
            widget["trigger_placeholder"] = placeholder
            return
        if not placeholder:
            msg = f"{type(self).__name__}(floating=True) needs a placeholder: it is the label text."
            raise ImproperlyConfigured(msg)
        # The placeholder text is the label. An empty trigger takes the name of the field's
        # clearing row, such as a filter's "All", or the default text.
        widget["trigger_placeholder"] = "" if clear is None else str(clear["label"])
        id_ = widget["attrs"].get("id")
        if id_:
            widget["floating_label_id"] = f"{id_}_floating_label"
            # `<label for>` cannot target the <summary>: name it by the floating
            # label, then by its value.
            if not widget["aria_labelledby"]:
                widget["aria_labelledby"] = f"{id_}_floating_label {id_}"


class Select(_StubMixin, SearchableSelectMixin, forms.Select):
    """Single-select Alpine dropdown with text filtering; posts via a hidden input.

    Drop-in for a native ``<select>``: validation is unchanged.
    """

    template_name = "formwork/widgets/select.html"
    #: The option rows alone, which a server search answers with.
    option_list_template_name = "formwork/widgets/partials/select_options.html"
    stub_template_name = "formwork/widgets/select_stub.html"
    search_variant = "select"

    class Media:
        js = (_ModuleScript("formwork/widgets/select.js"),)

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # forms.Select.format_value() wraps the value in a list; unwrap for the template.
        fmt_value = widget["value"]
        if isinstance(fmt_value, (list, tuple)):
            widget["value"] = fmt_value[0] if fmt_value else ""
        first = widget["selected_options"][0] if widget["selected_options"] else {}
        # A value no option holds (a deleted row, an edited post) shows the
        # placeholder, so it must not post again. Empty choices can't tell.
        if not first and (widget["options"] or isinstance(self.choices, ModelChoiceIterator)):
            widget["value"] = ""
        widget["selected_label"] = first.get("label", "")
        widget["selected_icon"] = first.get("icon", "")
        widget["selected_label_html"] = first.get("label_html", "")
        widget["selected_toggle_class"] = first.get("selected_toggle_class", "")
        return context

    def get_stub_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:  # noqa: ANN401
        if self.stub_copy is None:
            # A row with choices of its own loads them to size its stub, as the full select does.
            context = self.get_context(name, value, attrs)
            widget = context["widget"]
            widget["trigger_placeholder"] = widget["attrs"].get("placeholder", "")
            widget["autowidth_copy"] = self.autowidth_copy(widget)
            return context
        # forms.Select's own context builds every option; the stub shows the selected one alone.
        context = forms.Widget.get_context(self, name, value, attrs)
        widget = context["widget"]
        current = widget["value"]
        if isinstance(current, (list, tuple)):
            current = current[0] if current else ""
        current = "" if current is None else str(current)
        labels = self._labels_of({current}) if current else []
        label = labels[0][1] if labels else None
        extras = label_extras(label, badges=self.badges) if label is not None else {}
        _trigger_context(widget)
        widget.update(
            {
                "value": current if label is not None else "",
                "selected_label": "" if label is None else str(label),
                "selected_icon": extras.get("icon", ""),
                "selected_label_html": extras.get("label_html", ""),
                "selected_toggle_class": extras.get("selected_toggle_class", ""),
                "trigger_placeholder": widget["attrs"].get("placeholder", ""),
                "autowidth_copy": self.stub_copy(),
            }
        )
        return context
