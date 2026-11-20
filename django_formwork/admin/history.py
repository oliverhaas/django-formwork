"""The admin's history: who changed an object, when, and the values before and after.

``AdminSite.history`` holds the backend. ``ModelHistory`` keeps the entries in the admin's own
table. ``PghistoryHistory`` shows the events of django-pghistory for the models it tracks.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import decimal
import itertools
from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils import formats, timezone, translation
from django.utils.text import capfirst, get_text_list
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence

    from django.contrib.contenttypes.models import ContentType
    from django.http import HttpRequest

__all__ = [
    "ADD",
    "CHANGE",
    "DELETE",
    "Change",
    "Entry",
    "EntrySource",
    "EventSource",
    "FieldChange",
    "History",
    "HistorySource",
    "ModelHistory",
    "PghistoryHistory",
    "change_message",
]

ADD, CHANGE, DELETE = "add", "change", "delete"
# A longer value is cut, so one text field cannot fill the table.
VALUE_LIMIT = 300


@dataclass(frozen=True)
class FieldChange:
    """One changed field. ``old`` and ``new`` are ``None`` when the entry has no values, as for a password."""

    label: str
    old: str | None = None
    new: str | None = None

    @property
    def has_values(self) -> bool:
        return self.old is not None or self.new is not None


@dataclass(frozen=True)
class Change:
    """One line of an entry: the object itself, or a row of an inline, with the fields that changed."""

    text: str
    fields: tuple[FieldChange, ...] = ()
    #: The inline row the fields belong to, such as 'Part "Wheel"'; empty for the object itself.
    target: str = ""

    @property
    def has_values(self) -> bool:
        return any(field.has_values for field in self.fields)


@dataclass(frozen=True)
class Entry:
    """One save, addition or deletion, as the history panel and the index show it."""

    action: str
    time: dt.datetime
    user: str
    changes: tuple[Change, ...]
    object_repr: str = ""
    content_type: ContentType | None = None
    object_id: str = ""


class History:
    """Where the admin writes its history and where the pages read it."""

    def log(self, request: HttpRequest, objects: Iterable[models.Model], action: str, message: Any = "") -> None:
        """Record ``action`` on each object. ``message`` is the list of ``change_message`` or a text."""
        raise NotImplementedError

    def entries(self, request: HttpRequest, obj: models.Model, start: int, stop: int) -> list[Entry]:
        """The entries of ``obj`` from ``start`` to ``stop``, newest first."""
        raise NotImplementedError

    def recent(self, request: HttpRequest, limit: int) -> list[Entry]:
        """The last entries of the user who made the request."""
        raise NotImplementedError

    def source(self, model: type[models.Model]) -> HistorySource | None:
        """The table the history list of ``model`` shows; None for a backend without one."""
        return None

    @contextlib.contextmanager
    def context(self, request: HttpRequest) -> Generator[None]:
        """Wraps each admin view, so a backend can tie the database writes to the request."""
        yield


class ModelHistory(History):
    """Entries in the admin's own table, written by the admin views."""

    def log(self, request: HttpRequest, objects: Iterable[models.Model], action: str, message: Any = "") -> None:
        from django.contrib.contenttypes.models import ContentType

        from django_formwork.admin.models import HistoryEntry

        user = request.user if request.user.is_authenticated else None
        changes, text = (message, "") if isinstance(message, list) else ([], str(message or ""))
        HistoryEntry.objects.bulk_create(
            HistoryEntry(
                user=cast("Any", user),
                content_type=ContentType.objects.get_for_model(obj, for_concrete_model=False),
                object_id=str(obj.pk),
                object_repr=str(obj)[:200],
                action=action,
                changes=changes,
                message=text,
            )
            for obj in objects
        )

    def entries(self, request: HttpRequest, obj: models.Model, start: int, stop: int) -> list[Entry]:
        from django.contrib.contenttypes.models import ContentType

        from django_formwork.admin.models import HistoryEntry

        rows = HistoryEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj, for_concrete_model=False), object_id=str(obj.pk)
        ).fetch_mode(models.FETCH_PEERS)
        return [_entry(row) for row in rows[start:stop]]

    def recent(self, request: HttpRequest, limit: int) -> list[Entry]:
        from django_formwork.admin.models import HistoryEntry

        if not request.user.is_authenticated:
            return []
        rows = HistoryEntry.objects.filter(user_id=cast("Any", request.user.pk)).fetch_mode(models.FETCH_PEERS)
        return [_entry(row) for row in rows[:limit]]

    def source(self, model: type[models.Model]) -> HistorySource | None:
        return EntrySource(model)


