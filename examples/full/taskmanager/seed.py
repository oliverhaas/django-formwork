from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Activity, Member, Profile, Tag, Task

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
# Title, status, priority, assignee, tags, due in days (None for no date), description.
TASKS = [
    (
        "Move auth onto django-allauth",
        "in_progress",
        "high",
        "Devon",
        ["backend", "security"],
        -3,
        (
            "Our own login views predate social sign-in and miss rate limits. allauth covers both, and its "
            "templates take the form renderer, so the pages keep our look.\n\n"
            "Keep the session cookie name, so nobody gets logged out on deploy."
        ),
    ),
    (
        "Drop legacy /api/v1 endpoints",
        "in_progress",
        "critical",
        "Devon",
        ["backend"],
        -1,
        (
            "v1 has had no traffic from our own clients for two releases. Two integrations still call it; both "
            "owners have the migration guide.\n\nRemove the routes, the serializers and their tests in one change."
        ),
    ),
    (
        "Fix dropdown clipping in Safari",
        "review",
        "medium",
        "Devon",
        ["frontend", "bug"],
        0,
        (
            "In Safari 17 the assignee dropdown is cut off at the bottom of a table cell. The popover needs the "
            "top layer there too."
        ),
    ),
    (
        "Review the 0.2 changelog draft",
        "todo",
        "medium",
        "Devon",
        ["docs"],
        2,
        "Iris wrote the first draft. Check that every breaking change says what to do after the upgrade.",
    ),
    (
        "Pick a date for the team offsite",
        "todo",
        "low",
        "Devon",
        [],
        5,
        "Three weekends are left in the poll. Pick the one that most people can make and book the venue.",
    ),
    (
        "Set up preview deploys for pull requests",
        "todo",
        "medium",
        "Devon",
        ["infra"],
        12,
        (
            "Each pull request gets its own short-lived app with a copy of the sample data, so a review can "
            "click through the change."
        ),
    ),
    (
        "Rotate the staging database password",
        "todo",
        "high",
        "Devon",
        ["security", "infra"],
        None,
        "The old password was in a screenshot in the onboarding docs. Rotate it and move it to the secret store.",
    ),
    (
        "Upgrade to Django 6.0",
        "done",
        "high",
        "Devon",
        ["backend"],
        -4,
        "Template partials replace our own include tags. The test suite passes on 6.0 without warnings.",
    ),
    (
        "Fix the flaky login test",
        "done",
        "medium",
        "Devon",
        ["bug"],
        -2,
        "The test read the clock twice and failed when a second passed between the reads.",
    ),
    (
        "Audit a11y on the dashboard",
        "review",
        "medium",
        "Mira",
        ["frontend", "a11y"],
        1,
        (
            "Run axe and a screen reader over the dashboard. File one task per finding, with the element and the "
            "rule it breaks."
        ),
    ),
    (
        "Migrate icons to django-iconx",
        "done",
        "low",
        "Sasha",
        ["frontend", "polish"],
        -8,
        "One icon set, served as masks, instead of three inline SVG copies.",
    ),
    (
        "Onboarding wizard copy review",
        "todo",
        "medium",
        "Iris",
        ["design", "docs"],
        4,
        "The wizard's help texts explain the widgets, not the project. Rewrite them for a new user.",
    ),
    (
        "Tighten CSP headers",
        "todo",
        "high",
        "Kai",
        ["security", "infra"],
        2,
        "Drop unsafe-inline for scripts. The theme switcher's inline script needs a nonce first.",
    ),
    (
        "Replace sentry-sdk with OpenTelemetry",
        "review",
        "high",
        "Robin",
        ["infra", "perf"],
        6,
        "Traces and errors go to one collector. The sampling rate stays at 10 percent.",
    ),
    (
        "Settings: add 2FA enrolment",
        "todo",
        "high",
        "Mira",
        ["frontend", "security"],
        7,
        "Show a QR code, ask for one code from the app, then show the recovery codes once.",
    ),
    (
        "Investigate htmx morph flicker",
        "in_progress",
        "medium",
        "Sasha",
        ["frontend", "bug"],
        -2,
        ("A dropdown that is open during a morph closes and opens again. Find out which attribute the morph resets."),
    ),
    (
        "Write the release notes for 0.2",
        "todo",
        "low",
        "Iris",
        ["docs"],
        3,
        "A short post for the blog: three features with a screenshot each, then the full changelog link.",
    ),
    (
        "Spike: server-sent events for the board",
        "todo",
        "low",
        "Kai",
        ["research", "backend"],
        10,
        "Two days at most. Find out whether the board can show other people's moves without a reload.",
    ),
    (
        "Tune the Postgres pool size",
        "done",
        "medium",
        "Robin",
        ["infra", "perf"],
        -12,
        "Twenty connections per worker were too many for the small database plan.",
    ),
    (
        "Add a confirmation to bulk delete",
        "todo",
        "low",
        "",
        ["frontend"],
        5,
        "Deleting more than ten rows asks first and names the count.",
    ),
    (
        "Document the deploy runbook",
        "in_progress",
        "medium",
        "Robin",
        ["docs", "infra"],
        2,
        "Who deploys, how to roll back, and whom to call when the migration step fails.",
    ),
]
COMMENTS = [
    "I'll pick this up after standup.",
    "First draft is up, feedback welcome.",
    "Blocked on the staging deploy. It should clear by tomorrow.",
    "Looks good to me. One question about the naming, see the review.",
    "Can we split this? The second half needs input from design.",
    "Paired with Kai on this. The fix is smaller than we thought.",
    "I moved the due date. The review took longer than planned.",
    "Tested it on a phone too, no problems there.",
    "Do we need a changelog line for this?",
    "Yes, under Fixes. One sentence is enough.",
]
STEPS = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.REVIEW, Task.Status.DONE]


