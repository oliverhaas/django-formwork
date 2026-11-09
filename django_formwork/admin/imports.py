"""Changelist imports: a file's rows checked by the admin's form and saved through its hooks."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.contrib.admin.utils import model_ngettext, quote
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db import models, router, transaction
from django.db.models import Q
from django.db.models.expressions import DatabaseDefault
from django.urls import reverse
from django.utils import timezone
from django.utils.hashable import make_hashable
from django.utils.text import capfirst, get_text_list
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from django_formwork.admin.cells import Cell, cell_for_field, cell_for_value
from django_formwork.admin.formats import MISSING, FileError, FileFormat, Table
from django_formwork.forms import FormworkForm
from django_formwork.formsets import FormworkBaseModelFormSet, formwork_modelformset_factory
from django_formwork.widgets import ClearableFileInput

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.http import HttpRequest

__all__ = [
    "Column",
    "ImportFileForm",
    "ImportResult",
    "PreviewRow",
    "Row",
    "Status",
    "check_import",
    "column_guide",
    "preview_rows",
    "save_import",
]

#: The most rows the preview shows; rows with errors come first, then changed and new rows.
PREVIEW_LIMIT = 1000
#: Values per ``__in`` query when the import looks up related and existing records.
CHUNK_SIZE = 1000
#: Rows per query when existing records are found by a key of several fields.
COMPOUND_CHUNK_SIZE = 200
#: How close a cell's time must be to the record's to count as unchanged.
TIME_PRECISION = dt.timedelta(milliseconds=1)
#: The most choices the column guide lists for a field.
GUIDE_CHOICES = 6

# Related fields a lookup column example names, in this order of preference.
_LOOKUP_EXAMPLES = ("slug", "name", "title", "code", "email", "username")


class Status(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    ERROR = "error"


class ImportFileForm(FormworkForm):
    """The file to import; its extension names the format."""

    file = forms.FileField(label=gettext_lazy("File"), widget=ClearableFileInput())

    def __init__(self, *args: Any, formats: Sequence[FileFormat], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.formats = {format_.extension: format_ for format_ in formats}
        self.file_format: FileFormat | None = None
        file_field = self.fields["file"]
        file_field.widget.attrs["accept"] = ",".join(f".{extension}" for extension in self.formats)
        file_field.help_text = _("A %(formats)s file with a header row.") % {"formats": self._labels()}

    def _labels(self) -> str:
        return get_text_list([format_.label for format_ in self.formats.values()], _("or"))

    def clean_file(self) -> Any:
        upload = self.cleaned_data["file"]
        extension = upload.name.rpartition(".")[2].lower() if "." in upload.name else ""
        self.file_format = self.formats.get(extension)
        if self.file_format is None:
            raise ValidationError(_("Pick a %(formats)s file.") % {"formats": self._labels()})
        return upload


# Columns


@dataclass(slots=True)
class Column:
    """A file column the import reads into a field of the admin's form."""

    index: int
    header: str
    name: str
    label: str
    #: The model field behind the form field, if there is one.
    model_field: models.Field[Any, Any] | None = None
    #: For ``category__name``: the field of the related model that the cells name.
    lookup: str | None = None


@dataclass(slots=True)
class KeyColumn:
    """A file column that finds the record a row updates."""

    index: int
    header: str
    field: models.Field[Any, Any]


@dataclass(slots=True)
class Mapping:
    columns: list[Column]
    keys: list[KeyColumn]
    #: The ``import_id_fields`` the file has no column for; then every row is new.
    missing_keys: list[str]
    #: Headers that name no field.
    ignored: list[str]

    @property
    def key_label(self) -> str:
        return " / ".join(capfirst(str(key.field.verbose_name)) for key in self.keys)

    @property
    def key_shown(self) -> bool:
        """True when a key column is not also a field column, so the preview shows it apart."""
        names = {column.name for column in self.columns}
        return bool(self.keys) and not self.missing_keys and any(key.field.name not in names for key in self.keys)


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def _model_field(opts: Any, name: str) -> models.Field[Any, Any] | None:
    try:
        return opts.get_field(name)
    except FieldDoesNotExist:
        return None