class PghistoryHistory(ModelHistory):
    """The events of django-pghistory for the models it tracks, the admin's own entries for the others.

    The admin keeps writing its own entries, which the index lists as recent actions. Each admin view
    runs in ``pghistory.context`` with the user and the URL, so an event records who made it.
    """

    @contextlib.contextmanager
    def context(self, request: HttpRequest) -> Generator[None]:
        import pghistory

        if not request.user.is_authenticated:
            yield
            return
        with pghistory.context(user=request.user.pk, url=request.path):
            yield

    def entries(self, request: HttpRequest, obj: models.Model, start: int, stop: int) -> list[Entry]:
        from pghistory.core import event_models
        from pghistory.models import Events

        if not event_models(tracks_model=type(obj)._meta.concrete_model):
            return super().entries(request, obj, start, stop)
        tracked = Events.objects.tracks(obj)  # ty: ignore[unresolved-attribute]
        events = list(tracked.order_by("-pgh_created_at", "-pgh_id")[start:stop])
        users = _users({(event.pgh_context or {}).get("user") for event in events})
        values = _related_values(type(obj), [event.pgh_diff or {} for event in events])
        entries = []
        for event in events:
            user = users.get(str((event.pgh_context or {}).get("user")), "")
            entries.append(_event_entry(event, type(obj), user, event.pgh_diff, values))
        return entries

    def source(self, model: type[models.Model]) -> HistorySource | None:
        from pghistory.core import event_models

        tracking = event_models(tracks_model=model._meta.concrete_model)
        return EventSource(model, tracking[0]) if tracking else super().source(model)


# The history list


class HistorySource:
    """The table a model's history list shows, one row per change.

    A backend returns one from ``History.source()``. The list pages the rows of ``queryset()``,
    newest first by ``ordering``, and reads each page at once through ``entries()``.
    """

    #: The table, such as the admin's ``HistoryEntry`` or a pghistory event model.
    model: type[models.Model]
    #: The column the list's date filter reads.
    time_field: str
    #: Newest first, best with an index. The list's Time column sorts by the first field.
    ordering: tuple[str, ...]

    def __init__(self, tracked: type[models.Model]) -> None:
        #: The model whose changes the table holds.
        self.tracked = tracked

    def queryset(self) -> models.QuerySet[Any]:
        """The rows of the tracked model's changes."""
        raise NotImplementedError

    def entries(self, rows: Sequence[Any]) -> list[Entry]:
        """One entry per row, in the rows' order. ``object_id`` names the changed object."""
        raise NotImplementedError

    def name(self, row: Any, entry: Entry) -> str:
        """The name of a row's object after it was deleted."""
        return entry.object_repr

    def for_action(self, action: str) -> models.Q:
        """The rows of one action: ``ADD``, ``CHANGE`` or ``DELETE``."""
        raise NotImplementedError

    def for_user(self, pk: Any) -> models.Q:
        """The rows of the changes one user made."""
        raise NotImplementedError

    def for_object(self, pk: Any) -> models.Q:
        """The rows of one object."""
        raise NotImplementedError


class EntrySource(HistorySource):
    """The admin's own ``HistoryEntry`` table."""

    time_field = "time"
    ordering = ("-time", "-pk")

    def __init__(self, tracked: type[models.Model]) -> None:
        from django_formwork.admin.models import HistoryEntry

        super().__init__(tracked)
        self.model = HistoryEntry

    def queryset(self) -> models.QuerySet[Any]:
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(self.tracked, for_concrete_model=False)
        return self.model._default_manager.filter(content_type=content_type).fetch_mode(models.FETCH_PEERS)

    def entries(self, rows: Sequence[Any]) -> list[Entry]:
        return [_entry(row) for row in rows]

    def for_action(self, action: str) -> models.Q:
        return models.Q(action=action)

    def for_user(self, pk: Any) -> models.Q:
        return models.Q(user=pk)

    def for_object(self, pk: Any) -> models.Q:
        return models.Q(object_id=str(pk))


