"""InputText widget."""

from __future__ import annotations

from typing import Any

from django import forms


class InputText(forms.TextInput):
    """Text input that can float its placeholder as a DaisyUI floating label.

    With ``floating=True`` the input is wrapped in a
    ``<label class="floating-label">`` so the ``placeholder`` doubles as a
    label that floats above the field once it holds a value or gains focus.

    ``input_type`` swaps the underlying HTML input type (for example
    ``"email"`` or ``"url"``) while keeping the floating-label behaviour.

    Usage::

        email = forms.EmailField(
            widget=InputText(
                floating=True,
                input_type="email",
                attrs={"placeholder": "Email address"},
            ),
        )
    """

    template_name = "formwork/widgets/input_text.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        floating: bool = False,
        input_type: str = "text",
    ) -> None:
        super().__init__(attrs)
        self.floating = floating
        self.input_type = input_type

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["floating"] = self.floating
        return context
