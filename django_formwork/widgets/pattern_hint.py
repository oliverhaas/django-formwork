"""Hint under a text control while its value misses the ``pattern``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

if TYPE_CHECKING:
    from django.utils.functional import Promise


class PatternHintMixin(forms.Widget):
    """Shows ``pattern_hint`` under the control while the value misses its ``pattern``.

    CSS reads the browser's verdict (``partials/pattern_hint.html``). Pair it with a server-side validator.
    """

    pattern_hint: str | Promise = ""

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["pattern_hint"] = self.pattern_hint
        return context
