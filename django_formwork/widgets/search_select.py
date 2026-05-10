"""SearchSelect widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET, _resolve_search_expectations, _skeleton_rows

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class SearchSelect(forms.Select):
    """Single-select dropdown with text search/filter.

    Renders a DaisyUI-styled dropdown with a text input for filtering
    options.  Submits a single key value via a hidden ``<input>`` element.
    Uses Alpine.js for filtering, keyboard navigation, and selection.

    This is a ``<select>`` replacement — the submitted value is a key
    from the choices list, not free text.

    When ``search_url`` is provided, the text input uses htmx to fetch
    matching options from the server instead of client-side filtering.

    Icons and descriptions are carried by the choice label.  Wrap choice
    labels in :class:`~django_formwork.fields.FormworkChoiceLabel` or use
    :class:`~django_formwork.fields.FormworkModelChoiceField` with
    ``icon_from_instance`` / ``description_from_instance``.

    Usage::

        city = forms.ChoiceField(
            choices=[("nyc", "New York"), ("ldn", "London"), ...],
            widget=SearchSelect,
        )

        # With server-side search:
        city = forms.ChoiceField(
            widget=SearchSelect(search_url=reverse_lazy("city-search")),
        )
    """

    template_name = "formwork/widgets/search_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | object = _NOT_SET,
        expected_count: int | None = None,
        expected_icons: bool = False,
        expected_descriptions: bool = False,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self.expected_count = expected_count
        self.expected_icons = expected_icons
        self.expected_descriptions = expected_descriptions
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        from django_formwork.fields import FormworkChoiceLabel

        context = super().get_context(name, value, attrs)
        # Select.format_value() wraps value in a list — unwrap for template.
        fmt_value = context["widget"]["value"]
        if isinstance(fmt_value, (list, tuple)):
            context["widget"]["value"] = fmt_value[0] if fmt_value else ""
        # Single pass: find selected label/icon AND read icons/descriptions.
        selected_label = ""
        selected_icon = ""
        total = 0
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                label = option["label"]
                if isinstance(label, FormworkChoiceLabel):
                    option["icon"] = label.icon
                    option["description"] = label.description
                else:
                    option["icon"] = ""
                    option["description"] = ""
                if option["selected"]:
                    selected_label = str(label)
                    selected_icon = option["icon"]
                total += 1
        context["widget"]["selected_label"] = selected_label
        context["widget"]["selected_icon"] = selected_icon
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        context["widget"]["search_threshold"] = self.search_threshold
        # Resolve expected counts/shape — for server-side widgets this drives
        # the loading skeleton and the initial visibility of the search input.
        expected_count, expected_icons, expected_descriptions = self._resolve_expectations()
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url and expected_count is not None:
            # Decide up-front from the expected count instead of waiting for an OOB swap.
            context["widget"]["show_search"] = expected_count >= self.search_threshold
        elif search_url:
            # Server-side search without an expected count hint: start hidden,
            # let OOB total-count swap decide.
            context["widget"]["show_search"] = False
        else:
            context["widget"]["show_search"] = total >= self.search_threshold
        context["widget"]["expected_count"] = expected_count
        context["widget"]["expected_icons"] = expected_icons
        context["widget"]["expected_descriptions"] = expected_descriptions
        context["widget"]["skeleton_rows"] = _skeleton_rows(expected_count) if search_url else []
        return context

    def _resolve_expectations(self) -> tuple[int | None, bool, bool]:
        """Return ``(expected_count, expected_icons, expected_descriptions)``.

        Falls back to auto-registered metadata so most callers don't need to
        repeat what the registry already knows.
        """
        return _resolve_search_expectations(
            self._registry_key,
            self.expected_count,
            self.expected_icons,
            self.expected_descriptions,
        )
