"""Radio and checkbox choices drawn as cards."""

from __future__ import annotations

from typing import Any

from django import forms
from django.forms.widgets import ChoiceWidget


class _CardChoiceMixin(ChoiceWidget):
    """Shared rendering for the card choice widgets."""

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        # The template cannot read the hyphenated key; the error border needs it.
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        return context


class CardRadioSelect(_CardChoiceMixin, forms.RadioSelect):
    """Radio choices drawn as large selectable cards, side by side from the ``lg`` breakpoint."""

    template_name = "formwork/widgets/card_choice.html"


class CardCheckboxSelectMultiple(_CardChoiceMixin, forms.CheckboxSelectMultiple):
    """Checkbox choices drawn as large selectable cards, side by side from the ``lg`` breakpoint."""

    template_name = "formwork/widgets/card_choice.html"
