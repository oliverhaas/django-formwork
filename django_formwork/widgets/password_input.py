"""Password input with a show/hide toggle."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _ModuleScript
from .floating import FloatingLabelMixin


class PasswordInput(FloatingLabelMixin, forms.PasswordInput):
    """Password input with a button that shows the typed text; ``reveal=False`` drops the button."""

    template_name = "formwork/widgets/password_input.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/password_input.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        render_value: bool = False,  # noqa: FBT001, FBT002
        *,
        floating: bool = False,
        reveal: bool = True,
    ) -> None:
        super().__init__(attrs, render_value, floating=floating)
        self.reveal = reveal

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["reveal"] = self.reveal
        return context
