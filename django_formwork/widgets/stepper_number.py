"""Number input between decrease and increase buttons."""

from __future__ import annotations

from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from ._base import _ModuleScript


class StepperNumberInput(forms.NumberInput):
    """Number input between buttons that step it by its ``step`` attribute.

    ``min`` bounds the buttons without a native ``min`` attribute. ``integer`` drops the decimals.
    """

    template_name = "formwork/widgets/stepper_number.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/stepper_number.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        integer: bool = False,
        min: float | None = None,  # noqa: A002
        trailing_buttons: bool = False,
    ) -> None:
        super().__init__(attrs)
        self.integer = integer
        self.min = min
        self.trailing_buttons = trailing_buttons

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["integer"] = self.integer
        widget["min"] = self.min
        widget["trailing_buttons"] = self.trailing_buttons
        # The template owns the class list; attrs.html would render a second class.
        widget["css_class"] = widget["attrs"].pop("class", "")
        widget["attrs"].setdefault("aria-roledescription", _("Number field"))
        return context
