"""SuffixNumberInput widget."""

from __future__ import annotations

from typing import Any

from django import forms


class SuffixNumberInput(forms.NumberInput):
    """Number input with a static unit, currency, or percent suffix inside the field.

    The ``suffix`` renders as non-interactive text pinned to the trailing
    edge of the field, for example ``"kg"``, ``"USD"`` or ``"%"``.

    Usage::

        weight = forms.DecimalField(widget=SuffixNumberInput(suffix="kg"))
    """

    template_name = "formwork/widgets/suffix_number.html"

    def __init__(self, suffix: str = "", attrs: dict[str, Any] | None = None) -> None:
        self.suffix = suffix
        super().__init__(attrs)

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["suffix"] = self.suffix
        return context