def map_columns(headers: Sequence[str], form: forms.BaseForm, opts: Any, id_fields: Sequence[str]) -> Mapping:
    """Match each header to a form field by its name or label, ignoring case."""
    names: dict[str, str] = {}
    for name, form_field in form.fields.items():
        if isinstance(form_field, forms.FileField):
            continue
        model_field = _model_field(opts, name)
        for alias in (form_field.label, getattr(model_field, "verbose_name", None)):
            if alias:
                names.setdefault(_fold(str(alias)), name)
    # A field's own name wins over another field's label.
    names.update(
        {_fold(name): name for name, form_field in form.fields.items() if not isinstance(form_field, forms.FileField)}
    )

    key_fields = [opts.get_field(name) for name in id_fields]
    key_aliases: dict[str, int] = {}
    for position, key_field in enumerate(key_fields):
        for alias in (key_field.name, key_field.attname, key_field.verbose_name):
            key_aliases.setdefault(_fold(str(alias)), position)

    columns: list[Column] = []
    keys: dict[int, KeyColumn] = {}
    ignored: list[str] = []
    seen: dict[str, str] = {}
    for index, header in enumerate(headers):
        folded = _fold(header)
        if not folded:
            continue
        matched = False
        key_position = key_aliases.get(folded)
        if key_position is not None and key_position not in keys:
            keys[key_position] = KeyColumn(index, header, key_fields[key_position])
            matched = True
        field_name, lookup = _field_for(folded, names, form)
        if field_name is not None:
            if field_name in seen:
                msg = _("The columns “%(first)s” and “%(second)s” are both for %(field)s. Remove one of them.") % {
                    "first": seen[field_name],
                    "second": header,
                    "field": form.fields[field_name].label or field_name,
                }
                raise FileError(msg)
            seen[field_name] = header
            label = str(form.fields[field_name].label or capfirst(field_name))
            columns.append(Column(index, header, field_name, label, _model_field(opts, field_name), lookup))
            matched = True
        if not matched:
            ignored.append(header)
    if not columns and not keys:
        quoted = [f"“{header}”" for header in headers if header.strip()]
        msg = _("None of the columns is a field of %(name)s: %(headers)s.") % {
            "name": opts.verbose_name_plural,
            "headers": get_text_list(quoted, _("and")),
        }
        raise FileError(msg)
    missing = [key_field.name for position, key_field in enumerate(key_fields) if position not in keys]
    return Mapping(columns, [keys[position] for position in sorted(keys)], missing, ignored)


def _field_for(folded: str, names: dict[str, str], form: forms.BaseForm) -> tuple[str | None, str | None]:
    """The form field a header names, and the related field of a ``category__name`` header."""
    name = names.get(folded)
    if name is not None:
        return name, None
    head, separator, rest = folded.partition("__")
    name = names.get(head) if separator else None
    form_field = form.fields.get(name) if name is not None else None
    if isinstance(form_field, forms.ModelChoiceField):
        for related in _queryset(form_field).model._meta.concrete_fields:
            if rest in {related.name.casefold(), related.attname.casefold()}:
                return name, related.name
    return None, None


# Cells


