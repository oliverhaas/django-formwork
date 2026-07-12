"""InputMask widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _ModuleScript


class InputMask(forms.TextInput):
    """Text input with a fixed-format mask.

    Uses Alpine.js to enforce a pattern as the user types.
    ``#`` = digit, ``A`` = letter, ``*`` = any character.

    Usage::

        phone = forms.CharField(widget=InputMask(mask="(###) ###-####"))
        zip_code = forms.CharField(widget=InputMask(mask="#####"))
    """

    template_name = "formwork/widgets/input_mask.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/input_mask.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None, *, mask: str = "") -> None:
        super().__init__(attrs)
        self.mask = mask

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["mask"] = self.mask
        # Build placeholder from mask pattern.
        # Use middle dot (·) instead of underscore — underscores sit at the
        # text baseline and are clipped/invisible in DaisyUI's input component.
        placeholder = self.mask.replace("#", "\u00b7").replace("A", "\u00b7").replace("*", "\u00b7")
        if "placeholder" not in context["widget"]["attrs"]:
            context["widget"]["attrs"]["placeholder"] = placeholder
        return context
