"""Range widget."""

from __future__ import annotations

from django import forms


class Range(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI.

    Usage::

        from django_formwork.widgets import Range

        volume = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100}))
    """

    input_type = "range"
