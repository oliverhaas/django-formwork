"""SearchInput widget."""

from __future__ import annotations

from typing import Any

from django import forms


class SearchInput(forms.TextInput):
    """Search field with a leading magnifier and an optional trailing clear button.

    The magnifier swaps to a spinner while an htmx request is in flight
    (``show_spinner``); the clear button empties the field and refocuses it
    (``show_clear``).  To drive an htmx search, pass ``hx-*`` attributes and
    point ``hx-indicator`` at ``<id>_icon``.

    Usage::

        query = forms.CharField(widget=SearchInput(), required=False)
    """

    input_type = "search"
    template_name = "formwork/widgets/search_input.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        show_spinner: bool = True,
        show_clear: bool = True,
    ) -> None:
        super().__init__(attrs)
        self.show_spinner = show_spinner
        self.show_clear = show_clear

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["show_spinner"] = self.show_spinner
        widget["show_clear"] = self.show_clear
        widget["attrs"].setdefault("placeholder", "Search…")
        return context
