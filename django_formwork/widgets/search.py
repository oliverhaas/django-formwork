"""Search/selection widgets: SearchSelect, MultiSelect, ComboBox, CountryInput, CascadeSelect."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class MultiSelect(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes."""

    template_name = "formwork/widgets/multi_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        icons: dict[str, str] | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | object = _NOT_SET,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.icons = icons or {}
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self.icon_from_instance = icon_from_instance
        self.description_from_instance = description_from_instance
        self._registry_key: str | None = None

    def get_context(self, name: str, value: list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        total = sum(len(options) for _, options, _ in context["widget"]["optgroups"])
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        else:
            context["widget"]["show_search"] = total >= self.search_threshold or bool(search_url)
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        context["widget"]["search_url"] = search_url
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                option["icon"] = self.icons.get(str(option["value"]), "")
        if search_url:
            selected_values = set(value or [])
            initial_selected = [
                [str(option["value"]), [str(option["label"]), option.get("icon", "")]]
                for _group, options, _index in context["widget"]["optgroups"]
                for option in options
                if str(option["value"]) in selected_values
            ]
            context["widget"]["initial_selected_json"] = json.dumps(initial_selected)
        return context


class SearchSelect(forms.Select):
    """Single-select dropdown with text search/filter."""

    template_name = "formwork/widgets/search_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        icons: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | object = _NOT_SET,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.icons = icons or {}
        self.descriptions = descriptions or {}
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self.icon_from_instance = icon_from_instance
        self.description_from_instance = description_from_instance
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        fmt_value = context["widget"]["value"]
        if isinstance(fmt_value, (list, tuple)):
            context["widget"]["value"] = fmt_value[0] if fmt_value else ""
        selected_label = ""
        selected_icon = ""
        total = 0
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                val_str = str(option["value"])
                option["icon"] = self.icons.get(val_str, "")
                option["description"] = self.descriptions.get(val_str, "")
                if option["selected"]:
                    selected_label = str(option["label"])
                    selected_icon = option["icon"]
                total += 1
        context["widget"]["selected_label"] = selected_label
        context["widget"]["selected_icon"] = selected_icon
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        context["widget"]["search_threshold"] = self.search_threshold
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url:
            context["widget"]["show_search"] = False
        else:
            context["widget"]["show_search"] = total >= self.search_threshold
        return context


class ComboBox(forms.TextInput):
    """Text input with autocomplete suggestions."""

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
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        context["widget"]["icons_json"] = json.dumps(
            {s: self.icons[s] for s in self.suggestions if s in self.icons},
            ensure_ascii=False,
        )
        return context


class CountryInput(SearchSelect):
    """Searchable country selector with flag emojis."""

    def __init__(self, attrs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        from django_formwork.data import country_choices

        super().__init__(attrs=attrs, choices=tuple(country_choices()), **kwargs)


class CascadeSelect(forms.Select):
    """Dependent cascading dropdown using htmx."""

    template_name = "formwork/widgets/cascade_select.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        parent_field: str = "",
        search_url: str = "",
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.parent_field = parent_field
        self.search_url = search_url

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["parent_field"] = self.parent_field
        context["widget"]["search_url"] = self.search_url
        return context
