"""MultiSelect widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class MultiSelect(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes.

    Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes.
    Uses Alpine.js for open/close state and selected-count display.
    The template adds the ``multiselect`` class on checkboxes so
    CSS doesn't apply the default ``checkbox`` class.

    When ``search_url`` is provided, the search input uses htmx to fetch
    options from the server.  Selected values are tracked in Alpine state
    and submitted via hidden inputs (not the visible checkboxes).

    Icons are carried by the choice label.  Wrap choice labels in
    :class:`~django_formwork.fields.FormworkChoiceLabel` (with the ``icon``
    value wrapped in ``mark_safe``) or use
    :class:`~django_formwork.fields.FormworkModelMultipleChoiceField` with
    ``icon_from_instance``.

    Usage::

        languages = forms.MultipleChoiceField(
            choices=[("py", "Python"), ("js", "JavaScript")],
            widget=MultiSelect,
        )

        # With server-side search:
        languages = forms.MultipleChoiceField(
            widget=MultiSelect(search_url=reverse_lazy("lang-search")),
        )
    """

    template_name = "formwork/widgets/multi_select.html"
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

    def get_context(self, name: str, value: list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        from django_formwork.fields import FormworkChoiceLabel

        context = super().get_context(name, value, attrs)
        total = sum(len(options) for _, options, _ in context["widget"]["optgroups"])
        # Resolve search URL: explicit > auto-registered > none.
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
        # Read icon from FormworkChoiceLabel.
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                label = option["label"]
                option["icon"] = label.icon if isinstance(label, FormworkChoiceLabel) else ""
        if search_url:
            # Build initial selected map for Alpine: [[value, [label, icon]], ...]
            selected_values = set(value or [])
            initial_selected = [
                [str(option["value"]), [str(option["label"]), option.get("icon", "")]]
                for _group, options, _index in context["widget"]["optgroups"]
                for option in options
                if str(option["value"]) in selected_values
            ]
            context["widget"]["initial_selected_json"] = json.dumps(initial_selected)
        return context
