"""Checkbox drawn as a switch."""

from __future__ import annotations

from typing import Any

from django import forms


class ToggleInput(forms.CheckboxInput):
    """Checkbox drawn as a DaisyUI toggle switch, with the field label beside it.

    ``field.html`` renders the label beside the switch; the ``toggle`` class swaps the checkbox styling.
    """

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        attrs = dict(attrs or {})
        attrs["class"] = f"toggle {attrs.get('class', '')}".strip()
        super().__init__(attrs)
