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


def _row_post(task, **changes):
    """A per-row autosave payload: the row's editable fields, plus overrides."""
    data = {
        "id": str(task.pk),
        "_formwork_prefix": "",
        "status": task.status,
        "priority": task.priority,
        "assignee": task.assignee_id or "",
    }
    data.update(changes)
    return data


def test_row_edit_reassigns_via_htmx(client, db):
    member = _member()
    task = Task.objects.create(title="Reassign me")
    response = client.post(
        reverse("task_row_save"),
        _row_post(task, assignee=member.pk),
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.assignee == member


def test_row_edit_can_unassign(client, db):
    member = _member()
    task = Task.objects.create(title="Unassign me", assignee=member)
    response = client.post(
        reverse("task_row_save"),
        _row_post(task, assignee=""),
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.assignee is None


def test_row_edit_cannot_clobber_readonly_fields(client, db):
    """A row POST may change editable columns; a disabled column (title) is ignored."""
    task = Task.objects.create(title="Keep my title", status=Task.Status.REVIEW)
    client.post(
        reverse("task_row_save"),
        _row_post(task, title="HACKED", status=Task.Status.DONE),
        headers={"HX-Request": "true"},
    )
    task.refresh_from_db()
    assert task.title == "Keep my title"  # disabled column, untouched by POST
    assert task.status == Task.Status.DONE  # editable column, saved


def test_list_rows_are_keyed_by_task_pk(client, db):
    """Rows carry a pk-based identity (id + prefix), not a positional formset
    index, so htmx morph tracks each row across re-renders instead of swapping
    content between slots."""
    a = Task.objects.create(title="First")
    b = Task.objects.create(title="Second")
    content = client.get(reverse("task_list")).content.decode()
    for task in (a, b):
        assert f'id="formwork-row-task-{task.pk}"' in content
        assert f'value="task-{task.pk}"' in content  # round-tripped _formwork_prefix
    assert 'id="formwork-row-form-0"' not in content  # no positional ids


def test_add_task_appends_a_draft_row(client, db):
    before = Task.objects.count()
    response = client.post(reverse("task_add"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert Task.objects.count() == before + 1
    assert b"<tbody" in response.content
    task = Task.objects.latest("id")
    content = response.content.decode()
    assert f'id="formwork-row-task-{task.pk}"' in content  # same pk scheme as the list


def test_inline_delete_removes_the_task(client, db):
    task = Task.objects.create(title="Delete me")
    response = client.post(
        reverse("task_delete", kwargs={"pk": task.pk}),
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert not Task.objects.filter(pk=task.pk).exists()


def test_deleting_a_member_keeps_the_task(client, db):
    member = _member()
    task = Task.objects.create(title="Orphan me", assignee=member)
    member.delete()
    task.refresh_from_db()
    assert task.assignee is None


def test_search_filter_has_type_search_with_leading_magnifier(client, db):
    """The filter search box is a type=search input with a leading magnifier icon."""
    content = client.get(reverse("task_list")).content.decode()
    assert '<input type="search" name="q"' in content
    assert "icon-search" in content  # leading magnifier


def test_status_and_priority_filters_have_floating_labels(client, db):
    """The select filters carry floating labels so the active filter reads clearly."""
    content = client.get(reverse("task_list")).content.decode()
    assert content.count('class="floating-label"') == 2
    assert "<span>Status</span>" in content
    assert "<span>Priority</span>" in content


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