def _text(value: Any) -> str:
    """A cell as the text a form would post."""
    if value is None or value is MISSING:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    if isinstance(value, dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _form_value(value: Any, form_field: forms.Field, table: Table, choices: dict[str, str] | None) -> Any:
    """A cell as the data a form field reads, for its ``to_python()``."""
    if isinstance(form_field, forms.JSONField) and table.structured:
        # The form parses JSON text, as from its textarea; ``{}`` stays an empty object.
        return "" if value is None else json.dumps(value, ensure_ascii=False)
    is_date = isinstance(form_field, forms.DateField)
    if is_date and isinstance(value, dt.datetime) and value.time() == dt.time():
        # Excel keeps a date as a datetime at midnight.
        value = value.date()
    text = _text(value)
    if table.decimal_comma and isinstance(form_field, forms.DecimalField | forms.FloatField) and "," in text:
        text = text.replace(".", "").replace(",", ".")
    if choices is not None and text:
        text = choices.get(text.casefold(), text)
    return text


def _choice_aliases(form_field: forms.Field) -> dict[str, str] | None:
    """Labels and yes/no words a cell can hold, by their folded text, with the value each stands for."""
    if isinstance(form_field, forms.BooleanField):
        return {_("yes").casefold(): "true", _("no").casefold(): "false", "yes": "true", "no": "false"}
    if isinstance(form_field, forms.ChoiceField) and not isinstance(form_field, forms.ModelChoiceField):
        aliases: dict[str, str] = {}
        for value, label in _flat_choices(form_field.choices):
            aliases.setdefault(str(label).casefold(), str(value))
        for value, _label in _flat_choices(form_field.choices):
            aliases[str(value).casefold()] = str(value)
        return aliases
    return None


def _flat_choices(choices: Any) -> list[tuple[Any, Any]]:
    flat: list[tuple[Any, Any]] = []
    for value, label in choices:
        if isinstance(label, list | tuple):
            flat.extend(label)
        else:
            flat.append((value, label))
    return flat


def _tokens(value: Any, *, many: bool) -> list[str]:
    if value is None or value is MISSING:
        return []
    if many:
        items = value if isinstance(value, list | tuple) else str(value).split(",")
        return [token for token in (_text(item) for item in items) if token]
    text = _text(value)
    return [text] if text else []


# Rows


@dataclass(slots=True, eq=False)
class Row:
    """One row of the file and what the import makes of it."""

    number: int
    cells: list[Any]
    #: The form's data, by field name.
    data: dict[str, Any] = field(default_factory=dict)
    #: Each column's cell as the file writes it, for the preview of an invalid value.
    raw: dict[str, str] = field(default_factory=dict)
    #: Errors found before the form runs, by field name; ``""`` holds the row's own.
    errors: dict[str, list[str]] = field(default_factory=dict)
    key: tuple[Any, ...] | None = None
    key_text: str = ""
    duplicate: bool = False
    #: The user cannot save the row; the preview shows only that, not the form's errors.
    denied: bool = False
    #: The record the row updates; None for a new record.
    obj: models.Model | None = None
    form: Any = None
    status: Status = Status.NEW
    #: The fields the row changes, and their values before the import.
    changed: list[str] = field(default_factory=list)
    current: dict[str, Any] = field(default_factory=dict)

    def add_error(self, name: str, message: str) -> None:
        self.errors.setdefault(name, []).append(message)


@dataclass(slots=True)
class _Relation:
    """A column of related records, looked up for the whole file in one query per thousand values."""

    column: Column
    form_field: forms.ModelChoiceField[Any]
    many: bool
    #: The field of the related model that the cells name.
    target: models.Field[Any, Any]
    #: The records found, by the value the form field posts for them.
    found: dict[str, models.Model] = field(default_factory=dict)

    def patch(self, form_field: forms.ModelChoiceField[Any]) -> None:
        """Make a row's form field use the records found instead of a query per row."""
        if self.many:
            form_field.clean = partial(_clean_many, form_field, form_field.clean, self.found)  # type: ignore[method-assign]
        else:
            form_field.to_python = partial(_to_python_one, form_field.to_python, self.found)  # type: ignore[method-assign]


def _queryset(form_field: forms.ModelChoiceField[Any]) -> models.QuerySet[Any]:
    """The field's choices: a model choice field built by a model form always has a queryset."""
    return cast("models.QuerySet[Any]", form_field.queryset)


def _to_python_one(original: Callable[[Any], Any], found: dict[str, models.Model], value: Any) -> Any:
    if isinstance(value, str) and value in found:
        return found[value]
    return original(value)


def _clean_many(
    form_field: forms.ModelChoiceField[Any],
    original: Callable[[Any], Any],
    found: dict[str, models.Model],
    value: Any,
) -> Any:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item in found for item in value):
        return original(value)
    form_field.run_validators(value)
    key = form_field.to_field_name or "pk"
    return _queryset(form_field).filter(**{f"{key}__in": value})


