"""A read-only value in the box of a filled field."""

from __future__ import annotations

from typing import Any

from django import forms

from .select import ChoiceLabel


class Display(forms.Widget):
    """A value the user cannot change, in the box of a filled field. It posts nothing.

    Each item is a string or a ``ChoiceLabel``; with ``badges``, each item is a badge in its ``color``.
    """

    template_name = "formwork/widgets/display.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, badges: bool = False) -> None:
        super().__init__(attrs)
        self.badges = badges

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        if value is None or value == "":
            values: list[object] = []
        elif isinstance(value, list | tuple):
            values = list(value)
        else:
            values = [value]
        widget = context["widget"]
        widget["items"] = [item if isinstance(item, ChoiceLabel) else ChoiceLabel(str(item)) for item in values]
        widget["badges"] = self.badges
        # A <div> takes no form attributes, so the template reads only these two.
        widget["aria_labelledby"] = widget["attrs"].get("aria-labelledby")
        widget["aria_describedby"] = widget["attrs"].get("aria-describedby")
        return context

    def id_for_label(self, id_: str) -> str:  # noqa: ARG002
        return ""
