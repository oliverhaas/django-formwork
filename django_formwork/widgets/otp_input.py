"""One-time code input."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _FormworkTemplatesMixin, size_classes


class OTPInput(_FormworkTemplatesMixin, forms.TextInput):
    """One-time code of ``length`` digits in a single input, drawn as one box per digit.

    One real input keeps SMS autofill and paste working.
    """

    template_name = "formwork/widgets/otp_input.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, length: int = 6) -> None:
        super().__init__(attrs)
        self.length = length

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["attrs"].setdefault("inputmode", "numeric")
        widget["attrs"].setdefault("autocomplete", "one-time-code")
        widget["attrs"]["maxlength"] = self.length
        widget["attrs"]["pattern"] = f"[0-9]{{{self.length}}}"
        widget["slots"] = range(self.length)
        # DaisyUI sizes and colors the boxes through classes on the <label class="otp">.
        css_class = widget["attrs"].pop("class", "")
        own_size = any(size.rpartition(":")[2].startswith("otp-") for size in size_classes(css_class).split())
        widget["otp_class"] = css_class if own_size else f"otp-md sm:otp-lg {css_class}".strip()
        return context