def _resolve(relation: _Relation, rows: list[Row]) -> None:
    """Look up the column's related records and put each row's in its form data, or an error."""
    column, form_field = relation.column, relation.form_field
    related_opts = _queryset(form_field).model._meta
    tokens: dict[Row, list[tuple[str, Any]]] = {}
    invalid: dict[Row, list[str]] = {}
    wanted: set[Any] = set()
    for row in rows:
        cell = row.cells[column.index]
        if cell is MISSING:
            continue
        converted = []
        for token in _tokens(cell, many=relation.many):
            try:
                value = relation.target.to_python(token)
            except ValidationError:
                invalid.setdefault(row, []).append(token)
            else:
                converted.append((token, value))
                wanted.add(make_hashable(value))
        tokens[row] = converted

    matches: dict[Any, dict[Any, models.Model]] = {}
    values = list(wanted)
    for start in range(0, len(values), CHUNK_SIZE):
        chunk = values[start : start + CHUNK_SIZE]
        for obj in _queryset(form_field).filter(**{f"{relation.target.name}__in": chunk}):
            matches.setdefault(make_hashable(getattr(obj, relation.target.attname)), {})[obj.pk] = obj

    for row, converted in tokens.items():
        keys, missing = [], list(invalid.get(row, ()))
        for token, value in converted:
            found = matches.get(make_hashable(value), {})
            if len(found) == 1:
                obj = next(iter(found.values()))
                key = str(form_field.prepare_value(obj))
                relation.found[key] = obj
                keys.append(key)
            elif found:
                msg = ngettext(
                    "%(count)s %(name)s matches “%(value)s”.",
                    "%(count)s %(name)s match “%(value)s”.",
                    len(found),
                ) % {"count": len(found), "name": model_ngettext(related_opts, len(found)), "value": token}
                row.add_error(column.name, msg)
            else:
                missing.append(token)
        if missing:
            quoted = [f"“{token}”" for token in missing]
            msg = _("No %(name)s matches %(values)s.") % {
                "name": related_opts.verbose_name,
                "values": get_text_list(quoted, _("or")),
            }
            row.add_error(column.name, msg)
        if column.name not in row.errors:
            row.data[column.name] = keys if relation.many else (keys[0] if keys else "")


def _match_records(model_admin: Any, request: HttpRequest, mapping: Mapping, rows: list[Row]) -> None:
    """Find the record each row updates by its key columns, in one query per thousand keys."""
    if not mapping.keys or mapping.missing_keys:
        return
    fields = [key.field for key in mapping.keys]
    fields_label = get_text_list([str(key_field.verbose_name) for key_field in fields], _("and"))
    first: dict[tuple[Any, ...], int] = {}
    for row in rows:
        texts = [_text(row.cells[key.index]) for key in mapping.keys]
        row.key_text = " / ".join(texts)
        if not all(texts):
            continue
        values = []
        for key, text in zip(mapping.keys, texts, strict=True):
            try:
                values.append(key.field.to_python(text))
            except ValidationError as error:
                row.add_error("", f"{capfirst(str(key.field.verbose_name))}: {' '.join(error.messages)}")
                break
        else:
            row.key = tuple(make_hashable(value) for value in values)
            if row.key in first:
                row.duplicate = True
                row.add_error(
                    "", _("Row %(row)s has the same %(fields)s.") % {"row": first[row.key], "fields": fields_label}
                )
            else:
                first[row.key] = row.number

    queryset = model_admin.get_queryset(request)
    related = [column.name for column in mapping.columns if isinstance(column.model_field, models.ForeignKey)]
    many = [column.name for column in mapping.columns if isinstance(column.model_field, models.ManyToManyField)]
    if related:
        queryset = queryset.select_related(*related)
    if many:
        queryset = queryset.prefetch_related(*many)
    attnames = [key_field.attname for key_field in fields]
    found: dict[tuple[Any, ...], models.Model] = {}
    wanted = list(first)
    size = CHUNK_SIZE if len(fields) == 1 else COMPOUND_CHUNK_SIZE
    for start in range(0, len(wanted), size):
        chunk = wanted[start : start + size]
        if len(fields) == 1:
            condition = Q(**{f"{attnames[0]}__in": [key[0] for key in chunk]})
        else:
            condition = Q()
            for key_values in chunk:
                condition |= Q(**dict(zip(attnames, key_values, strict=True)))
        for obj in queryset.filter(condition):
            found[tuple(make_hashable(getattr(obj, attname)) for attname in attnames)] = obj
    for row in rows:
        obj = found.get(row.key) if row.key is not None else None
        if obj is not None:
            # A second row for the same record checks against its own copy.
            row.obj = copy.copy(obj) if row.duplicate else obj


def _keep_record_times(rows: list[Row], mapping: Mapping, form: Any) -> None:
    """Excel and JSON keep a time to the millisecond: a cell that matches the record's to that keeps the record's own."""
    fields = {
        column.name: form.fields[column.name]
        for column in mapping.columns
        if isinstance(form.fields[column.name], forms.DateTimeField | forms.TimeField)
    }
    for row in rows:
        if row.obj is None:
            continue
        for name, form_field in fields.items():
            current = getattr(row.obj, name, None)
            if not isinstance(current, dt.datetime | dt.time) or not row.data.get(name):
                continue
            try:
                value = form_field.to_python(row.data[name])
            except ValidationError:
                continue
            if type(value) is type(current) and abs(_naive(value) - _naive(current)) < TIME_PRECISION:
                row.data[name] = form_field.prepare_value(current)


