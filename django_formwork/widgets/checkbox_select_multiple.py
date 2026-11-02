"""Django's own checkbox group, laid out in columns."""

from __future__ import annotations

from typing import Any, ClassVar

from django import forms


class CheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """Drop-in for Django's widget; pass ``columns=2`` for a two-column grid."""

    # Full class strings so Tailwind's source scan keeps them.
    COLUMN_CLASSES: ClassVar[dict[int, str]] = {2: "!grid grid-cols-2 gap-x-1"}

    def __init__(self, *args: Any, columns: int = 1, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.columns = columns

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        # Set after the options are built, so the layout stays off the inputs.
        if layout := self.COLUMN_CLASSES.get(self.columns):
            context["widget"]["attrs"]["class"] = layout
        return context
