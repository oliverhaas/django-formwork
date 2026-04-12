"""Toggle widget."""

from __future__ import annotations

from typing import Any

from django import forms


class Toggle(forms.CheckboxInput):
    """Checkbox rendered as a DaisyUI toggle switch.

    Adds the ``toggle`` class so CSS applies the DaisyUI toggle styling
    instead of ``checkbox``.

    Usage::

        agree = forms.BooleanField(widget=Toggle)
    """

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        defaults: dict[str, Any] = {}
        if attrs:
            defaults.update(attrs)
        cls = defaults.get("class", "")
        defaults["class"] = f"toggle {cls}".strip()
        super().__init__(defaults)
