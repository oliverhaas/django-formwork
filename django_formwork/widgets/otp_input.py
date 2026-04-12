"""OTPInput widget."""

from __future__ import annotations

from typing import Any

from django import forms


class OTPInput(forms.TextInput):
    """One-time password / PIN code input.

    Renders N single-character inputs that auto-advance on typing.
    The submitted value is the concatenated string.  Uses Alpine.js.

    Usage::

        code = forms.CharField(widget=OTPInput(length=6))
    """

    template_name = "formwork/widgets/otp_input.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, length: int = 6) -> None:
        super().__init__(attrs)
        self.length = length

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["length"] = self.length
        context["widget"]["digits"] = list(range(self.length))
        # Pre-fill individual digits from current value.
        val = value or ""
        context["widget"]["initial_digits"] = [val[i] if i < len(val) else "" for i in range(self.length)]
        return context