def _naive(value: dt.datetime | dt.time) -> dt.datetime:
    if isinstance(value, dt.time):
        return dt.datetime.combine(dt.date.min, value.replace(tzinfo=None))
    return timezone.make_naive(value) if timezone.is_aware(value) else value


# Forms


class _CellWidget(forms.Widget):
    """Reads a field's value from a row as is, where the admin's widget reads a post."""

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        return data.get(name)

    def value_omitted_from_data(self, data: Any, files: Any, name: str) -> bool:
        return name not in data


class _ImportFormSet(FormworkBaseModelFormSet):
    """One form per row: new rows add, the others update their record."""

    def __init__(self, *args: Any, rows: list[Row], relations: dict[str, _Relation], **kwargs: Any) -> None:
        self.import_rows = rows
        self.relations = relations
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index: int | None) -> dict[str, Any]:
        if index is None:
            return super().get_form_kwargs(index)
        row = self.import_rows[index]
        # A record's row that changes nothing skips validation, as an unchanged extra form does.
        return {"data": row.data, "instance": row.obj, "prefix": None, "empty_permitted": row.obj is not None}

    def _construct_form(self, i: int, **kwargs: Any) -> Any:
        form = super()._construct_form(i, **kwargs)
        row = self.import_rows[i]
        adding = row.obj is None
        for name in list(form.fields):
            form_field = form.fields[name]
            # Files don't fit in a cell; a column the file lacks keeps the record's value.
            if isinstance(form_field, forms.FileField) or (not adding and name not in row.data):
                del form.fields[name]
                continue
            form_field.widget = _CellWidget()
            form_field.show_hidden_initial = False
            if adding and name not in row.data:
                # As the add form would post it: ``{}`` for a JSON default stays an empty object.
                row.data[name] = form_field.prepare_value(form.get_initial_for_field(form_field, name))
            relation = self.relations.get(name)
            if relation is not None:
                relation.patch(form_field)
        known = [
            name
            for name, relation in self.relations.items()
            if name in form.fields
            and isinstance(relation.column.model_field, models.ForeignKey)
            and not relation.column.model_field.remote_field.parent_link
        ]
        if known:
            instance = form.instance
            instance.clean_fields = partial(_clean_known_fields, instance, instance.clean_fields, known)
        return form

    def add_fields(self, form: Any, index: int | None) -> None:
        # Rows find their record by key, not by a pk field of the form.
        forms.BaseFormSet.add_fields(self, form, index)

    def validate_unique(self) -> None:
        """Mark a row that repeats an earlier row's unique values, naming that row."""
        valid = [form for form in self.forms if form.is_valid() and form.cleaned_data]
        rows = {id(row.form): row for row in self.import_rows}
        unique_checks: set[tuple[Any, tuple[str, ...]]] = set()
        date_checks: set[tuple[Any, str, str, str]] = set()
        for form in valid:
            exclude = form._get_validation_exclusions()
            checks, dates = form.instance._get_unique_checks(exclude=exclude, include_meta_constraints=True)
            unique_checks.update(checks)
            date_checks.update(dates)
        opts = cast("type[models.Model]", self.model)._meta
        groups: list[tuple[tuple[str, ...], Callable[[Any], tuple[Any, ...] | None]]] = [
            (fields, partial(_unique_values, fields)) for _model, fields in unique_checks
        ]
        groups += [
            ((name, date_field), partial(_date_values, name, lookup, date_field))
            for _model, lookup, name, date_field in date_checks
        ]
        for fields, values in sorted(groups, key=lambda group: group[0]):
            seen: dict[tuple[Any, ...], int] = {}
            for form in valid:
                if not form.is_valid():
                    continue
                key = values(form.cleaned_data)
                if key is None:
                    continue
                number = rows[id(form)].number
                if key not in seen:
                    seen[key] = number
                    continue
                labels = [str(cast("models.Field[Any, Any]", opts.get_field(name)).verbose_name) for name in fields]
                msg = _("Row %(row)s has the same %(fields)s.") % {
                    "row": seen[key],
                    "fields": get_text_list(labels, _("and")),
                }
                form.add_error(fields[0] if len(fields) == 1 else None, msg)


