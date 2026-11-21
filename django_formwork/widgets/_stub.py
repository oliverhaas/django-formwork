"""Stubs for the widgets of a formset's saved rows, which load the full widget on first use."""

from __future__ import annotations

from functools import cache, partial
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlencode

from ._base import _StubMixin, widget_of
from .select import SearchableSelectMixin, rows_share_choices

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from django import forms
    from django.forms.formsets import BaseFormSet
    from django.utils.safestring import SafeString


def _shared_copy(bound: forms.BoundField, select: SearchableSelectMixin) -> str:
    return select.autowidth_copy(
        select.get_context(bound.html_name, bound.value(), bound.build_widget_attrs({}))["widget"]
    )


def with_query(url: str, **query: Any) -> str:
    """``url`` with ``query`` added to its query string."""
    return f"{url}{'&' if '?' in url else '?'}{urlencode(query)}"


def stub_formset(formset: BaseFormSet[Any], url_of: Callable[[str], str], *, share: bool | None = None) -> None:
    """Render the widgets of a formset's saved rows as stubs, also inside a wrapping widget; call it after ``share_choices``.

    A field with an error renders in full, next to its error. ``url_of(name)`` answers with ``loaded_widget`` for
    the query ``pk`` and ``prefix``, and the stub's inputs under their names."""
    # Built when the first stub renders, where the selects of the page share their queries.
    copies: dict[str, Callable[[], str]] = {}
    urls: dict[str, str] = {}
    for form in formset.forms:
        pk = getattr(getattr(form, "instance", None), "pk", None)
        if pk is None:
            continue
        for name, field in form.fields.items():
            widget = widget_of(field, _StubMixin)
            if field.disabled or widget is None or name in form.errors:
                continue
            if isinstance(widget, SearchableSelectMixin):
                if widget.floating:
                    continue
                # Rows that share their choices share the labels that size their stubs.
                if rows_share_choices(formset, field, share=share):
                    widget.stub_copy = copies.setdefault(name, cache(partial(_shared_copy, form[name], widget)))
            if name not in urls:
                urls[name] = url_of(name)
            widget.stub_url = with_query(urls[name], pk=pk, prefix=form.prefix)


def loaded_widget(bound: forms.BoundField) -> SafeString:
    """The full widget that takes the place of the stub of ``bound``, without a widget that wraps it.

    The field's label names it, as a table cell has no ``<label>``."""
    # Each stub widget is a Widget; _StubMixin is only its mixin.
    widget = cast("forms.Widget", widget_of(bound.field, _StubMixin))
    return bound.as_widget(widget, attrs={"aria-label": str(bound.label)})


def formset_row(
    formset_class: type[BaseFormSet[Any]], prefix: str, field: str, data: Mapping[str, Any], /, **kwargs: Any
) -> Any:  # noqa: ANN401
    """The form of the first row of ``formset_class(**kwargs)``, as the formset builds it, under the form ``prefix``.

    The inputs of ``field`` in ``data`` set its value over the row's saved one. None when the formset has no
    saved row.
    """
    kwargs.setdefault("prefix", prefix.rpartition("-")[0] or None)
    form_kwargs = kwargs.pop("form_kwargs", None) or {}
    formset = formset_class(form_kwargs={**form_kwargs, "prefix": prefix}, **kwargs)
    form = next(iter(formset.initial_forms), None)
    if form is not None and field in form.fields:
        widget, html_name = form.fields[field].widget, form.add_prefix(field)
        if not widget.value_omitted_from_data(data, {}, html_name):
            form.initial[field] = widget.value_from_datadict(data, {}, html_name)
    return form
