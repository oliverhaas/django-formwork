"""Native date input, and a start and end date as one control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence


class DateInput(forms.DateInput):
    """Native date input.

    Django's own widget renders ``type="text"`` with a locale format; the native control accepts only ISO.
    """

    input_type = "date"

    def __init__(self, attrs: dict[str, Any] | None = None, format: str = "%Y-%m-%d") -> None:  # noqa: A002
        super().__init__(attrs=attrs, format=format)


class DateRangeInput(forms.MultiWidget):
    """Start and end date side by side under one field label.

    The pair carries the visible label, so each input names itself to screen readers only.
    """

    template_name = "formwork/widgets/date_range.html"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__([DateInput(), DateInput()], attrs)
        self.sub_labels = (_("From"), _("To"))

    def decompress(self, value: object) -> list[dt.date | None]:
        if not value:
            return [None, None]
        start, end = cast("Sequence[dt.date | None]", value)
        return [start, end]

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        for subwidget, label in zip(context["widget"]["subwidgets"], self.sub_labels, strict=True):
            subwidget["label"] = label
        return context
