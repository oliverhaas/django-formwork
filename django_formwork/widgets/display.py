"""A read-only value in the box of a filled field, and a value cut to a few lines."""

from __future__ import annotations

from typing import Any

from django import forms
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.timezone import template_localtime  # type: ignore[attr-defined]  # ty: ignore[missing-module-member]  (missing from django-stubs)
from django.utils.translation import pgettext

from ._base import _FormworkTemplatesMixin
from .select import ChoiceLabel

__all__ = ["MAX_LINES", "Display", "check_max_lines", "clamp"]

# The line counts that clamp() takes; formwork.css builds a line-clamp class for each.
MAX_LINES = range(1, 11)


def check_max_lines(max_lines: int | None) -> None:
    """Raise ``ValueError`` unless ``max_lines`` is ``None`` or a count that ``clamp()`` takes."""
    if max_lines is not None and max_lines not in MAX_LINES:
        msg = f"max_lines must be None or {MAX_LINES.start} to {MAX_LINES.stop - 1}, not {max_lines!r}."
        raise ValueError(msg)


def clamp(content: object, max_lines: int | None) -> Any:  # noqa: ANN401
    """``content`` cut to ``max_lines`` lines, with a [more] toggle that shows the rest; ``None`` leaves it whole.

    The toggle shows only when the lines overflow, and keeps its room either way, so the box keeps its width.
    """
    if max_lines is None:
        return content
    return format_html(
        '<div class="formwork-clamp"><div class="formwork-clamp-body line-clamp-{}">{}</div>'
        '<details><summary data-more="{}" data-less="{}"></summary></details></div>',
        max_lines,
        localize(template_localtime(content)),
        pgettext("help text toggle", "[more]"),
        pgettext("help text toggle", "[less]"),
    )


class Display(_FormworkTemplatesMixin, forms.Widget):
    """A value the user cannot change, in the box of a filled field. It posts nothing.

    Each item is a string or a ``ChoiceLabel``; with ``badges``, each item is a badge in its ``color``.
    With ``max_lines``, the box shows that many lines and a [more] toggle for the rest.
    """

    template_name = "formwork/widgets/display.html"

    def __init__(
        self, attrs: dict[str, Any] | None = None, *, badges: bool = False, max_lines: int | None = None
    ) -> None:
        super().__init__(attrs)
        check_max_lines(max_lines)
        self.badges = badges
        self.max_lines = max_lines

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
        widget["max_lines"] = self.max_lines
        # A <div> takes no form attributes, so the template reads only these two.
        widget["aria_labelledby"] = widget["attrs"].get("aria-labelledby")
        widget["aria_describedby"] = widget["attrs"].get("aria-describedby")
        return context

    def id_for_label(self, id_: str) -> str:  # noqa: ARG002
        return ""
