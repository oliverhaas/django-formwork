"""ComboBox widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET, _ModuleScript, _resolve_initial_results

if TYPE_CHECKING:
    from collections.abc import Callable


def _normalize_suggestions(
    suggestions: list[str] | list[tuple[str, list[str]]] | None,
) -> list[tuple[str, list[str]]]:
    """Return suggestions in grouped form ``[(group, items), ...]``.

    Flat ``["a", "b"]`` is wrapped in a single empty-named group.
    """
    if not suggestions:
        return []
    # Grouped when the first entry is a (group, items) pair; otherwise flat.
    if isinstance(suggestions[0], (tuple, list)):
        groups: list[tuple[str, list[str]]] = []
        for item in suggestions:
            if isinstance(item, (tuple, list)) and len(item) == 2:  # noqa: PLR2004
                group, items = item
                groups.append((str(group), [str(s) for s in items]))
            else:
                # A stray non-pair among groups degrades to an ungrouped item
                # rather than raising on the tuple unpack.
                groups.append(("", [str(item)]))
        return groups
    return [("", [str(s) for s in suggestions])]


class ComboBox(forms.TextInput):
    """Text input with autocomplete suggestions.

    Renders a text input with a dropdown of suggestions that appear as the
    user types.  The submitted value is whatever the user typed (free text),
    not a key from a choices list.  Suggestions are just hints.

    In multiple mode (``multiple=True``), accepts comma-separated values.
    Suggestions appear for the segment currently being typed.

    Server-side search auto-wires through the formwork registry: define a
    ``search_choices_<fieldname>`` method on a
    :class:`~django_formwork.forms.FormworkForm` returning ``(value, label)``
    tuples or ``{"label": ..., "icon": ...}`` dicts.

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

    class Media:
        js = (_ModuleScript("formwork/widgets/combo_box.js"),)

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        *,
        suggestions: list[str] | list[tuple[str, list[str]]] | None = None,
        multiple: bool = False,
        search_decorator: Callable | None = _NOT_SET,
        icons: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
    ) -> None:
        super().__init__(attrs)
        self.suggestions = suggestions or []
        self.multiple = multiple
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

        groups = _normalize_suggestions(self.suggestions) or [("", [])]
        return [(group, [_build(s) for s in items]) for group, items in groups]

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        groups = self._suggestion_groups()
        flat_suggestions = [item for _g, items in groups for item in items]
        context["widget"]["suggestion_groups"] = groups
        context["widget"]["multiple"] = self.multiple
        # Resolve search URL from the registry. No registration → client-side only.
        search_url: str | None = None
        if self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        # Build initial icon map from current value for unfocused display.
        flat_texts = [item["text"] for item in flat_suggestions]
        context["widget"]["icons_json"] = json.dumps(
            {s: self.icons[s] for s in flat_texts if s in self.icons},
            ensure_ascii=False,
        )
        # Pre-render the first ``max_results`` suggestions in the dropdown
        # so it opens with real data; htmx replaces them on first focus.
        _total, initial_options = _resolve_initial_results(self._registry_key)
        context["widget"]["initial_options"] = initial_options if search_url else []
        return context
