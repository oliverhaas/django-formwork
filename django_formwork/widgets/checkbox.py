"""Single checkbox with its own text beside the box."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

if TYPE_CHECKING:
    from collections.abc import Callable


class CheckboxInput(forms.CheckboxInput):
    """Checkbox with ``text`` beside the box and the field label above it.

    Without ``text`` the field label sits beside the box.
    """

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        check_test: Callable[[Any], bool] | None = None,
        *,
        text: str = "",
    ) -> None:
        super().__init__(attrs, check_test)
        self.text = text

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["text"] = self.text
        return context
