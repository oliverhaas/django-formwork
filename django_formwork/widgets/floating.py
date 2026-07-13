"""Floating-label variants of the native text, select, and textarea widgets."""

from __future__ import annotations

from typing import Any

from django import forms


class FloatingLabelMixin:
    """Render a control inside DaisyUI's floating-label wrapper, reusing the placeholder as the label."""

    floating_wrapper_template = "formwork/widgets/floating_label.html"

    def __init__(self, *args: Any, floating_label: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.floating_label = floating_label
        if floating_label:
            # Remember the real widget template so the wrapper can include it,
            # then point rendering at the wrapper.
            self._inner_template_name = self.template_name
            self.template_name = self.floating_wrapper_template

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)  # type: ignore[misc]
        if self.floating_label:
            widget = context["widget"]
            widget["inner_template_name"] = self._inner_template_name
            widget["floating_label_text"] = widget["attrs"].get("placeholder", "")
        return context


class TextInput(FloatingLabelMixin, forms.TextInput):
    """``forms.TextInput`` with an optional DaisyUI floating label."""


class Textarea(FloatingLabelMixin, forms.Textarea):
    """``forms.Textarea`` with an optional DaisyUI floating label."""


class Select(FloatingLabelMixin, forms.Select):
    """``forms.Select`` with an optional DaisyUI floating label (placeholder used only as label text)."""

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        if self.floating_label:
            context["widget"]["attrs"].pop("placeholder", None)
        return context