def _clean_known_fields(
    instance: models.Model,
    original: Callable[..., None],
    names: list[str],
    exclude: set[str] | None = None,
) -> None:
    """``Model.clean_fields`` without each foreign key's ``exists()`` query: the form field fetched the record already."""
    exclude = set(exclude or ())
    known = [cast("models.Field[Any, Any]", instance._meta.get_field(name)) for name in names if name not in exclude]
    errors: dict[str, Any] = {}
    try:
        original(exclude=exclude | {model_field.name for model_field in known})
    except ValidationError as error:
        errors = error.update_error_dict(errors)
    for model_field in known:
        raw = getattr(instance, model_field.attname)
        if (model_field.blank and raw in model_field.empty_values) or isinstance(raw, DatabaseDefault):
            continue
        try:
            value = model_field.to_python(raw)
            models.Field.validate(model_field, value, instance)
            model_field.run_validators(value)
        except ValidationError as error:
            errors[model_field.name] = error.error_list
        else:
            setattr(instance, model_field.attname, value)
    if errors:
        raise ValidationError(errors)


def _unique_values(fields: tuple[str, ...], cleaned: dict[str, Any]) -> tuple[Any, ...] | None:
    if not all(name in cleaned for name in fields):
        return None
    values = tuple(
        make_hashable(value.pk if isinstance(value, models.Model) else value)
        for value in (cleaned[name] for name in fields)
    )
    return None if None in values else values


def _date_values(name: str, lookup: str, date_field: str, cleaned: dict[str, Any]) -> tuple[Any, ...] | None:
    value, date = cleaned.get(name), cleaned.get(date_field)
    if value is None or date is None:
        return None
    parts = (date.year, date.month, date.day) if lookup == "date" else (getattr(date, lookup),)
    return (make_hashable(value), *parts)


# Checking a file


@dataclass(slots=True)
class ImportResult:
    """What a file would do: each row's status and form, and a digest the import compares."""

    mapping: Mapping
    rows: list[Row]
    counts: dict[str, int]
    digest: str
    relations: dict[str, _Relation]

    @property
    def errors(self) -> int:
        return self.counts[Status.ERROR]

    @property
    def pending(self) -> int:
        """The rows an import saves: the new and the changed ones."""
        return self.counts[Status.NEW] + self.counts[Status.CHANGED]

    @property
    def can_import(self) -> bool:
        return not self.errors and self.pending > 0


def check_import(model_admin: Any, request: HttpRequest, table: Table, content: bytes) -> ImportResult:
    """Run every row of ``table`` through the admin's form; raises ``FileError`` for columns it can't use."""
    opts = model_admin.opts
    form_class = model_admin.get_import_form(request)
    probe = form_class()
    mapping = map_columns(table.headers, probe, opts, model_admin.get_import_id_fields(request))
    if not table.rows:
        raise FileError(_("The file has no rows under its header row."))

    rows = [Row(number, cells) for number, cells in table.rows]
    relations: dict[str, _Relation] = {}
    aliases: dict[str, dict[str, str] | None] = {}
    for column in mapping.columns:
        form_field = probe.fields[column.name]
        if isinstance(form_field, forms.ModelChoiceField):
            related_opts = _queryset(form_field).model._meta
            target_name = column.lookup or form_field.to_field_name
            target = related_opts.get_field(target_name) if target_name else related_opts.pk
            many = isinstance(form_field, forms.ModelMultipleChoiceField)
            relations[column.name] = _Relation(column, form_field, many, target)
        else:
            aliases[column.name] = _choice_aliases(form_field)
    for row in rows:
        for column in mapping.columns:
            cell = row.cells[column.index]
            if cell is MISSING:
                continue
            row.raw[column.name] = _text(cell)
            if column.name not in relations:
                form_field = probe.fields[column.name]
                row.data[column.name] = _form_value(cell, form_field, table, aliases[column.name])
    for relation in relations.values():
        _resolve(relation, rows)
    _match_records(model_admin, request, mapping, rows)
    _keep_record_times(rows, mapping, probe)

    formset_class = formwork_modelformset_factory(
        model_admin.model,
        form=form_class,
        formset=_ImportFormSet,
        extra=0,
        max_num=len(rows),
        absolute_max=len(rows),
    )
    formset = formset_class(
        {"form-TOTAL_FORMS": str(len(rows)), "form-INITIAL_FORMS": "0"},
        rows=rows,
        relations=relations,
        queryset=model_admin.model._default_manager.none(),
    )
    can_add = model_admin.has_add_permission(request)
    for row, form in zip(rows, formset.forms, strict=True):
        row.form = form
        if row.obj is None:
            if not can_add:
                row.denied = True
                row.add_error("", _("You can’t add %(name)s.") % {"name": opts.verbose_name_plural})
            continue
        # Before validation, which writes the row's values into the record.
        row.current = {column.name: _current(row.obj, form, column) for column in mapping.columns}
        row.changed = list(form.changed_data)
        if not row.changed:
            continue
        if not model_admin.has_change_permission(request, row.obj):
            row.denied = True
            row.add_error("", _("You can’t change this %(name)s.") % {"name": opts.verbose_name})
            continue
        for name in set(model_admin.get_readonly_fields(request, row.obj)).intersection(row.changed):
            row.add_error(name, _("This field can’t be changed."))
    formset.is_valid()

    counts = dict.fromkeys(Status, 0)
    digest = hashlib.sha256(content)
    for row in rows:
        if row.errors or row.form.errors:
            row.status = Status.ERROR
        elif row.obj is None:
            row.status = Status.NEW
        else:
            row.status = Status.CHANGED if row.changed else Status.UNCHANGED
        counts[row.status] += 1
        before = ";".join(f"{name}={_fingerprint(row.current.get(name))}" for name in sorted(row.changed))
        digest.update(f"\n{row.number}:{row.status}:{row.obj.pk if row.obj else ''}:{before}".encode())
    return ImportResult(
        mapping, rows, {str(status): count for status, count in counts.items()}, digest.hexdigest(), relations
    )


