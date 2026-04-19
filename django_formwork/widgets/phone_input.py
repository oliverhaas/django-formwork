"""PhoneInput widget."""

from __future__ import annotations

from typing import Any

from django import forms


class PhoneInput(forms.MultiWidget):
    """Phone number input with country code prefix selector.

    Renders a country-code dropdown (with flags) next to a text input.
    The submitted value is ``"{dial_code} {number}"`` (e.g. ``"+1 5551234"``).

    Usage::

        phone = forms.CharField(widget=PhoneInput)
    """

    template_name = "formwork/widgets/phone_input.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, default_code: str = "+1") -> None:
        from django_formwork.data import phone_prefix_choices

        self.default_code = default_code
        self._prefix_choices = phone_prefix_choices()
        prefix_widget = forms.HiddenInput()
        number_widget = forms.TextInput(
            attrs={"placeholder": "Phone number", "type": "tel", "class": "join-item input grow"},
        )
        super().__init__(widgets=[prefix_widget, number_widget], attrs=attrs)

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:  # noqa: ANN401
        context = super().get_context(name, value, attrs)
        context["widget"]["prefix_choices"] = self._prefix_choices
        return context

    def decompress(self, value: str | None) -> list[str]:
        if value:
            parts = value.split(" ", 1)
            if len(parts) == 2:  # noqa: PLR2004
                return parts
            return [self.default_code, value]
        return [self.default_code, ""]

    def value_from_datadict(self, data: Any, files: Any, name: str) -> str:  # type: ignore[override]  # noqa: ANN401
        values = super().value_from_datadict(data, files, name)
        prefix = values[0] or ""
        number = values[1] or ""
        return f"{prefix} {number}".strip() if number else ""
