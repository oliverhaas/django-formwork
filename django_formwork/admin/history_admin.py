"""The history list of a model: every change of its rows, newest first, from the history backend's table."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

import django_filters
from django.contrib.admin.utils import quote
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from django_formwork.admin import jinja
from django_formwork.admin.changelist import ChangeList
from django_formwork.admin.filters import DateRangeFilter, ObjectFilter, _floating
from django_formwork.admin.history import ADD, CHANGE, DELETE, Change, Entry, HistorySource
from django_formwork.admin.options import ModelAdmin
from django_formwork.widgets import ChoiceLabel, Select

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django import forms
    from django.db import models
    from django.http import HttpRequest, HttpResponse

    from django_formwork.widgets.select import BadgeColor

__all__ = ["HistoryAdmin"]

ACTIONS = {
    ADD: (gettext_lazy("Added"), "success"),
    CHANGE: (gettext_lazy("Changed"), "info"),
    DELETE: (gettext_lazy("Deleted"), "error"),
}


class HistoryChangeList(ChangeList):
    """The history list's rows link their object's change page, without the list's filters."""

    def url_for_result(self, result: models.Model) -> str:
        obj = result.history_object  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        if obj is None:
            return ""
        parent = self.model_admin.parent
        return reverse(parent.url_name("change"), args=(quote(obj.pk),), current_app=parent.admin_site.name)

    def change_url(self, result: models.Model) -> str:
        return self.url_for_result(result)


