"""MultiSelect widget."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

from ._base import _NOT_SET, _ModuleScript, _resolve_initial_results

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class MultiSelect(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes.

    Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes.
    Uses Alpine.js for open/close state and selected-count display.
    The template adds the ``multiselect`` class on checkboxes so
    CSS doesn't apply the default ``checkbox`` class.

    Server-side search auto-wires through the formwork registry: pair the
    widget with ``search_fields`` against a ``ModelMultipleChoiceField``
    queryset, or define a ``search_choices_<fieldname>`` method on a
    :class:`~django_formwork.forms.FormworkForm`.  Selected values are
    tracked in Alpine state and submitted via hidden inputs.

    Icons are carried by the choice label.  Wrap choice labels in
    :class:`~django_formwork.fields.ChoiceLabel` (with the ``icon``
    value wrapped in ``mark_safe``) or use
    :class:`~django_formwork.fields.FormworkModelMultipleChoiceField` with
    ``icon_from_instance``.

    Usage::

        # Static choices
        languages = forms.MultipleChoiceField(
            choices=[("py", "Python"), ("js", "JavaScript")],
            widget=MultiSelect,
        )

        # Server-side search (model-backed)
        languages = forms.ModelMultipleChoiceField(
            queryset=Language.objects.all(),
            widget=MultiSelect(search_fields=["name"], search_decorator=login_required),
        )
    """

    template_name = "formwork/widgets/multi_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    class Media:
        js = (_ModuleScript("formwork/widgets/multi_select.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | None = _NOT_SET,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self._registry_key: str | None = None

    def get_context(self, name: str, value: list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        from django_formwork.fields import ChoiceLabel

        context = super().get_context(name, value, attrs)
        total = sum(len(options) for _, options, _ in context["widget"]["optgroups"])
        # Resolve search URL from the registry. No registration → client-side only.
        search_url: str | None = None
        if self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        # Pre-render the first ``max_results`` options into the listbox so
        # the dropdown opens with real data; htmx replaces them on first
        # focus.  Total count drives the ``show_search`` decision.
        registry_total, initial_options = _resolve_initial_results(self._registry_key)
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url and registry_total is not None:
            context["widget"]["show_search"] = registry_total >= self.search_threshold
        else:
            context["widget"]["show_search"] = total >= self.search_threshold or bool(search_url)
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        context["widget"]["aria_describedby"] = context["widget"]["attrs"].get("aria-describedby")
        context["widget"]["search_url"] = search_url
        context["widget"]["initial_options"] = initial_options if search_url else []
        # Read icon from ChoiceLabel.
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                label = option["label"]
                option["icon"] = label.icon if isinstance(label, ChoiceLabel) else ""
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
