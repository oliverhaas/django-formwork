"""Free-text combo boxes: a text input with a suggestion dropdown."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Concatenate

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from ._base import _ModuleScript, _resolve_initial_results
from .select import _UNSET_DECORATOR, label_extras

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from django.db.models import Model, QuerySet
    from django.http import HttpRequest

    from .select import ChoiceLabel, _UnsetDecorator

    Suggestion = str | ChoiceLabel
    Suggestions = Sequence[Suggestion] | Sequence[tuple[str, Sequence[Suggestion]]]


class ComboBox(forms.TextInput):
    """Text input with a suggestion dropdown; the submitted value is free text.

    ``suggestions`` are hints, flat or grouped as ``[(group, [...])]``.
    """

    template_name = "formwork/widgets/combo_box.html"
    search_variant = "combo_box"
    multiple = False

    class Media:
        js = (_ModuleScript("formwork/widgets/combo_box.js"),)

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        *,
        suggestions: Suggestions | None = None,
        show_spinner: bool = True,
        search_key: str | None = None,
        search_params: Mapping[str, int | str] | None = None,
        search_fields: Sequence[str] | None = None,
        search_queryset: Callable[Concatenate[HttpRequest, ...], QuerySet[Any]] | None = None,
        search_decorator: Callable[..., Any] | _UnsetDecorator | None = _UNSET_DECORATOR,
        label_from_instance: Callable[[Model], object] | None = None,
    ) -> None:
        if search_key is not None and search_fields:
            msg = "Pass either search_key or search_fields, not both."
            raise ImproperlyConfigured(msg)
        super().__init__(attrs)
        self.suggestions = list(suggestions or [])
        self.show_spinner = show_spinner
        self.search_key = search_key
        self.search_params = dict(search_params or {})
        self.search_fields: tuple[str, ...] = tuple(search_fields) if search_fields else ()
        self.search_queryset = search_queryset
        self.search_decorator = search_decorator
        self.label_from_instance = label_from_instance
        # Set by FormworkForm when it registers a search for this widget.
        self._registry_key: str | None = None

    def _options(self) -> list[dict[str, Any]]:
        """The suggestions as option rows; a pick fills the input with the label."""
        options: list[dict[str, Any]] = []
        for entry in self.suggestions:
            group, items = (str(entry[0]), entry[1]) if isinstance(entry, (tuple, list)) else ("", [entry])
            options.extend(
                {"value": str(item), "label": str(item), "group": group, **label_extras(item)} for item in items
            )
        return options

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # The template merges `class` into its own class attribute.
        widget["input_attrs"] = {key: val for key, val in widget["attrs"].items() if key != "class"}
        widget["options"] = self._options()
        widget["multiple"] = self.multiple
        widget["show_spinner"] = self.show_spinner
        widget["search_url"] = None
        widget["truncated"] = False
        widget["shown"] = None
        widget["more_url"] = None
        if self._registry_key is not None:
            _total, rows = _resolve_initial_results(self._registry_key)
            widget["options"] = [{**row, "label_html": "", "group": ""} for row in rows]
            widget["search_url"] = reverse("formwork:search", kwargs={"key": self._registry_key})
        # The closed input shows a picked suggestion's icon beside its text.
        icons = {option["label"]: str(option["icon"]) for option in widget["options"] if option["icon"]}
        widget["icons_json"] = json.dumps(icons)
        return context


class ComboBoxMultiple(ComboBox):
    """``ComboBox`` for comma-separated free text; suggestions apply to the segment being typed."""

    multiple = True
