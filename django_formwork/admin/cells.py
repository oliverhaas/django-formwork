"""How a changelist cell or a read-only field shows a value."""

from __future__ import annotations

import datetime as dt
import decimal
import json
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from django.contrib.admin.utils import lookup_field
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import formats, timezone
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import SafeData
from django.utils.translation import gettext

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["BADGE_COLORS", "Cell", "cell_for_field", "cell_for_value", "list_cell"]

# Choices without a colour of their own take these in turn, by their place in the choices.
BADGE_COLORS = ("primary", "secondary", "accent", "info", "success", "warning", "error", "neutral")

CellKind = Literal["empty", "boolean", "badge", "number", "date", "html", "text", "file", "json"]


class Cell(TypedDict):
    """One value, ready for the ``cell`` macro."""

    kind: CellKind
    text: str
    color: str
    url: str


def _cell(kind: CellKind, text: object = "", *, color: str = "", url: str = "") -> Cell:
    return Cell(kind=kind, text=str(text), color=color, url=url)


def badge_color(stored: object, choices: list[object], colors: dict[str, str] | None) -> str:
    key = str(stored)
    if colors and key in colors:
        return colors[key]
    keys = [str(choice) for choice in choices]
    position = keys.index(key) if key in keys else 0
    return BADGE_COLORS[position % len(BADGE_COLORS)]


def cell_for_value(value: object, empty: str, *, boolean: bool = False) -> Cell:
    """A value a display method returned."""
    if boolean or isinstance(value, bool):
        return _cell("empty", empty) if value is None else _cell("boolean", "1" if value else "")
    if value is None or value == "":
        return _cell("empty", empty)
    if isinstance(value, SafeData):
        return _cell("html", value)
    if isinstance(value, dt.datetime):
        return _cell("date", formats.localize(timezone.template_localtime(value)))  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    if isinstance(value, dt.date | dt.time):
        return _cell("date", formats.localize(value))
    if isinstance(value, int | float | decimal.Decimal):
        return _cell("number", formats.number_format(value, force_grouping=True))
    if isinstance(value, list | tuple):
        return _cell("text", ", ".join(str(item) for item in value))
    return _cell("text", value)


def cell_for_field(
    value: Any,
    field: models.Field[Any, Any],
    empty: str,
    *,
    obj: models.Model | None = None,
    colors: dict[str, str] | None = None,
) -> Cell:
    """A model field's value, shown by the field's type."""
    flatchoices = getattr(field, "flatchoices", None)
    if flatchoices:
        if value is None or value == "":
            return _cell("empty", empty)
        labels = dict(flatchoices)
        choices = [choice for choice, _label in flatchoices]
        return _cell("badge", labels.get(value, value), color=badge_color(value, choices, colors))
    if isinstance(field, models.BooleanField):
        return cell_for_value(value, empty, boolean=True)
    if value is None or value == "":
        return _cell("empty", empty)
    if isinstance(field, models.FileField):
        return _cell("file", value, url=getattr(value, "url", "") if value else "")
    if isinstance(field, models.JSONField):
        try:
            return _cell("json", json.dumps(value, ensure_ascii=False, cls=field.encoder))
        except TypeError:
            return _cell("json", value)
    if isinstance(field, models.DecimalField):
        return _cell("number", formats.number_format(value, field.decimal_places, force_grouping=True))
    if isinstance(field, models.IntegerField | models.FloatField):
        return _cell("number", formats.number_format(value, force_grouping=True))
    if isinstance(field, models.DateTimeField | models.DateField | models.TimeField):
        return cell_for_value(value, empty)
    return _cell("text", value)


def list_cell(name: str | Callable[..., Any], obj: models.Model, model_admin: Any) -> Cell:
    """One ``list_display`` entry of one row, the way ``ChangeList`` result rows read it."""
    empty = model_admin.get_empty_value_display()
    try:
        field, attr, value = lookup_field(name, obj, model_admin)
    except ObjectDoesNotExist:
        return _cell("empty", empty)
    if field is None or (field.auto_created and not field.concrete):
        empty = getattr(attr, "empty_value_display", empty)
        return cell_for_value(value, empty, boolean=getattr(attr, "boolean", False))
    if isinstance(field.remote_field, models.ManyToOneRel):
        related = getattr(obj, field.name)
        return _cell("empty", empty) if related is None else _cell("text", related)
    colors = getattr(model_admin, "list_badges", {}).get(name) if isinstance(name, str) else None
    return cell_for_field(value, field, empty, obj=obj, colors=colors)


def html(cell: Cell) -> str:
    """A cell as markup, for a read-only field outside a template."""
    text = conditional_escape(cell["text"])
    match cell["kind"]:
        case "boolean" if cell["text"]:
            return format_html(
                '<span class="inline-flex text-[color:color-mix(in_oklab,var(--color-success)_75%,var(--color-base-content))]" title="{}"><i class="icon icon-circle-check size-[1.125rem]"'
                ' aria-hidden="true"></i><span class="sr-only">{}</span></span>',
                gettext("Yes"),
                gettext("Yes"),
            )
        case "boolean":
            return format_html(
                '<span class="inline-flex text-base-content/50" title="{}"><i class="icon icon-circle-x size-[1.125rem]"'
                ' aria-hidden="true"></i><span class="sr-only">{}</span></span>',
                gettext("No"),
                gettext("No"),
            )
        case "badge":
            dot = "status" if cell["color"] == "neutral" else f"status status-{cell['color']}"
            return format_html(
                '<span class="badge badge-ghost gap-1.5"><span class="{}" aria-hidden="true"></span>{}</span>',
                dot,
                text,
            )
        case _:
            return str(text)