class EventSource(HistorySource):
    """A pghistory event model of the tracked model.

    The list reads the event table itself, not pghistory's ``Events``, which works out each
    event's diff across the whole table before a filter or a page applies. Here a page loads the
    event before each of its rows in one more query and compares the two.
    """

    time_field = "pgh_created_at"
    # The primary key follows the order of the events and has the index that pgh_created_at lacks.
    ordering = ("-pgh_id",)

    def __init__(self, tracked: type[models.Model], model: type[models.Model]) -> None:
        super().__init__(tracked)
        self.model = model
        self.fields = [field for field in model._meta.concrete_fields if not field.name.startswith("pgh_")]
        try:
            context = model._meta.get_field("pgh_context")
        except FieldDoesNotExist:
            context = None
        # A context is a row of pghistory's Context table, or a JSON field on the event itself.
        self.context_path = (
            None if context is None else "pgh_context__metadata" if context.is_relation else "pgh_context"
        )

    def queryset(self) -> models.QuerySet[Any]:
        return self.model._default_manager.all().fetch_mode(models.FETCH_PEERS)

    def entries(self, rows: Sequence[Any]) -> list[Entry]:
        previous = self._previous(rows)
        diffs = [self._diff(previous.get(row.pk), row) for row in rows]
        users = _users({self._context(row).get("user") for row in rows})
        values = _related_values(self.tracked, [diff or {} for diff in diffs])
        return [
            _event_entry(row, self.tracked, users.get(str(self._context(row).get("user")), ""), diff, values)
            for row, diff in zip(rows, diffs, strict=True)
        ]

    def for_action(self, action: str) -> models.Q:
        events = self.model._default_manager
        first = ~models.Exists(
            events.filter(pgh_obj_id=models.OuterRef("pgh_obj_id"), pgh_id__lt=models.OuterRef("pgh_id"))
        )
        # As _event_entry reads the labels of pghistory's own trackers.
        added = models.Q(pgh_label="insert") | (models.Q(pgh_label="snapshot") & models.Q(first))
        if action == ADD:
            return added
        if action == DELETE:
            return models.Q(pgh_label="delete")
        return ~added & ~models.Q(pgh_label="delete")

    def for_user(self, pk: Any) -> models.Q:
        if self.context_path is None:
            return models.Q(pk__in=[])
        # The JSON keeps the key as the context got it, a number or a text.
        return models.Q(**{f"{self.context_path}__user": pk}) | models.Q(**{f"{self.context_path}__user": str(pk)})

    def for_object(self, pk: Any) -> models.Q:
        return models.Q(pgh_obj_id=pk)

    def name(self, row: Any, entry: Entry) -> str:
        """The object's name from the values the event keeps, as the object had them."""
        names = {field.attname for field in self.tracked._meta.concrete_fields}
        obj = self.tracked(
            **{field.attname: getattr(row, field.attname) for field in self.fields if field.attname in names}
        )
        try:
            return str(obj)
        except ObjectDoesNotExist, AttributeError, TypeError, ValueError:
            return ""

    def _context(self, row: Any) -> dict[str, Any]:
        if self.context_path is None:
            return {}
        context = row.pgh_context
        return (getattr(context, "metadata", context) or {}) if context is not None else {}

    def _previous(self, rows: Sequence[Any]) -> dict[Any, Any]:
        """The event before each row of the same object, by ``pgh_id`` as pghistory's diff orders them."""
        events = self.model._default_manager
        before = events.filter(pgh_obj_id=models.OuterRef("pgh_obj_id"), pgh_id__lt=models.OuterRef("pgh_id"))
        before_ids = events.filter(pk__in=[row.pk for row in rows]).values(
            before=models.Subquery(before.order_by("-pgh_id").values("pgh_id")[:1])
        )
        # The rows and the events before them, in order per object: each row follows its own.
        by_object: dict[Any, dict[Any, Any]] = {}
        found: list[Any] = [*events.filter(pk__in=before_ids), *rows]
        for event in found:
            by_object.setdefault(event.pgh_obj_id, {})[event.pk] = event
        previous = {}
        for object_events in by_object.values():
            for earlier, later in itertools.pairwise(sorted(object_events.values(), key=attrgetter("pk"))):
                previous[later.pk] = earlier
        return previous

    def _diff(self, before: Any, after: Any) -> dict[str, list[Any]] | None:
        """The changed columns, as pghistory's ``pgh_diff`` has them; None for an object's first event."""
        if before is None:
            return None
        diff = {}
        for field in self.fields:
            old, new = field.value_from_object(before), field.value_from_object(after)
            if old != new:
                diff[cast("str", field.column)] = [old, new]
        return diff


