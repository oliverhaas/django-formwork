"""Changelist exports: the columns and the background job; ``formats`` writes the files."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.admin.utils import lookup_field
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models
from django.http import HttpRequest, QueryDict
from django.utils import timezone
from django.utils.text import slugify

from django_formwork.admin.formats import FORMATS, FileFormat

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from django_formwork.admin.models import ExportJob

__all__ = [
    "Column",
    "export_filename",
    "export_rows",
    "get_columns",
    "run_export_job",
]

#: Rows the database sends per round trip while an export reads the list.
CHUNK_SIZE = 2000


@dataclass(frozen=True, slots=True)
class Column:
    """One column of an export: its header and how a row's value is read."""

    name: str
    get: Callable[[models.Model], Any]
    #: A JSON field: JSON keeps the data, the other formats write it as JSON text.
    structured: bool = False


def get_columns(model_admin: Any, request: HttpRequest) -> list[Column]:
    """The columns of ``model_admin.get_export_fields()``, in their order."""
    opts = model_admin.model._meta
    columns = []
    for entry in model_admin.get_export_fields(request):
        try:
            field = opts.get_field(entry) if isinstance(entry, str) else None
        except FieldDoesNotExist:
            field = None
        if field is None or not (field.concrete or field.many_to_many):
            columns.append(Column(_entry_name(entry), _lookup(entry, model_admin)))
        elif field.many_to_many:
            columns.append(Column(field.name, _related_pks(field.name)))
        elif field.is_relation:
            columns.append(Column(field.name, _attribute(field.attname)))
        else:
            structured = isinstance(field, models.JSONField)
            columns.append(Column(field.name, field.value_from_object, structured=structured))
    return columns


def _entry_name(entry: str | Callable[..., Any]) -> str:
    return entry if isinstance(entry, str) else getattr(entry, "__name__", str(entry))


def _attribute(attname: str) -> Callable[[models.Model], Any]:
    return lambda obj: getattr(obj, attname)


def _related_pks(name: str) -> Callable[[models.Model], Any]:
    return lambda obj: sorted(related.pk for related in getattr(obj, name).all())


def _lookup(entry: str | Callable[..., Any], model_admin: Any) -> Callable[[models.Model], Any]:
    def get(obj: models.Model) -> Any:
        try:
            _field, _attr, value = lookup_field(entry, obj, model_admin)
        except ObjectDoesNotExist:
            return None
        return value

    return get


def export_rows(columns: list[Column], queryset: models.QuerySet[Any]) -> Iterator[list[Any]]:
    """Each row's values, read in chunks, with the many-to-many columns prefetched."""
    opts = queryset.model._meta
    many = [column.name for column in columns if column.name in {field.name for field in opts.many_to_many}]
    if many:
        queryset = queryset.prefetch_related(*many)
    for obj in queryset.iterator(chunk_size=CHUNK_SIZE):
        yield [column.get(obj) for column in columns]


def export_filename(opts: Any, export_format: FileFormat) -> str:
    stamp = timezone.localtime().strftime("%Y-%m-%d-%H%M")
    return f"{slugify(str(opts.verbose_name_plural))}-{stamp}.{export_format.extension}"


# The background job


def job_request(job: ExportJob) -> HttpRequest:
    """A GET request for the job's changelist as its user, for ``get_queryset()`` and the filters."""
    request = HttpRequest()
    request.method = "GET"
    request.GET = QueryDict(job.query)
    request.user = job.user
    return request


def run_export_job(job_id: int) -> None:
    """Write the file of one export job. A task queue calls this with the job's id."""
    from django_formwork.admin.models import ExportJob
    from django_formwork.admin.sites import get_site

    job = ExportJob.objects.select_related("user", "content_type").get(pk=job_id)
    if job.is_finished:
        return
    job.status = ExportJob.Status.RUNNING
    job.save(update_fields=["status"])
    try:
        site = get_site(job.site_name)
        model = job.content_type.model_class()
        model_admin = site.get_model_admin_or_none(model) if site is not None and model is not None else None
        if model_admin is None:
            msg = f"No admin for {job.content_type} on the site {job.site_name!r}."
            raise LookupError(msg)  # noqa: TRY301
        request = job_request(job)
        request.path = model_admin.changelist_url(request)
        export_format = FORMATS[job.format]
        columns = model_admin.get_export_columns(request)
        counter = _Counter(export_rows(columns, model_admin.get_export_queryset(request)))
        buffer = io.BytesIO()
        export_format.write(columns, counter, buffer)
        job.file.save(export_filename(model_admin.opts, export_format), ContentFile(buffer.getvalue()), save=False)
    except Exception as exc:
        job.status = ExportJob.Status.FAILED
        job.error = f"{type(exc).__name__}: {exc}"
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        raise
    job.status = ExportJob.Status.DONE
    job.row_count = counter.count
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "file", "row_count", "finished_at"])


class _Counter:
    """Passes rows through and counts them."""

    def __init__(self, rows: Iterable[list[Any]]) -> None:
        self.rows = rows
        self.count = 0

    def __iter__(self) -> Iterator[list[Any]]:
        for row in self.rows:
            self.count += 1
            yield row
