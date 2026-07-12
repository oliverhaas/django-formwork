"""InputNumber widget."""

from __future__ import annotations

from django import forms

from ._base import _ModuleScript


class InputNumber(forms.NumberInput):
    """Number input with increment/decrement buttons.

    Wraps a standard ``<input type="number">`` with +/- buttons.
    Uses Alpine.js for the stepping logic.

    Usage::

        quantity = forms.IntegerField(widget=InputNumber(attrs={"min": "1", "max": "99"}))
    """

    template_name = "formwork/widgets/input_number.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/input_number.js"),)
