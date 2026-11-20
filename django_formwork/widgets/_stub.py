"""Stubs for the widgets of a formset's saved rows, which load the full widget on first use."""

from __future__ import annotations

from functools import cache, partial
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from django.utils.html import format_html_join

from ._base import _StubMixin
from .select import Select, rows_share_choices

if TYPE_CHECKING:
    from collections.abc import Callable

    from django import forms
    from django.forms.formsets import BaseFormSet


def _autowidth_copy(bound: forms.BoundField, select: Select) -> str:
    """The option labels that size a select's trigger, as the full select renders them."""
    widget = select.get_context(bound.html_name, bound.value(), bound.build_widget_attrs({}))["widget"]
    # A list that loads its options from the server has no copy in the full select either.
    if widget["search_url"]:
        return ""
    return format_html_join(
        "",
        "<span>{}</span>",
        (
            (option["label_html"] if widget["badges"] and option.get("label_html") else option["label"],)
            for option in widget["options"]
        ),
    )


def stub_formset(formset: BaseFormSet[Any], url_of: Callable[[str], str], *, share: bool | None = None) -> None:
    """Render the widgets of an unbound formset's saved rows as stubs; call it after ``share_choices``.

    ``url_of(name)`` answers with a field's full widget for the query ``pk``, ``prefix`` and ``value``.
    A select whose rows can get choices of their own keeps the full widget."""
    if formset.is_bound:
        return
    # Built when the first stub renders, where the selects of the page share their queries.
    copies: dict[str, Callable[[], str]] = {}
    urls: dict[str, str] = {}
    for form in formset.forms:
        pk = getattr(getattr(form, "instance", None), "pk", None)
        if pk is None:
            continue
        for name, field in form.fields.items():
            widget = field.widget
            if field.disabled or not isinstance(widget, _StubMixin):
                continue
            if isinstance(widget, Select):
                if widget.floating or not rows_share_choices(formset, field, share=share):
                    continue
                if name not in copies:
                    copies[name] = cache(partial(_autowidth_copy, form[name], widget))
                widget.stub_copy = copies[name]
            if name not in urls:
                urls[name] = url_of(name)
            widget.stub_url = f"{urls[name]}?{urlencode({'pk': pk, 'prefix': form.prefix})}"
