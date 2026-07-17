"""DataList widget."""

from __future__ import annotations

from typing import Any

from django import forms


class DataList(forms.TextInput):
    """Text input with native ``<datalist>`` browser suggestions.

    Renders an ``<input>`` with a ``list`` attribute pointing to a
    ``<datalist>`` containing the provided suggestions.  No JavaScript
    is required: the browser provides the autocomplete dropdown natively.

    Note: the submitted value is whatever the user typed (free text),
    not a key from a choices list.

    Usage::

        browser = forms.CharField(
            widget=DataList(suggestions=["Chrome", "Firefox", "Safari"]),
        )
    """

    template_name = "formwork/widgets/datalist.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, suggestions: list[str] | None = None) -> None:
        super().__init__(attrs)
        self.suggestions = suggestions or []

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget_id = context["widget"]["attrs"].get("id")
        if widget_id:
            context["widget"]["attrs"]["list"] = f"{widget_id}_list"
        context["widget"]["suggestions"] = self.suggestions
        return context
