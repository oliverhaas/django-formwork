"""Tests for tasks: My work, the board and the task page."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from taskmanager.models import Activity, Member, Profile, Task
from taskmanager.views import DONE_ON_BOARD


def _member(name="Mira Chen", email="mira@example.com"):
    return Member.objects.create(name=name, email=email)


@pytest.fixture
def me(db):
    """The member the profile names, as Settings sets it."""
    member = _member(name="Devon Vega", email="devon@example.com")
    profile = Profile.load()
    profile.member = member
    profile.save()
    return member


def test_member_initials_from_full_and_single_names(db):
    assert _member(name="Mira Chen").initials == "MC"
    assert _member(name="Robin", email="robin@example.com").initials == "RO"


def test_task_create_assigns_a_member(client, db):
    member = _member()
    response = client.post(
        reverse("task_create"),
        {
            "title": "Ship the release",
            "priority": Task.Priority.HIGH,
            "status": Task.Status.TODO,
            "assignee": member.pk,
        },
    )
    assert response.status_code == 302
    task = Task.objects.get(title="Ship the release")
    assert task.assignee == member


def test_deleting_a_member_keeps_the_task(client, db):
    member = _member()
    task = Task.objects.create(title="Orphan me", assignee=member)
    member.delete()
    task.refresh_from_db()
    assert task.assignee is None


def test_my_work_lists_my_open_tasks_by_due_date(client, me):
    today = timezone.localdate()
    Task.objects.create(title="Later task", assignee=me, due_date=today + timedelta(days=30))
    Task.objects.create(title="Week task", assignee=me, due_date=today + timedelta(days=2))
    Task.objects.create(title="Overdue task", assignee=me, due_date=today - timedelta(days=1))
    Task.objects.create(title="Someone else's task", assignee=_member(), due_date=today)
    content = client.get(reverse("dashboard")).content.decode()
    assert content.index("Overdue task") < content.index("Week task") < content.index("Later task")
    assert "Someone else&#x27;s task" not in content


def test_quick_add_assigns_the_task_to_me(client, me):
    response = client.post(reverse("dashboard"), {"title": "Book the room"})
    assert response.status_code == 302
    assert Task.objects.get(title="Book the room").assignee == me


def test_ticking_a_task_marks_it_done_and_unticking_reopens_it(client, me):
    task = Task.objects.create(title="Tick me", assignee=me, status=Task.Status.IN_PROGRESS)
    client.post(reverse("task_done", args=[task.pk]), {"done": "on"})
    task.refresh_from_db()
    assert task.status == Task.Status.DONE
    client.post(reverse("task_done", args=[task.pk]))
    task.refresh_from_db()
    assert task.status == Task.Status.TODO
    assert list(task.activity.values_list("value", flat=True)) == ["Done", "To Do"]


def test_board_puts_my_tasks_first_in_a_column(client, me):
    today = timezone.localdate()
    Task.objects.create(title="Their task", assignee=_member(), due_date=today)
    Task.objects.create(title="My task", assignee=me, due_date=today + timedelta(days=9))
    content = client.get(reverse("board")).content.decode()
    assert content.index("My task") < content.index("Their task")


def test_board_filter_narrows_the_columns(client, db):
    Task.objects.create(title="Urgent thing", priority=Task.Priority.CRITICAL)
    Task.objects.create(title="Minor thing", priority=Task.Priority.LOW)
    content = client.get(reverse("board"), {"priority": Task.Priority.CRITICAL}).content.decode()
    assert "Urgent thing" in content
    assert "Minor thing" not in content


def test_board_leaves_older_done_tasks_to_the_admin(client, db):
    tasks = [Task.objects.create(title=f"Finished {i:02d}", status=Task.Status.DONE) for i in range(DONE_ON_BOARD + 1)]
    content = client.get(reverse("board")).content.decode()
    assert tasks[-1].title in content
    assert tasks[0].title not in content
    assert "status__exact=done" in content


def test_board_move_changes_the_status_and_records_it(client, me):
    task = Task.objects.create(title="Move me")
    response = client.post(reverse("board_move"), {"task": task.pk, "status": Task.Status.REVIEW})
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == Task.Status.REVIEW
    entry = task.activity.get()
    assert (entry.author, entry.field, entry.value) == (me, "Status", "In Review")


def test_board_add_assigns_the_task_to_me_and_keeps_the_filters(client, me):
    response = client.post(
        f"{reverse('board_add')}?priority=high", {"title": "Draft the agenda", "status": Task.Status.IN_PROGRESS}
    )
    assert response["Location"] == f"{reverse('board')}?priority=high"
    task = Task.objects.get(title="Draft the agenda")
    assert (task.assignee, task.status) == (me, Task.Status.IN_PROGRESS)


def test_task_page_saves_a_change_and_records_it(client, me):
    task = Task.objects.create(title="Finish me", priority=Task.Priority.HIGH)
    response = client.post(
        reverse("task_detail", args=[task.pk]),
        {"status": Task.Status.DONE, "priority": Task.Priority.HIGH, "assignee": ""},
    )
    assert response["HX-Trigger"] == "task-changed"
    task.refresh_from_db()
    assert task.status == Task.Status.DONE
    entry = task.activity.get()
    assert (entry.author, entry.field, entry.value) == (me, "Status", "Done")


def test_comment_is_saved_with_my_name(client, me):
    task = Task.objects.create(title="Discuss me")
    response = client.post(reverse("task_comment", args=[task.pk]), {"comment": "  Looks good.  "})
    assert response["Location"] == task.get_absolute_url()
    entry = task.activity.get()
    assert (entry.author, entry.comment) == (me, "Looks good.")


def test_blank_comment_is_rejected(client, me):
    task = Task.objects.create(title="Discuss me")
    response = client.post(reverse("task_comment", args=[task.pk]), {"comment": "   "})
    assert response.status_code == 200
    assert b'aria-invalid="true"' in response.content
    assert not Activity.objects.exists()
