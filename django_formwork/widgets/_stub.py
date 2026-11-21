"""Stubs for the widgets of a formset's saved rows, which load the full widget on first use."""

from __future__ import annotations

from functools import cache, partial
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from ._base import _StubMixin
from .select import Select, autowidth_copy, rows_share_choices

if TYPE_CHECKING:
    from collections.abc import Callable

    from django import forms
    from django.forms.formsets import BaseFormSet


def _shared_copy(bound: forms.BoundField, select: Select) -> str:
    return autowidth_copy(select.get_context(bound.html_name, bound.value(), bound.build_widget_attrs({}))["widget"])


def with_query(url: str, **query: Any) -> str:
    """``url`` with ``query`` added to its query string."""
    return f"{url}{'&' if '?' in url else '?'}{urlencode(query)}"


def stub_formset(formset: BaseFormSet[Any], url_of: Callable[[str], str], *, share: bool | None = None) -> None:
    """Render the widgets of a formset's saved rows as stubs; call it after ``share_choices``.

    A field with an error renders in full, next to its error. ``url_of(name)`` answers with a field's
    full widget for the query ``pk``, ``prefix`` and ``value``."""
    # Built when the first stub renders, where the selects of the page share their queries.
    copies: dict[str, Callable[[], str]] = {}
    urls: dict[str, str] = {}
    for form in formset.forms:
        pk = getattr(getattr(form, "instance", None), "pk", None)
        if pk is None:
            continue
        for name, field in form.fields.items():
            widget = field.widget
            if field.disabled or not isinstance(widget, _StubMixin) or name in form.errors:
                continue
            if isinstance(widget, Select):
                if widget.floating:
                    continue
                # Rows that share their choices share the labels that size their stubs.
                if rows_share_choices(formset, field, share=share):
                    widget.stub_copy = copies.setdefault(name, cache(partial(_shared_copy, form[name], widget)))
            if name not in urls:
                urls[name] = url_of(name)
            widget.stub_url = with_query(urls[name], pk=pk, prefix=form.prefix)


def formset_row(formset_class: type[BaseFormSet[Any]], prefix: str, *, value_of: dict[str, str], **kwargs: Any) -> Any:  # noqa: ANN401
    """The form of the first row of ``formset_class(**kwargs)``, as the formset builds it, under the form ``prefix``.

    ``value_of`` sets the value of a field over the row's saved one. None when the formset has no saved row.
    """
    kwargs.setdefault("prefix", prefix.rpartition("-")[0] or None)
    form_kwargs = kwargs.pop("form_kwargs", None) or {}
    initial = {**form_kwargs.get("initial", {}), **value_of}
    formset = formset_class(form_kwargs={**form_kwargs, "prefix": prefix, "initial": initial}, **kwargs)
    return next(iter(formset.initial_forms), None)
