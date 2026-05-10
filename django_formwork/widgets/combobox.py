"""ComboBox widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

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
        suggestions: list[str] | list[tuple[str, list[str]]] | None = None,
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

    def _suggestion_groups(self) -> list[tuple[str, list[dict[str, str]]]]:
        """Normalize ``suggestions`` to a list of ``(group, items)`` tuples.

        Flat ``["a", "b"]`` becomes ``[("", [...])]``; grouped
        ``[("Group", ["a", "b"])]`` is preserved.
        """

        def _build(text: str) -> dict[str, str]:
            return {
                "text": text,
                "icon": self.icons.get(text, ""),
                "description": self.descriptions.get(text, ""),
            }

        if self.suggestions and isinstance(self.suggestions[0], (tuple, list)):
            grouped = cast("list[tuple[str, list[str]]]", self.suggestions)
            return [(group, [_build(s) for s in items]) for group, items in grouped]
        flat = cast("list[str]", self.suggestions)
        return [("", [_build(s) for s in flat])]

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        groups = self._suggestion_groups()
        # Flat list for backward compatibility with the existing template loop.
        context["widget"]["suggestions"] = [item for _g, items in groups for item in items]
        context["widget"]["suggestion_groups"] = groups
        context["widget"]["multiple"] = self.multiple
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        # Build initial icon map from current value for unfocused display.
        flat_texts = [item["text"] for item in context["widget"]["suggestions"]]
        context["widget"]["icons_json"] = json.dumps(
            {s: self.icons[s] for s in flat_texts if s in self.icons},
            ensure_ascii=False,
        )
        return context
