"""The admin's own tables: the history of changes, and exports that run in the background."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

__all__ = ["ExportJob", "HistoryEntry"]


def export_path(job: ExportJob, filename: str) -> str:
    # The job id in the name keeps the file apart from other exports of the same day.
    return f"formwork_admin/exports/{job.created_at:%Y/%m}/{job.pk}-{filename}"


class ExportJob(models.Model):
    """One export of a changelist, with the file it produced."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting")
        RUNNING = "running", _("Running")
        DONE = "done", _("Ready")
        FAILED = "failed", _("Failed")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    site_name = models.CharField(max_length=100)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    query = models.TextField(blank=True, help_text=_("The changelist's filters, search and ordering."))
    format = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file = models.FileField(upload_to=export_path, max_length=255, blank=True)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = (models.Index(fields=["user", "-created_at"], name="formwork_admin_export_user"),)
        verbose_name = _("export")
        verbose_name_plural = _("exports")

    def __str__(self) -> str:
        return f"{self.content_type} ({self.format}, {self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_finished(self) -> bool:
        return self.status in (self.Status.DONE, self.Status.FAILED)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Delete the row and its file."""
        if self.file:
            self.file.delete(save=False)
        return super().delete(*args, **kwargs)


class HistoryEntry(models.Model):
    """One addition, change or deletion made through the admin.

    ``changes`` holds the list that ``construct_change_message`` returns, with the values before and
    after each field. ``message`` holds a text that an admin passes to ``log_change`` instead.
    """

    class Action(models.TextChoices):
        ADD = "add", _("Added")
        CHANGE = "change", _("Changed")
        DELETE = "delete", _("Deleted")

    time = models.DateTimeField(default=timezone.now, editable=False)
    # A deleted user keeps the entries, which then name no one.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    object_id = models.CharField(max_length=255)
    object_repr = models.CharField(max_length=200)
    action = models.CharField(max_length=10, choices=Action.choices)
    changes = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ("-time", "-pk")
        indexes = (
            models.Index(fields=["content_type", "object_id", "-time"], name="formwork_admin_history_obj"),
            models.Index(fields=["user", "-time"], name="formwork_admin_history_user"),
        )
        verbose_name = _("history entry")
        verbose_name_plural = _("history entries")

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.object_repr}"
