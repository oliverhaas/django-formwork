"""Text input and textarea with an optional floating label."""

from __future__ import annotations

from typing import Any

from django import forms

from .floating import FloatingLabelMixin
from .pattern_hint import PatternHintMixin


class TextInput(PatternHintMixin, FloatingLabelMixin, forms.TextInput):
    """``forms.TextInput`` with an optional floating label and pattern hint.

    ``input_type`` covers the text-like types (``email``, ``tel``, ``url``) without a widget per type.
    """

    template_name = "formwork/widgets/text_input.html"

    def __init__(
        self, attrs: dict[str, Any] | None = None, *, floating: bool = False, input_type: str | None = None
    ) -> None:
        super().__init__(attrs, floating=floating)
        # Django's Input already took a `type` from attrs.
        if input_type is not None:
            self.input_type = input_type


class Textarea(FloatingLabelMixin, forms.Textarea):
    """``forms.Textarea`` with an optional floating label."""

    def __init__(self, attrs: dict[str, Any] | None = None, *, floating: bool = False) -> None:
        super().__init__(attrs, floating=floating)
