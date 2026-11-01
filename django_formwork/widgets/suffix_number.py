"""Number input with a unit inside the field."""

from __future__ import annotations

from typing import Any

from django import forms


class SuffixNumberInput(forms.NumberInput):
    """Number input with a static unit, currency or percent sign as a prefix or suffix inside the field."""

    template_name = "formwork/widgets/suffix_number.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, suffix: str = "", prefix: str = "") -> None:
        super().__init__(attrs)
        self.suffix = suffix
        self.prefix = prefix

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["suffix"] = self.suffix
        context["widget"]["prefix"] = self.prefix
        return context
