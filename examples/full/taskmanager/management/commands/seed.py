"""Seed the example database with realistic tasks + tags."""

from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from taskmanager.models import Tag, Task


class Command(BaseCommand):
    help = "Reset the database and populate it with sample tasks."

    def handle(self, *args, **options):  # noqa: ARG002
        Task.objects.all().delete()
        Tag.objects.all().delete()

        tag_names = [
            "frontend",
            "backend",
            "design",
            "infra",
            "docs",
            "bug",
            "feature",
            "polish",
            "research",
            "security",
            "perf",
            "a11y",
        ]
        tags = {n: Tag.objects.create(name=n) for n in tag_names}

        seed_tasks = [
            ("Move auth onto django-allauth", "in_progress", "high", "Devon", ["backend", "security"], -3),
            ("Audit a11y on the dashboard", "review", "medium", "Mira", ["frontend", "a11y"], 1),
            ("Migrate icons to django-iconx", "done", "low", "Sasha", ["frontend", "polish"], -8),
            ("Onboarding wizard copy review", "todo", "medium", "Iris", ["design", "docs"], 4),
            ("Tighten CSP headers", "todo", "high", "Kai", ["security", "infra"], 2),
            ("Drop legacy /api/v1 endpoints", "in_progress", "critical", "Devon", ["backend"], -1),
            ("Replace sentry-sdk with otel", "review", "high", "Robin", ["infra", "perf"], 6),
            ("Settings: add 2FA enrolment flow", "todo", "high", "Mira", ["frontend", "security"], 7),
            ("Investigate htmx morph flicker", "in_progress", "medium", "Sasha", ["frontend", "bug"], -2),
            ("Write changelog for 0.2 release", "todo", "low", "Iris", ["docs"], 3),
            ("Spike: server-sent events for tasks", "todo", "low", "Kai", ["research", "backend"], 10),
            ("Tune Postgres pool size", "done", "medium", "Robin", ["infra", "perf"], -12),
            ("Fix dropdown clipping in safari", "review", "medium", "Devon", ["frontend", "bug"], 0),
            ("Add bulk-delete confirmation", "todo", "low", "", ["frontend"], 5),
            ("Document deploy runbook", "in_progress", "medium", "Robin", ["docs", "infra"], 2),
        ]

        now = timezone.now()
        created = 0
        for title, status, priority, assignee, tag_keys, due_offset in seed_tasks:
            t = Task.objects.create(
                title=title,
                description=f"Auto-generated example task. Owner: {assignee or 'unassigned'}.",
                status=status,
                priority=priority,
                assignee=assignee,
                due_date=(now + timedelta(days=due_offset)).date() if due_offset is not None else None,
                rating=random.choice([None, 3, 4, 4, 5]) if status == "done" else None,  # noqa: S311
            )
            t.tags.set([tags[n] for n in tag_keys])
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} tasks, {len(tags)} tags."))