def _current(obj: models.Model, form: Any, column: Column) -> Any:
    if isinstance(column.model_field, models.ForeignKey):
        try:
            return getattr(obj, column.model_field.name)
        except ObjectDoesNotExist:
            return None
    return form.initial.get(column.name)


def _fingerprint(value: Any) -> str:
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, list | tuple):
        return ",".join(_fingerprint(item) for item in value)
    return repr(value)


# Saving


def save_import(model_admin: Any, request: HttpRequest, result: ImportResult) -> tuple[int, int]:
    """Save the new and changed rows in one transaction, through the admin's save hooks; the counts saved."""
    added = changed = 0
    with transaction.atomic(using=router.db_for_write(model_admin.model)):
        for row in result.rows:
            if row.status not in {Status.NEW, Status.CHANGED}:
                continue
            change = row.status is Status.CHANGED
            form = row.form
            obj = model_admin.save_form(request, form, change=change)
            model_admin.save_model(request, obj, form, change=change)
            model_admin.save_related(request, form, formsets=[], change=change)
            message = model_admin.construct_change_message(request, form, [], add=not change)
            if change:
                model_admin.log_change(request, obj, message)
                changed += 1
            else:
                model_admin.log_addition(request, obj, message)
                added += 1
    return added, changed


# The preview


@dataclass(slots=True)
class PreviewCell:
    cell: Cell
    #: The record's value before the import, for a changed cell.
    old: Cell | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PreviewRow:
    number: int
    status: Status
    key: str
    url: str
    cells: list[PreviewCell]
    #: Errors of the whole row, and of fields the file has no column for.
    messages: list[str]


def preview_rows(model_admin: Any, result: ImportResult) -> list[PreviewRow]:
    """The rows the preview shows, at most ``PREVIEW_LIMIT``, in file order."""
    empty = model_admin.get_empty_value_display()
    priority = {Status.ERROR: 0, Status.CHANGED: 1, Status.NEW: 2, Status.UNCHANGED: 3}
    shown = sorted(result.rows, key=lambda row: (priority[row.status], row.number))[:PREVIEW_LIMIT]
    columns = {column.name for column in result.mapping.columns}
    previews = []
    for row in sorted(shown, key=lambda row: row.number):
        form = row.form
        form_errors = {} if row.denied else form.errors
        cells = []
        for column in result.mapping.columns:
            errors = row.errors.get(column.name) or list(form_errors.get(column.name, ()))
            colors = model_admin.list_badges.get(column.name)
            cells.append(_preview_cell(row, column, result.relations.get(column.name), errors, empty, colors))
        messages = list(row.errors.get("", ()))
        for name, errors in form_errors.items():
            if name in columns:
                continue
            if name == "__all__":
                messages += errors
                continue
            label = form.fields[name].label if name in form.fields else name
            messages += [f"{label}: {error}" for error in errors]
        messages += [
            f"{name}: {error}"
            for name, errors in row.errors.items()
            if name and name not in columns
            for error in errors
        ]
        url = ""
        if row.obj is not None and row.obj.pk is not None:
            url = reverse(
                model_admin.url_name("change"), args=(quote(row.obj.pk),), current_app=model_admin.admin_site.name
            )
        previews.append(PreviewRow(row.number, row.status, row.key_text, url, cells, messages))
    return previews


