"""The changelist's info dialog: what the search looks in, the model's fields and its table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.core.exceptions import FieldDoesNotExist
from django.db import DatabaseError, connections, router, transaction
from django.db.models.constants import LOOKUP_SEP
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.models import Model
    from django.db.models.options import Options

__all__ = ["FieldInfo", "IndexInfo", "SearchField", "TableInfo", "describe_fields", "describe_search", "describe_table"]

#: The lookups of Django's ``search_fields`` prefixes.
PREFIXES = {"^": "istartswith", "=": "iexact", "@": "search"}

LOOKUP_LABELS = {
    "icontains": _("contains"),
    "istartswith": _("starts with"),
    "iexact": _("is"),
    "search": _("full text"),
}


@dataclass(frozen=True, slots=True)
class SearchField:
    """One entry of ``search_fields``: as written, the labels along its path and how a word matches."""

    entry: str
    path: tuple[str, ...]
    lookup: str


@dataclass(frozen=True, slots=True)
class FieldInfo:
    name: str
    label: str
    kind: str
    column: str
    related: str
    flags: tuple[str, ...]


INDEX_KINDS = {
    "primary_key": _("primary key"),
    "unique": _("unique"),
    "index": _("index"),
    "foreign_key": _("foreign key"),
    "check": _("check"),
}


@dataclass(frozen=True, slots=True)
class IndexInfo:
    """An index or constraint; ``target`` is the column a foreign key points to."""

    name: str
    kind: str
    columns: tuple[str, ...]
    target: str = ""

    @property
    def label(self) -> str:
        return str(INDEX_KINDS[self.kind])


@dataclass(frozen=True, slots=True)
class TableInfo:
    name: str
    database: str
    vendor: str
    data_size: int | None
    index_size: int | None
    indexes: list[IndexInfo]


def describe_search(model: type[Model], entries: Any) -> list[SearchField]:
    return [_search_field(model, entry) for entry in entries]


def _search_field(model: type[Model], entry: str) -> SearchField:
    """The same reading of an entry as ``ModelAdmin.get_search_results()``."""
    lookup = PREFIXES.get(entry[:1], "")
    opts = model._meta
    labels = []
    previous = None
    for part in entry.removeprefix(entry[:1] if lookup else "").split(LOOKUP_SEP):
        try:
            field = opts.get_field(opts.pk.name if part == "pk" else part)
        except FieldDoesNotExist:
            if previous is not None and previous.get_lookup(part):
                lookup = lookup or part
            break
        labels.append(_label(field))
        previous = field
        if path_infos := getattr(field, "path_infos", None):
            opts = path_infos[-1].to_opts
    lookup = lookup or "icontains"
    return SearchField(entry, tuple(labels), str(LOOKUP_LABELS.get(lookup, lookup)))


def _label(field: Any) -> str:
    if field.auto_created and not field.concrete and field.is_relation:
        related = field.related_model._meta
        return str(capfirst(related.verbose_name_plural if field.multiple else related.verbose_name))
    return str(capfirst(field.verbose_name))


def describe_fields(opts: Options[Any]) -> list[FieldInfo]:
    """The concrete and many-to-many fields, in the model's order."""
    return [_field_info(field) for field in (*opts.concrete_fields, *opts.many_to_many)]


def _field_info(field: Any) -> FieldInfo:
    kind = type(field).__name__
    if (digits := getattr(field, "max_digits", None)) is not None:
        kind = f"{kind}({digits}, {getattr(field, 'decimal_places', 0)})"
    elif field.max_length is not None:
        kind = f"{kind}({field.max_length})"
    if field.many_to_many:
        column = field.remote_field.through._meta.db_table
    else:
        column = field.column or ""
    flags = []
    if field.primary_key:
        flags.append(_("primary key"))
    elif field.unique:
        flags.append(_("unique"))
    elif field.db_index:
        flags.append(_("indexed"))
    if field.null:
        flags.append(_("null"))
    if field.choices:
        flags.append(_("choices"))
    return FieldInfo(
        name=field.name,
        label=str(capfirst(field.verbose_name)),
        kind=kind,
        column=column,
        related=field.related_model._meta.label if field.related_model else "",
        flags=tuple(map(str, flags)),
    )


def describe_table(model: type[Model]) -> TableInfo:
    """The model's table as the database has it: its indexes and constraints and, where the database says, its size."""
    alias = router.db_for_read(model)
    connection = connections[alias]
    name = model._meta.db_table
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, name)
    data_size, index_size = _sizes(connection, name)
    return TableInfo(
        name=name,
        database=alias,
        vendor=_vendor(connection),
        data_size=data_size,
        index_size=index_size,
        indexes=sorted((_index(key, spec) for key, spec in constraints.items()), key=_index_order),
    )


def _vendor(connection: BaseDatabaseWrapper) -> str:
    try:
        version = ".".join(map(str, connection.get_database_version()))
    except DatabaseError, NotImplementedError:
        return connection.display_name
    return f"{connection.display_name} {version}"


def _index(name: str, spec: Mapping[str, Any]) -> IndexInfo:
    columns = tuple(spec.get("columns") or ())
    if spec.get("foreign_key") and not spec.get("primary_key"):
        table, column = spec["foreign_key"]
        return IndexInfo(name, "foreign_key", columns, f"{table}.{column}")
    kind = next((key for key in ("primary_key", "unique", "check") if spec.get(key)), "index")
    return IndexInfo(name, kind, columns)


def _index_order(index: IndexInfo) -> tuple[int, str]:
    return list(INDEX_KINDS).index(index.kind), index.name


SIZE_QUERIES = {
    "postgresql": "SELECT pg_table_size(%s::regclass), pg_indexes_size(%s::regclass)",
    "mysql": (
        "SELECT data_length, index_length FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s"
    ),
    "sqlite": (
        "SELECT SUM(CASE WHEN name = %s THEN pgsize END), SUM(CASE WHEN name != %s THEN pgsize END) FROM dbstat "
        "WHERE name = %s OR name IN (SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = %s)"
    ),
}


def _sizes(connection: BaseDatabaseWrapper, table: str) -> tuple[int | None, int | None]:
    """The bytes of the table's rows and of its indexes; None where the database keeps no count."""
    sql = SIZE_QUERIES.get(connection.vendor)
    if sql is None:
        return None, None
    name = connection.ops.quote_name(table) if connection.vendor == "postgresql" else table
    params = [name] * sql.count("%s")
    try:
        # A savepoint, so a database without the statistics keeps the request's transaction usable.
        with transaction.atomic(using=connection.alias), connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
    except DatabaseError:
        return None, None
    data, indexes = row or (None, None)
    return _bytes(data), _bytes(indexes)


def _bytes(value: Any) -> int | None:
    return None if value is None else int(value)
