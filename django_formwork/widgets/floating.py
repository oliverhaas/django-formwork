"""Floating label for the input and textarea widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms
from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from django.forms.renderers import BaseRenderer
    from django.utils.safestring import SafeString


class FloatingLabelMixin(forms.Widget):
    """Render the control inside DaisyUI's floating-label wrapper, reusing the placeholder as the label.

    The wrapper template includes the widget's own template, so any input template works unchanged.
    """

    floating_wrapper_template = "formwork/widgets/floating_label.html"

    def __init__(self, *args: Any, floating: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.floating = floating

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["floating"] = self.floating
        if self.floating:
            placeholder = widget["attrs"].get("placeholder", "")
            if not placeholder:
                msg = f"{type(self).__name__}(floating=True) needs a placeholder: it is the label text."
                raise ImproperlyConfigured(msg)
            widget["inner_template_name"] = self.template_name
            widget["floating_label_text"] = placeholder
        return context

    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        if not self.floating:
            return super().render(name, value, attrs, renderer)
        context = self.get_context(name, value, attrs)
        return self._render(self.floating_wrapper_template, context, renderer)  # type: ignore[attr-defined]