def _entry(row: Any) -> Entry:
    return Entry(
        action=row.action,
        time=row.time,
        user=_user_name(row.user),
        changes=changes_from_message(row.changes or row.message),
        object_repr=row.object_repr,
        content_type=row.content_type,
        object_id=row.object_id,
    )


def _user_name(user: Any) -> str:
    if user is None:
        return ""
    full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
    return full_name or user.get_username()


def _users(pks: set[Any]) -> dict[str, str]:
    pks.discard(None)
    if not pks:
        return {}
    return {str(user.pk): _user_name(user) for user in get_user_model()._default_manager.filter(pk__in=pks)}


# Writing


def change_message(form: forms.BaseForm, formsets: Sequence[Any], add: bool) -> list[dict[str, Any]]:
    """Django's ``construct_change_message``, with the values before and after each changed field.

    Each ``changed`` item keeps Django's ``fields`` and adds ``values``: one ``[old, new]`` per field,
    or ``None`` for a field whose value stays out of the history, such as a password.
    """
    message: list[dict[str, Any]] = []
    with translation.override(None):
        if add:
            message.append({"added": {}})
        elif form.changed_data:
            message.append({"changed": _changed(form, form.changed_data)})
        for formset in formsets:
            forms_by_object = {id(inline.instance): inline for inline in formset.initial_forms}
            message.extend(
                {"added": {"name": str(added._meta.verbose_name), "object": str(added)}}
                for added in formset.new_objects
            )
            for changed, fields in formset.changed_objects:
                inline_form = forms_by_object.get(id(changed), formset.forms[0])
                message.append(
                    {
                        "changed": {
                            "name": str(changed._meta.verbose_name),
                            "object": str(changed),
                            **_changed(inline_form, fields),
                        }
                    }
                )
            message.extend(
                {"deleted": {"name": str(deleted._meta.verbose_name), "object": str(deleted)}}
                for deleted in formset.deleted_objects
            )
    return message


def _changed(form: forms.BaseForm, names: Sequence[str]) -> dict[str, Any]:
    labels, values = [], []
    for name in names:
        field = form.fields.get(name)
        labels.append(str(field.label or name) if field else name)
        values.append(_form_values(form, field, name) if field else None)
    return {"fields": labels, "values": values}


def _form_values(form: forms.BaseForm, field: forms.Field, name: str) -> list[str] | None:
    if isinstance(field.widget, forms.PasswordInput) or "password" in name:
        return None
    old = form.get_initial_for_field(field, name)
    new = getattr(form, "cleaned_data", {}).get(name)
    return [_form_display(field, old), _form_display(field, new)]


def _form_display(field: forms.Field, value: Any) -> str:
    if value is None or value == "" or (value is False and not isinstance(field, forms.BooleanField)):
        return ""
    if isinstance(field, forms.ModelMultipleChoiceField):
        objs = list(value)
        if objs and not isinstance(objs[0], models.Model) and field.queryset is not None:
            objs = list(field.queryset.filter(pk__in=objs))
        return _cut(", ".join(str(obj) for obj in objs))
    if isinstance(field, forms.ModelChoiceField):
        if not isinstance(value, models.Model):
            with contextlib.suppress(ValidationError):
                value = field.to_python(value)
        return _cut(str(value))
    if isinstance(field, forms.ChoiceField):
        labels = _flat_choices(field.choices)
        if isinstance(value, (list, tuple)):
            return _cut(", ".join(str(labels.get(str(item), item)) for item in value))
        return _cut(str(labels.get(str(value), value)))
    return _display(value)


