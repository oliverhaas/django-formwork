"""Search input with a magnifier, a spinner and a clear button."""

from __future__ import annotations

from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from ._base import _ModuleScript


class SearchInput(forms.TextInput):
    """Search field with a leading magnifier (an htmx spinner while a request runs) and a clear button.

    ``filter_items`` is a CSS selector: typing hides the matching rows whose ``data-label`` misses the query.
    """

    # CSS hides the WebKit clear button (.clearable-search), which the template replaces.
    input_type = "search"
    template_name = "formwork/widgets/search_input.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/search_input.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        show_spinner: bool = True,
        show_clear: bool = True,
        filter_items: str = "",
    ) -> None:
        super().__init__(attrs)
        self.show_spinner = show_spinner
        self.show_clear = show_clear
        self.filter_items = filter_items

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["show_spinner"] = self.show_spinner
        widget["show_clear"] = self.show_clear
        widget["filter_items"] = self.filter_items
        widget["attrs"].setdefault("placeholder", _("Search..."))
        # Room for the leading magnifier, and for the clear button when shown.
        padding = "ps-10 pe-10" if self.show_clear else "ps-10"
        classes = f"clearable-search {widget['attrs'].get('class', '')} {padding}"
        widget["attrs"]["class"] = " ".join(classes.split())
        return context