class HistoryAdmin(ModelAdmin):
    """The read-only history list of the model of ``parent``, the model's admin.

    The columns and filters take ``time``, ``object``, ``user``, ``action`` and ``changes``, besides
    the fields of the history's table and admin methods. The export also takes ``object_id``."""

    list_display: Sequence[Any] = ("time", "object", "user", "action", "changes")
    list_filter: Sequence[Any] = ("action", "user", "time")
    list_display_links: Sequence[Any] | None = ("object",)
    list_per_page = 50
    actions = None
    export_fields: Sequence[Any] | None = ("time", "object", "object_id", "user", "action", "changes")
    # A background export finds its admin among the site's registered ones, which this one is not.
    export_background_threshold = None
    change_list_template = "formwork_admin/history_list.html"
    history_admin = None

    def __init__(self, parent: ModelAdmin, source: HistorySource) -> None:
        self.parent = parent
        self.source = source
        super().__init__(source.model, parent.admin_site)
        self.ordering = source.ordering

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Any]:
        """Every change of the model. The list leaves out no row of objects that ``parent`` hides."""
        return self.source.queryset()

    def get_icon(self) -> str:
        return self.parent.get_icon()

    @property
    def media(self) -> forms.Media:
        return self.parent.media

    def export_name(self) -> str:
        return _("%(name)s history") % {"name": self.parent.opts.verbose_name}

    def url_name(self, view: str) -> str:
        return self.parent.url_name({"changelist": "history_list", "export": "history_export"}.get(view, view))

    # Permissions: whoever sees the model's rows sees their history, and nobody edits it.

    def has_view_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return self.parent.has_view_or_change_permission(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return False

    def has_import_permission(self, request: HttpRequest) -> bool:
        return False

    # The list

    def get_changelist(self, request: HttpRequest, **kwargs: Any) -> type[ChangeList]:
        return HistoryChangeList

    def get_changelist_instance(self, request: HttpRequest) -> ChangeList:
        cl = super().get_changelist_instance(request)
        cl.title = _("%(name)s history") % {"name": capfirst(self.parent.opts.verbose_name)}
        return cl

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        context = {
            "parent_admin": self.parent,
            "parent_changelist_url": reverse(self.parent.url_name("changelist"), current_app=self.admin_site.name),
            "items_name": _("changes"),
            "empty_hint": _("Each change to a %(name)s appears here.") % {"name": self.parent.opts.verbose_name},
            **(extra_context or {}),
        }
        return super().changelist_view(request, context)

    def prepare_rows(self, request: HttpRequest, rows: list[Any]) -> None:
        """Each row's entry and its object, in one query per page for the objects."""
        entries = self.source.entries(rows)
        pk_field = self.parent.opts.pk
        pks = set()
        for entry in entries:
            try:
                pks.add(pk_field.to_python(entry.object_id))
            except ValidationError:
                continue
        found = self.parent.get_queryset(request).in_bulk(pks) if pks else {}
        objects = {str(pk): obj for pk, obj in found.items()}
        for row, entry in zip(rows, entries, strict=True):
            row.history_entry = entry
            row.history_object = objects.get(entry.object_id)

    def get_list_display(self, request: HttpRequest) -> Sequence[Any]:
        return [self._columns.get(name, name) if isinstance(name, str) else name for name in self.list_display]

    def get_list_display_links(self, request: HttpRequest, list_display: Sequence[Any]) -> Sequence[Any] | None:
        links = self.list_display_links
        if links is None:
            return None
        return [self._columns.get(name, name) if isinstance(name, str) else name for name in links]

    def get_list_filter(self, request: HttpRequest) -> Sequence[Any]:
        # The object filter comes first, so the bar shows it, and a link to one object's history works.
        names = ["object", *(name for name in self.list_filter if name != "object")]
        return [self._filters.get(name, name) if isinstance(name, str) else name for name in names]

    def get_export_fields(self, request: HttpRequest) -> Sequence[Any]:
        fields = self.export_fields or ()
        return [self._export_columns.get(name, name) if isinstance(name, str) else name for name in fields]

    @cached_property
    def _columns(self) -> dict[str, Callable[[Any], Any]]:
        """The list's columns by name, as functions: a name alone would read a field of the table first."""

        def time(row: Any) -> Any:
            return row.history_entry.time

        def object_(row: Any) -> Any:
            if row.history_object is not None:
                return str(row.history_object)
            name = self.source.name(row, row.history_entry) or f"#{row.history_entry.object_id}"
            return format_html(
                '<span class="text-base-content/60">{}</span> <span class="text-xs text-base-content/50">({})</span>',
                name,
                _("deleted"),
            )

        def user(row: Any) -> Any:
            return row.history_entry.user or None

        def action(row: Any) -> Any:
            label, color = ACTIONS[row.history_entry.action]
            return format_html(
                '<span class="badge badge-sm whitespace-nowrap badge-soft badge-{}">{}</span>', color, label
            )

        def changes(row: Any) -> Any:
            shown = _shown(row.history_entry)
            if not shown:
                return None
            template = jinja.select_template(["formwork_admin/history_changes.html"])
            return mark_safe(template.render({"changes": shown}))  # noqa: S308

        object_.__name__ = "object"
        labels = {
            time: (gettext_lazy("Time"), self.source.ordering[0].removeprefix("-")),
            object_: (gettext_lazy("Object"), None),
            user: (gettext_lazy("User"), None),
            action: (gettext_lazy("Action"), None),
            changes: (gettext_lazy("Changes"), None),
        }
        for column, (label, order) in labels.items():
            column.short_description = label  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            if order:
                column.admin_order_field = order  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        return {column.__name__: column for column in labels}

    @cached_property
    def _export_columns(self) -> dict[str, Callable[[Any], Any]]:
        """The export's columns by name: the values as text, without the list's markup."""

        def time(row: Any) -> Any:
            return row.history_entry.time

        def object_(row: Any) -> Any:
            if row.history_object is not None:
                return str(row.history_object)
            return self.source.name(row, row.history_entry)

        def object_id(row: Any) -> Any:
            return row.history_entry.object_id

        def user(row: Any) -> Any:
            return row.history_entry.user

        def action(row: Any) -> Any:
            return row.history_entry.action

        def changes(row: Any) -> Any:
            return "; ".join(_change_text(change) for change in _shown(row.history_entry))

        object_.__name__ = "object"
        return {column.__name__: column for column in (time, object_, object_id, user, action, changes)}

    @cached_property
    def _filters(self) -> dict[str, Any]:
        """The list's filters by name, built once, as the filter bar keeps one class per ``list_filter``."""
        source = self.source

        def by_object(queryset: Any, name: str, value: Any) -> Any:
            return queryset.filter(source.for_object(value.pk))

        def by_user(queryset: Any, name: str, value: Any) -> Any:
            return queryset.filter(source.for_user(value.pk))

        def by_action(queryset: Any, name: str, value: Any) -> Any:
            return queryset.filter(source.for_action(value))

        from django.contrib.auth import get_user_model

        label = capfirst(self.parent.opts.verbose_name)
        choices = [
            (value, ChoiceLabel(str(title), color=cast("BadgeColor", color)))
            for value, (title, color) in ACTIONS.items()
        ]
        return {
            "object": ObjectFilter(self.parent.model, field_name="object", label=label, method=by_object),
            "user": ObjectFilter(get_user_model(), field_name="user", label=_("User"), method=by_user),
            "action": django_filters.ChoiceFilter(
                field_name="action",
                label=_("Action"),
                choices=choices,
                empty_label=_("All"),
                method=by_action,
                widget=Select(badges=True, show_search=False, **_floating(_("Action"))),
            ),
            "time": DateRangeFilter(field_name=source.time_field, label=_("Time")),
        }


def _shown(entry: Entry) -> list[Change]:
    """The changes worth a line: an addition or a deletion alone says no more than the action."""
    plain = {_("Added."), _("Deleted.")}
    return [change for change in entry.changes if change.fields or change.target or change.text not in plain]


def _change_text(change: Change) -> str:
    if not change.has_values:
        return change.text
    values = [
        f"{capfirst(field.label)}: {field.old or ''} → {field.new or ''}" if field.has_values else capfirst(field.label)
        for field in change.fields
    ]
    text = ", ".join(values)
    return f"{change.target}: {text}" if change.target else text
