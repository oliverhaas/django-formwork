"""The admin's background tasks, on Django's task framework."""

from __future__ import annotations

from django.tasks import task

from django_formwork.admin.exports import run_export_job

__all__ = ["run_export"]


@task
def run_export(job_id: int) -> None:
    """Write the file of an export job."""
    run_export_job(job_id)
