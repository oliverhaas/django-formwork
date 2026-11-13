"""The admin's history: who changed an object, when, and the values before and after.

``AdminSite.history`` holds the backend. ``ModelHistory`` keeps the entries in the admin's own
table. ``PghistoryHistory`` shows the events of django-pghistory for the models it tracks.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import decimal
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
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
    "FieldChange",
    "History",
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
        ).select_related("user")
        return [_entry(row) for row in rows[start:stop]]

    def recent(self, request: HttpRequest, limit: int) -> list[Entry]:
        from django_formwork.admin.models import HistoryEntry

        if not request.user.is_authenticated:
            return []
        rows = HistoryEntry.objects.filter(user_id=cast("Any", request.user.pk)).select_related("content_type", "user")
        return [_entry(row) for row in rows[:limit]]


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
            entries.append(_event_entry(event, type(obj), user, values))
        return entries


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


def _event_entry(event: Any, model: type[models.Model], user: str, values: dict[Any, dict[str, str]]) -> Entry:
    # The labels of pghistory's own trackers. A snapshot without a diff is the first one, so the insert.
    label = event.pgh_label
    diff = event.pgh_diff or {}
    if label == "delete":
        action, text = DELETE, _("Deleted.")
    elif label == "insert" or (label == "snapshot" and not diff):
        action, text = ADD, _("Added.")
    else:
        action, text = CHANGE, "" if label in {"update", "snapshot"} else capfirst(label.replace("_", " ")) + "."
    fields = []
    for column, (old, new) in diff.items():
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
