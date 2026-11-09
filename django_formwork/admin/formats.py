"""The file types a list exports to and imports from: CSV, Excel and JSON."""

from __future__ import annotations

import csv
import datetime as dt
import decimal
import io
import json
import uuid
import zipfile
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django_formwork.admin.exports import Column

__all__ = ["FORMATS", "MISSING", "CsvFormat", "FileError", "FileFormat", "JsonFormat", "Table", "XlsxFormat"]


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


#: A cell a JSON record leaves out, which differs from one it sets to null.
MISSING: Any = _Missing()


class FileError(ValueError):
    """A file that can't be read as a table; the message says why, for the user."""


@dataclass(slots=True)
class Table:
    """The rows of an imported file under its header row."""

    headers: list[str]
    #: Each row's number in the file, as a spreadsheet counts it, and its cells.
    rows: list[tuple[int, list[Any]]] = field(default_factory=list)
    #: JSON fields hold data, not JSON text.
    structured: bool = False
    #: Numbers can use a comma for the decimal point, as a semicolon-separated CSV does.
    decimal_comma: bool = False


def _text(value: Any, *, structured: bool = False) -> Any:
    """A value for a cell of a flat file: numbers, dates and booleans stay, the rest becomes text."""
    if structured:
        return "" if value is None else json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder)
    if value is None or isinstance(value, bool | int | float | decimal.Decimal | dt.date | dt.time):
        return value
    if isinstance(value, list | tuple | set):
        return ",".join(str(item) for item in value)
    if isinstance(value, models.Model | uuid.UUID):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or ""
    return str(value)


def _blank(cells: Iterable[Any]) -> bool:
    return all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in cells)


class FileFormat:
    """A file type the list exports to and imports from."""

    name: ClassVar[str]
    label: ClassVar[str]
    extension: ClassVar[str]
    content_type: ClassVar[str]

    @classmethod
    def is_available(cls) -> bool:
        return True

    def write(self, columns: list[Column], rows: Iterable[list[Any]], stream: BinaryIO) -> None:
        raise NotImplementedError

    def read(self, stream: BinaryIO) -> Table:
        """The file's header row and rows; raises ``FileError`` for a file it can't read."""
        raise NotImplementedError


class CsvFormat(FileFormat):
    name = "csv"
    label = "CSV"
    extension = "csv"
    content_type = "text/csv"

    def write(self, columns: list[Column], rows: Iterable[list[Any]], stream: BinaryIO) -> None:
        # The byte order mark tells Excel the file is UTF-8.
        text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
        writer = csv.writer(text)
        writer.writerow([column.name for column in columns])
        for row in rows:
            writer.writerow([self.cell(value, column.structured) for column, value in zip(columns, row, strict=True)])
        text.flush()
        text.detach()

    @staticmethod
    def cell(value: Any, structured: bool) -> str:
        value = _text(value, structured=structured)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, dt.date | dt.time):
            return value.isoformat()
        return str(value)

    def read(self, stream: BinaryIO) -> Table:
        data = stream.read()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            # What Excel on Windows saves as "CSV" without the UTF-8 option.
            try:
                text = data.decode("cp1252")
            except UnicodeDecodeError:
                raise FileError(_("The file isn’t UTF-8 text.")) from None
        # Excel writes semicolons where the comma is the decimal point, as in German.
        first_line = text.split("\n", 1)[0]
        delimiter = max(",;\t", key=first_line.count)
        try:
            records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as exc:
            raise FileError(_("The file isn’t valid CSV: %(error)s") % {"error": exc}) from None
        if not records or _blank(records[0]):
            raise FileError(_("The file is empty."))
        headers = [header.strip() for header in records[0]]
        rows = [
            (number, (cells + [""] * len(headers))[: len(headers)])
            for number, cells in enumerate(records[1:], start=2)
            if not _blank(cells)
        ]
        return Table(headers, rows, decimal_comma=delimiter == ";")


class JsonFormat(FileFormat):
    name = "json"
    label = "JSON"
    extension = "json"
    content_type = "application/json"

    def write(self, columns: list[Column], rows: Iterable[list[Any]], stream: BinaryIO) -> None:
        names = [column.name for column in columns]
        stream.write(b"[")
        for index, row in enumerate(rows):
            stream.write(b",\n" if index else b"\n")
            record = json.dumps(dict(zip(names, row, strict=True)), ensure_ascii=False, cls=_Encoder)
            stream.write(record.encode())
        stream.write(b"\n]\n")

    def read(self, stream: BinaryIO) -> Table:
        try:
            records = json.loads(stream.read())
        except ValueError as exc:
            raise FileError(_("The file isn’t valid JSON: %(error)s") % {"error": exc}) from None
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise FileError(_("The file isn’t a JSON list of objects."))
        headers = list(dict.fromkeys(str(key) for record in records for key in record))
        rows = [
            (number, [record.get(header, MISSING) for header in headers])
            for number, record in enumerate(records, start=1)
        ]
        return Table(headers, rows, structured=True)


class _Encoder(DjangoJSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, models.Model):
            return str(o)
        if isinstance(o, FieldFile):
            return o.name or None
        return super().default(o)


class XlsxFormat(FileFormat):
    name = "xlsx"
    label = "Excel"
    extension = "xlsx"
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @classmethod
    def is_available(cls) -> bool:
        return find_spec("openpyxl") is not None

    def write(self, columns: list[Column], rows: Iterable[list[Any]], stream: BinaryIO) -> None:
        from openpyxl import Workbook

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet()
        sheet.append([column.name for column in columns])
        for row in rows:
            sheet.append([self.cell(value, column.structured) for column, value in zip(columns, row, strict=True)])
        workbook.save(stream)

    @staticmethod
    def cell(value: Any, structured: bool) -> Any:
        value = _text(value, structured=structured)
        # Excel has no time zones: a datetime shows in the site's zone.
        if isinstance(value, dt.datetime) and timezone.is_aware(value):
            return timezone.localtime(value).replace(tzinfo=None)
        if isinstance(value, dt.time) and value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

    def read(self, stream: BinaryIO) -> Table:
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException

        try:
            workbook = load_workbook(stream, read_only=True, data_only=True)
        except InvalidFileException, zipfile.BadZipFile, KeyError, ValueError, OSError:
            raise FileError(_("The file isn’t an Excel workbook.")) from None
        try:
            sheet = workbook.worksheets[0]
            records = sheet.iter_rows(values_only=True)
            first = next(records, None)
            if first is None or _blank(first):
                raise FileError(_("The first sheet is empty."))
            headers = ["" if header is None else str(header).strip() for header in first]
            # A sheet's used range can run past the last header.
            while headers and not headers[-1]:
                headers.pop()
            rows = [
                (number, (list(cells) + [None] * len(headers))[: len(headers)])
                for number, cells in enumerate(records, start=2)
                if not _blank(cells[: len(headers)])
            ]
        finally:
            workbook.close()
        return Table(headers, rows)


#: The formats by name; ``ModelAdmin.export_formats`` and ``import_formats`` pick from these.
FORMATS: dict[str, FileFormat] = {format_.name: format_ for format_ in (CsvFormat(), XlsxFormat(), JsonFormat())}
