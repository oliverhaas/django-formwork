"""How a changelist cell or a read-only field shows a value."""

from __future__ import annotations

import datetime as dt
import decimal
import json
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from django.contrib.admin.utils import NotRelationField, get_fields_from_path, lookup_field
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db import models
from django.utils import formats, timezone
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import SafeData, SafeString, mark_safe
from django.utils.translation import gettext

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

__all__ = [
    "BADGE_COLORS",
    "Cell",
    "annotate_rows",
    "cell_for_field",
    "cell_for_value",
    "display_annotations",
    "display_attr",
    "list_cell",
    "list_field",
    "list_html",
]

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
        return _cell("date", formats.localize(timezone.template_localtime(value)))  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]
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


def list_field(model: type[models.Model], name: str | Callable[..., Any]) -> Any:
    """The model field a ``list_display`` entry shows, the last one of a path such as ``author__country``."""
    if not isinstance(name, str):
        return None
    try:
        return get_fields_from_path(model, name)[-1]
    except FieldDoesNotExist, NotRelationField:
        return None


def display_attr(entry: str | Callable[..., Any], model_admin: Any) -> Any:
    """What a column or a read-only entry names on the admin or else on the model, as ``lookup_field`` looks."""
    if callable(entry):
        return entry
    attr = getattr(model_admin, entry, None) if entry != "__str__" else None
    if attr is None:
        attr = getattr(model_admin.model, entry, None)
    return attr.fget if isinstance(attr, property) else attr


def display_annotations(entries: Iterable[str | Callable[..., Any]], model_admin: Any) -> list[dict[str, Any]]:
    """The ``annotate`` of each ``@display`` function that ``entries`` name and that has one."""
    annotations = (getattr(display_attr(entry, model_admin), "admin_annotations", None) for entry in entries)
    return [annotate for annotate in annotations if annotate]


def annotate_rows(rows: Iterable[models.Model], annotations: Iterable[Mapping[str, Any]]) -> None:
    """Set the values of each ``annotate`` on the saved ``rows``, computed for these rows only.

    Each ``annotate`` takes a query of its own, so the joins of two columns do not multiply each other's counts.
    """
    saved = [row for row in rows if row.pk is not None]
    if not saved:
        return
    queryset = type(saved[0])._base_manager.db_manager(saved[0]._state.db).filter(pk__in=[row.pk for row in saved])
    for annotate in annotations:
        values = queryset.order_by().values("pk").annotate(**annotate).values_list("pk", *annotate)
        by_pk = {pk: rest for pk, *rest in values}
        for row in saved:
            for name, value in zip(annotate, by_pk.get(row.pk, ()), strict=False):
                setattr(row, name, value)


def list_cell(name: str | Callable[..., Any], obj: models.Model, model_admin: Any) -> Cell:
    """One ``list_display`` entry of one row, the way ``ChangeList`` result rows read it."""
    empty = model_admin.get_empty_value_display()
    try:
        field, attr, value = lookup_field(name, obj, model_admin)
    except ObjectDoesNotExist:
        return _cell("empty", empty)
    if field is None:
        # Django's list shows the value of a path such as "author__country" by the path's last field.
        field = list_field(model_admin.model, name)
    if field is None or (field.auto_created and not field.concrete):
        empty = getattr(attr, "empty_value_display", empty)
        return cell_for_value(value, empty, boolean=getattr(attr, "boolean", False))
    if isinstance(field.remote_field, models.ManyToOneRel):
        return _cell("empty", empty) if value is None else _cell("text", value)
    colors = getattr(model_admin, "list_badges", {}).get(name) if isinstance(name, str) else None
    return cell_for_field(value, field, empty, obj=obj, colors=colors)


def list_html(cell: Cell) -> SafeString:
    """A cell as markup, as the list and the import preview show it."""
    text = cell["text"]
    match cell["kind"]:
        case "empty":
            return format_html('<span class="text-base-content/35">{}</span>', text)
        case "boolean" if text:
            return format_html(
                '<span class="inline-flex align-middle text-[color:color-mix(in_oklab,var(--color-success)_75%,var(--color-base-content))]" title="{}"><i class="icon icon-circle-check size-[1.125rem]"'
                ' aria-hidden="true"></i><span class="sr-only">{}</span></span>',
                gettext("Yes"),
                gettext("Yes"),
            )
        case "boolean":
            return format_html(
                '<span class="inline-flex align-middle text-base-content/50" title="{}"><i class="icon icon-circle-x size-[1.125rem]"'
                ' aria-hidden="true"></i><span class="sr-only">{}</span></span>',
                gettext("No"),
                gettext("No"),
            )
        case "badge":
            color = "badge-ghost" if cell["color"] == "neutral" else f"badge-soft badge-{cell['color']}"
            return format_html('<span class="badge badge-sm whitespace-nowrap {}">{}</span>', color, text)
        case "number":
            return format_html('<span class="tabular-nums">{}</span>', text)
        case "date":
            return format_html('<span class="whitespace-nowrap tabular-nums">{}</span>', text)
        case "html":
            return mark_safe(text)  # noqa: S308 (an "html" cell holds markup the project returned as safe)
        case "file" if cell["url"]:
            return format_html(
                '<a class="link link-hover link-primary inline-flex items-center gap-1" href="{}"><i class="icon icon-paperclip size-3.5" aria-hidden="true"></i>{}</a>',
                cell["url"],
                text.rsplit("/", 1)[-1],
            )
        case "json":
            return format_html(
                '<code class="block max-w-xs truncate font-mono text-xs text-base-content/70">{}</code>', text
            )
        case _:
            return conditional_escape(text)


def html(cell: Cell) -> str:
    """A cell as markup, for a read-only field outside a template."""
    match cell["kind"]:
        case "boolean":
            return list_html(cell)
        case "badge":
            color = "badge-ghost" if cell["color"] == "neutral" else f"badge-soft badge-{cell['color']}"
            return format_html('<span class="badge {}">{}</span>', color, cell["text"])
        case _:
            return str(conditional_escape(cell["text"]))
