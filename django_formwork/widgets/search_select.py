"""SearchSelect widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET

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
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
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
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url:
            # Server-side search: start hidden, let OOB total-count swap decide.
            context["widget"]["show_search"] = False
        else:
            context["widget"]["show_search"] = total >= self.search_threshold
        return context
