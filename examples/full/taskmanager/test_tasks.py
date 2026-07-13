"""Tests for tasks: the Member assignee and the inline row edit."""

from __future__ import annotations

from django.urls import reverse

from taskmanager.models import Member, Task


def _member(name="Mira Chen", email="mira@example.com"):
    return Member.objects.create(name=name, email=email)


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


def test_row_edit_reassigns_via_htmx(client, db):
    member = _member()
    task = Task.objects.create(title="Reassign me")
    response = client.post(
        reverse("task_status", kwargs={"pk": task.pk}),
        {"field": "assignee", "assignee": member.pk},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.assignee == member


def test_row_edit_can_unassign(client, db):
    member = _member()
    task = Task.objects.create(title="Unassign me", assignee=member)
    response = client.post(
        reverse("task_status", kwargs={"pk": task.pk}),
        {"field": "assignee", "assignee": ""},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.assignee is None


def test_row_edit_ignores_fields_outside_the_marker(client, db):
    """Only the field named by the posted "field" marker may change."""
    member = _member()
    task = Task.objects.create(title="Keep my status", status=Task.Status.REVIEW)
    client.post(
        reverse("task_status", kwargs={"pk": task.pk}),
        {"field": "assignee", "assignee": member.pk, "status": Task.Status.DONE},
        headers={"HX-Request": "true"},
    )
    task.refresh_from_db()
    assert task.assignee == member
    assert task.status == Task.Status.REVIEW


def test_deleting_a_member_keeps_the_task(client, db):
    member = _member()
    task = Task.objects.create(title="Orphan me", assignee=member)
    member.delete()
    task.refresh_from_db()
    assert task.assignee is None


def test_task_row_priority_trigger_carries_severity_class(client, db):
    """The priority SearchSelect seeds its trigger class from the saved severity."""
    Task.objects.create(title="Recolor me", priority=Task.Priority.HIGH)
    response = client.get(reverse("task_list"))
    assert response.status_code == 200
    assert b'data-selected-toggle-class="select-soft select-warning"' in response.content


def test_dashboard_shows_assignee_initials_badge(client, db):
    Task.objects.create(title="Badge check", assignee=_member())
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"badge-neutral" in response.content
    assert b"MC" in response.content
