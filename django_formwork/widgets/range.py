"""Range widget."""

from __future__ import annotations

from django import forms


class Range(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI.

    CSS targets ``input[type="range"]`` directly; no extra attributes
    needed.

    Usage::

        volume = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100}))
    """

    input_type = "range"
