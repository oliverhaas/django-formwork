"""Native date input."""

from __future__ import annotations

from typing import Any

from django import forms


class DateInput(forms.DateInput):
    """Native date input.

    Django's own widget renders ``type="text"`` with a locale format; the native control accepts only ISO.
    """

    input_type = "date"

    def __init__(self, attrs: dict[str, Any] | None = None, format: str = "%Y-%m-%d") -> None:  # noqa: A002
        super().__init__(attrs=attrs, format=format)
