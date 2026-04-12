"""Advanced input widgets: DatePicker, InputNumber, OTPInput, PhoneInput, InputMask."""

from __future__ import annotations

from typing import Any

from django import forms


class DatePicker(forms.DateInput):
    """Date input with an Alpine.js calendar dropdown."""

    template_name = "formwork/widgets/date_picker.html"
    input_type = "text"

    def __init__(self, attrs: dict[str, Any] | None = None, *, format: str | None = None) -> None:  # noqa: A002
        defaults: dict[str, Any] = {"placeholder": "YYYY-MM-DD"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults, format=format or "%Y-%m-%d")


class InputNumber(forms.NumberInput):
    """Number input with increment/decrement buttons."""

    template_name = "formwork/widgets/input_number.html"


class OTPInput(forms.TextInput):
    """One-time password / PIN code input."""

    template_name = "formwork/widgets/otp_input.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, length: int = 6) -> None:
        super().__init__(attrs)
        self.length = length

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["length"] = self.length
        context["widget"]["digits"] = list(range(self.length))
        val = value or ""
        context["widget"]["initial_digits"] = [val[i] if i < len(val) else "" for i in range(self.length)]
        return context


class PhoneInput(forms.MultiWidget):
    """Phone number input with country code prefix selector."""

    template_name = "formwork/widgets/phone_input.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, default_code: str = "+1") -> None:
        from django_formwork.data import phone_prefix_choices

        self.default_code = default_code
        prefix_widget = forms.Select(choices=phone_prefix_choices())
        number_widget = forms.TextInput(attrs={"placeholder": "Phone number", "type": "tel"})
        super().__init__(widgets=[prefix_widget, number_widget], attrs=attrs)

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


class InputMask(forms.TextInput):
    """Text input with a fixed-format mask."""

    template_name = "formwork/widgets/input_mask.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, mask: str = "") -> None:
        super().__init__(attrs)
        self.mask = mask

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["mask"] = self.mask
        placeholder = self.mask.replace("#", "_").replace("A", "_").replace("*", "_")
        if "placeholder" not in context["widget"]["attrs"]:
            context["widget"]["attrs"]["placeholder"] = placeholder
        return context