def clear() -> None:
    Task.objects.all().delete()
    Tag.objects.all().delete()
    Member.objects.all().delete()


def history(rng: random.Random, task: Task, created: datetime, members: list[Member]) -> None:
    """Comments and status changes between the task's creation and now."""
    moves = STEPS[1 : STEPS.index(task.status) + 1]
    count = len(moves) + rng.randint(0, 3)
    stamps = sorted(created + (timezone.now() - created) * rng.random() for _ in range(count))
    owner = task.assignee or rng.choice(members)
    is_move = [True] * len(moves) + [False] * (count - len(moves))
    rng.shuffle(is_move)
    # Moves keep their order, so a task never goes backwards. The assignee makes most of them; anyone comments.
    statuses = iter(moves)
    for stamp, move in zip(stamps, is_move, strict=True):
        if move:
            author = owner if rng.random() < 0.8 else rng.choice(members)
            entry = Activity(author=author, field="Status", value=Task.Status(next(statuses)).label)
        else:
            entry = Activity(author=rng.choice(members), comment=rng.choice(COMMENTS))
        entry.task = task
        entry.created_at = stamp
        entry.save()


def seed(rng: random.Random, scale: float) -> str:  # noqa: ARG001
    members = {
        name.split()[0]: Member.objects.create(name=name, email=f"{name.split()[0].lower()}@example.com")
        for name in MEMBERS
    }
    tags = {name: Tag.objects.create(name=name) for name in TAGS}
    now = timezone.now()
    today = timezone.localdate()
    for title, status, priority, assignee, tag_names, due_offset, description in TASKS:
        due_date = today + timedelta(days=due_offset) if due_offset is not None else None
        task = Task.objects.create(
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee=members[assignee] if assignee else None,
            due_date=due_date,
            # An open task due after today reminds at 9:00 the day before.
            remind_at=timezone.make_aware(datetime.combine(due_date - timedelta(days=1), time(9)))
            if due_date and status != Task.Status.DONE and due_offset > 0
            else None,
            rating=rng.choice([None, 3, 4, 4, 5]) if status == Task.Status.DONE else None,
        )
        task.tags.set([tags[name] for name in tag_names])
        created = now - timedelta(days=rng.randint(6, 30), hours=rng.randint(0, 23))
        history(rng, task, created, list(members.values()))
        last = task.activity.order_by("-created_at").values_list("created_at", flat=True).first()
        Task.objects.filter(pk=task.pk).update(created_at=created, updated_at=last or created)
    profile = Profile.load()
    profile.member = members["Devon"]
    profile.save()
    return f"{len(TASKS)} tasks, {len(tags)} tags, {len(members)} members"