def _flat_choices(choices: Any) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, label in choices:
        if isinstance(label, (list, tuple)):
            flat.update(_flat_choices(label))
        else:
            flat[str(key)] = label
    return flat


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    if isinstance(value, dt.datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    if isinstance(value, (dt.date, dt.time, decimal.Decimal, float, int)):
        return str(formats.localize(value))
    if isinstance(value, FieldFile):
        return value.name or ""
    if hasattr(value, "name") and hasattr(value, "read"):
        return str(value.name)
    if isinstance(value, (list, tuple, set)):
        return _cut(", ".join(_display(item) for item in value))
    return _cut(str(value))


def _cut(text: str) -> str:
    return text if len(text) <= VALUE_LIMIT else text[: VALUE_LIMIT - 1] + "…"


# Reading


def changes_from_message(message: Any) -> tuple[Change, ...]:
    """The lines of a stored message: the list of ``change_message`` or Django's, or a plain text."""
    if not message:
        return ()
    if isinstance(message, str):
        return (Change(message),)
    changes = []
    for item in message:
        if "added" in item:
            added = item["added"]
            text = (
                _("Added {name} “{object}”.").format(name=_(added["name"]), object=added["object"])
                if added
                else _("Added.")
            )
            changes.append(Change(text))
        elif "changed" in item:
            changed = item["changed"]
            labels = [_(label) for label in changed.get("fields", [])]
            values = changed.get("values") or [None] * len(labels)
            fields = tuple(
                FieldChange(label, *(value or (None, None))) for label, value in zip(labels, values, strict=False)
            )
            field_list = get_text_list(labels, _("and"))
            target = ""
            if "name" in changed:
                text = _("Changed {fields} for {name} “{object}”.").format(
                    fields=field_list, name=_(changed["name"]), object=changed["object"]
                )
                target = f"{capfirst(_(changed['name']))} “{changed['object']}”"
            else:
                text = _("Changed {fields}.").format(fields=field_list)
            changes.append(Change(text, fields, target))
        elif "deleted" in item:
            deleted = item["deleted"]
            changes.append(
                Change(_("Deleted {name} “{object}”.").format(name=_(deleted["name"]), object=deleted["object"]))
            )
    return tuple(changes)


def _event_entry(
    event: Any, model: type[models.Model], user: str, diff: dict[str, Any] | None, values: dict[Any, dict[str, str]]
) -> Entry:
    # The labels of pghistory's own trackers. A snapshot without a diff is the first one, so the insert.
    label = event.pgh_label
    if label == "delete":
        action, text = DELETE, _("Deleted.")
    elif label == "insert" or (label == "snapshot" and diff is None):
        action, text = ADD, _("Added.")
    else:
        action, text = CHANGE, "" if label in {"update", "snapshot"} else capfirst(label.replace("_", " ")) + "."
    fields = []
    for column, (old, new) in (diff or {}).items():
        field = _field_for_column(model, column)
        if field is None:
            continue
        hidden = "password" in field.name
        fields.append(
            FieldChange(
                str(field.verbose_name),
                None if hidden else _field_display(field, old, values),
                None if hidden else _field_display(field, new, values),
            )
        )
    if action == CHANGE and not text:
        labels = [change.label for change in fields]
        text = (
            _("Changed {fields}.").format(fields=get_text_list(labels, _("and"))) if labels else _("No fields changed.")
        )
    return Entry(
        action=action,
        time=event.pgh_created_at,
        user=user,
        changes=(Change(text, tuple(fields)),),
        object_id=str(event.pgh_obj_id or ""),
    )


def _field_for_column(model: type[models.Model], column: str) -> models.Field[Any, Any] | None:
    for field in model._meta.concrete_fields:
        if field.column == column:
            return field
    with contextlib.suppress(FieldDoesNotExist):
        named = model._meta.get_field(column)
        return named if isinstance(named, models.Field) else None
    return None


def _related_values(model: type[models.Model], diffs: list[dict[str, Any]]) -> dict[Any, dict[str, str]]:
    """The names of the objects a foreign key in the diffs points to, one query per related model."""
    wanted: dict[Any, set[Any]] = {}
    for diff in diffs:
        for column, pair in diff.items():
            field = _field_for_column(model, column)
            if field is not None and field.many_to_one:
                wanted.setdefault(field, set()).update(value for value in pair if value is not None)
    names: dict[Any, dict[str, str]] = {}
    for field, pks in wanted.items():
        related = field.related_model
        to_field = field.target_field.attname
        names[field] = {
            str(getattr(obj, to_field)): str(obj) for obj in related._base_manager.filter(**{f"{to_field}__in": pks})
        }
    return names


def _field_display(field: models.Field[Any, Any], value: Any, values: dict[Any, dict[str, str]]) -> str:
    if value is None:
        return ""
    if field.many_to_one:
        return values.get(field, {}).get(str(value), str(value))
    if field.flatchoices:
        return _cut(str(dict(field.flatchoices).get(value, value)))
    with contextlib.suppress(ValidationError, TypeError, ValueError):
        value = field.to_python(value)
    return _display(value)