def _preview_cell(
    row: Row, column: Column, relation: _Relation | None, errors: list[str], empty: str, colors: dict[str, str] | None
) -> PreviewCell:
    name = column.name
    if errors:
        return PreviewCell(cell_for_value(row.raw.get(name) or None, empty), errors=errors)
    if row.obj is not None and name not in row.changed:
        return PreviewCell(_display(row.current.get(name), column, empty, colors))
    cleaned = getattr(row.form, "cleaned_data", {})
    if relation is not None and relation.many and name in cleaned:
        new = _display([relation.found[key] for key in row.data.get(name) or ()], column, empty, colors)
    elif name in cleaned:
        new = _display(cleaned[name], column, empty, colors)
    else:
        new = cell_for_value(row.raw.get(name) or None, empty)
    old = _display(row.current.get(name), column, empty, colors) if row.obj is not None else None
    return PreviewCell(new, old)


def _display(value: Any, column: Column, empty: str, colors: dict[str, str] | None) -> Cell:
    if isinstance(value, models.Model):
        return cell_for_value(str(value), empty)
    if isinstance(value, list | tuple | models.QuerySet):
        return cell_for_value(", ".join(str(item) for item in value) or None, empty)
    model_field = column.model_field
    if model_field is not None and not model_field.is_relation:
        return cell_for_field(value, model_field, empty, colors=colors)
    return cell_for_value(value, empty)


# The column guide


@dataclass(slots=True)
class GuideEntry:
    name: str
    label: str
    required: bool
    key: bool
    hint: str


def column_guide(model_admin: Any, request: HttpRequest) -> list[GuideEntry]:
    """The columns an import reads, for the import page: the key columns first."""
    opts = model_admin.opts
    form = model_admin.get_import_form(request)()
    id_fields = list(model_admin.get_import_id_fields(request))
    entries = []
    for name in id_fields:
        if name not in form.fields:
            key_field = opts.get_field(name)
            label = capfirst(str(key_field.verbose_name))
            entries.append(GuideEntry(name, label, required=False, key=True, hint=_("Finds the record to update")))
    for name, form_field in form.fields.items():
        if isinstance(form_field, forms.FileField):
            continue
        label = str(form_field.label or capfirst(name))
        entries.append(GuideEntry(name, label, form_field.required, name in id_fields, _hint(name, form_field)))
    return entries


def _hint(name: str, form_field: forms.Field) -> str:
    if isinstance(form_field, forms.ModelChoiceField):
        related = _queryset(form_field).model._meta
        field_names = {related_field.name for related_field in related.concrete_fields}
        example = next((field_name for field_name in _LOOKUP_EXAMPLES if field_name in field_names), None)
        if isinstance(form_field, forms.ModelMultipleChoiceField):
            if example:
                return _("IDs separated by commas, or a %(lookup)s column") % {"lookup": f"{name}__{example}"}
            return _("IDs separated by commas")
        if example:
            return _("An ID, or a %(lookup)s column") % {"lookup": f"{name}__{example}"}
        return _("An ID")
    if isinstance(form_field, forms.BooleanField):
        return _("true or false")
    if isinstance(form_field, forms.ChoiceField):
        values = [str(value) for value, _label in _flat_choices(form_field.choices) if value not in ("", None)]
        listed = ", ".join(values[:GUIDE_CHOICES]) + (", …" if len(values) > GUIDE_CHOICES else "")
        return _("One of %(values)s") % {"values": listed} if values else ""
    if isinstance(form_field, forms.DateTimeField):
        return _("Date and time, such as %(example)s") % {"example": "2026-03-31 14:30"}
    if isinstance(form_field, forms.DateField):
        return _("Date, such as %(example)s") % {"example": "2026-03-31"}
    if isinstance(form_field, forms.TimeField):
        return _("Time, such as %(example)s") % {"example": "14:30"}
    if isinstance(form_field, forms.JSONField):
        return _("JSON")
    if isinstance(form_field, forms.IntegerField | forms.DecimalField | forms.FloatField):
        return _("A number")
    return ""
