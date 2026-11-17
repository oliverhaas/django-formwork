from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Member, Profile, Tag, Task

MEMBERS = ["Devon Vega", "Mira Chen", "Sasha Petrov", "Iris Okafor", "Kai Tanaka", "Robin Larsen"]
TAGS = [
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
TASKS = [
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


def clear() -> None:
    Task.objects.all().delete()
    Tag.objects.all().delete()
    Member.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:  # noqa: ARG001
    members = {
        name.split()[0]: Member.objects.create(name=name, email=f"{name.split()[0].lower()}@example.com")
        for name in MEMBERS
    }
    tags = {name: Tag.objects.create(name=name) for name in TAGS}
    today = timezone.localdate()
    for title, status, priority, assignee, tag_names, due_offset in TASKS:
        due_date = today + timedelta(days=due_offset)
        task = Task.objects.create(
            title=title,
            description=f"Auto-generated example task. Owner: {assignee or 'unassigned'}.",
            status=status,
            priority=priority,
            assignee=members[assignee] if assignee else None,
            due_date=due_date,
            # An open task due after today reminds at 9:00 the day before.
            remind_at=timezone.make_aware(datetime.combine(due_date - timedelta(days=1), time(9)))
            if status != Task.Status.DONE and due_offset > 0
            else None,
            rating=rng.choice([None, 3, 4, 4, 5]) if status == Task.Status.DONE else None,
        )
        task.tags.set([tags[name] for name in tag_names])
    Profile.load()
    return f"{len(TASKS)} tasks, {len(tags)} tags, {len(members)} members"
