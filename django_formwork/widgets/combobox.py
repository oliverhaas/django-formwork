"""ComboBox widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET

if TYPE_CHECKING:
    from collections.abc import Callable


class ComboBox(forms.TextInput):
    """Text input with autocomplete suggestions.

    Renders a text input with a dropdown of suggestions that appear as the
    user types.  The submitted value is whatever the user typed (free text),
    not a key from a choices list.  Suggestions are just hints.

    In multiple mode (``multiple=True``), accepts comma-separated values.
    Suggestions appear for the segment currently being typed.

    Usage::

        tags = forms.CharField(
            widget=ComboBox(suggestions=["Python", "JavaScript", "Go"]),
        )

        # Multiple mode:
        tags = forms.CharField(
            widget=ComboBox(
                suggestions=["pizza", "pasta", "sushi"],
                multiple=True,
            ),
        )
    """

    template_name = "formwork/widgets/combo_box.html"

    def __init__(  # noqa: PLR0913
        self,
        *,
        suggestions: list[str] | None = None,
        multiple: bool = False,
        search_url: str | None = None,
        search_decorator: Callable | object = _NOT_SET,
        icons: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs)
        self.suggestions = suggestions or []
        self.multiple = multiple
        self.search_url = search_url
        self.search_decorator = search_decorator
        self.icons = icons or {}
        self.descriptions = descriptions or {}
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["suggestions"] = [
            {"text": s, "icon": self.icons.get(s, ""), "description": self.descriptions.get(s, "")}
            for s in self.suggestions
        ]
        context["widget"]["multiple"] = self.multiple
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        # Build initial icon map from current value for unfocused display.
        context["widget"]["icons_json"] = json.dumps(
            {s: self.icons[s] for s in self.suggestions if s in self.icons},
            ensure_ascii=False,
        )
        return context
