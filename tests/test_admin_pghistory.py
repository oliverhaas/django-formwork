"""The admin's pghistory backend, which runs on PostgreSQL with ``settings.postgres``."""

import csv
import io
import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from django_formwork.admin import site
from django_formwork.admin.history import PghistoryHistory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not apps.is_installed("history_app"), reason="needs pghistory on PostgreSQL"),
]


@pytest.fixture(autouse=True)
def pghistory_site(settings, monkeypatch):
    settings.ROOT_URLCONF = "admin_app.urls"
    monkeypatch.setattr(site, "history", PghistoryHistory())


@pytest.fixture
def models():
    from history_app import models

    return models


def url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


def history_rows(client, obj):
    soup = BeautifulSoup(client.get(url(type(obj), "change", obj.pk)).content, "html.parser")
    for hidden in soup.select(".sr-only"):
        hidden.decompose()
    return [row.get_text(" ", strip=True) for row in soup.select("#history li")]


@pytest.mark.parametrize("name", ["Draft", "Memo", "Plain"])
def test_admin_pages_render(admin_client, models, name):
    model = getattr(models, name)
    obj = model.objects.create()
    for view, args in [
        ("changelist", ()),
        ("add", ()),
        ("change", (obj.pk,)),
        ("history_list", ()),
        ("delete", (obj.pk,)),
    ]:
        assert admin_client.get(url(model, view, *args)).status_code == 200, view


def test_change_through_the_admin_names_the_user_and_the_values(admin_client, django_user_model, models):
    ada = django_user_model.objects.create_user("ada")
    draft = models.Draft.objects.create(title="Plan")

    admin_client.post(url(models.Draft, "change", draft.pk), {"title": "Plan", "status": "done", "owner": ada.pk})

    newest = history_rows(admin_client, draft)[0]
    assert "admin" in newest
    assert "Open → Done" in newest
    assert "empty → ada" in newest


def test_change_outside_the_admin_shows_from_the_events(admin_client, models):
    draft = models.Draft.objects.create(title="Plan")
    draft.title = "Final plan"
    draft.save()

    rows = history_rows(admin_client, draft)

    assert "Plan → Final plan" in rows[0]
    assert "Added" in rows[1]


def test_model_without_pghistory_keeps_the_admin_entries(admin_client, models):
    plain = models.Plain.objects.create(name="First")

    admin_client.post(url(models.Plain, "change", plain.pk), {"name": "Second"})

    assert "First → Second" in history_rows(admin_client, plain)[0]


def list_rows(client, model, query=None):
    soup = BeautifulSoup(client.get(url(model, "history_list"), query or {}).content, "html.parser")
    for hidden in soup.select(".sr-only"):
        hidden.decompose()
    return [row.get_text(" ", strip=True) for row in soup.select("#changelist-table tbody tr")]


@pytest.fixture
def drafts(admin_client, models):
    note = models.Draft.objects.create(title="Note")
    note.title = "Short note"
    note.save()
    admin_client.post(url(models.Draft, "add"), {"title": "Plan", "status": "open"})
    plan = models.Draft.objects.exclude(pk=note.pk).get()
    admin_client.post(url(models.Draft, "change", plan.pk), {"title": "Final plan", "status": "open"})
    return SimpleNamespace(plan=plan, note=note)


def test_history_list_shows_each_event_with_its_changes_and_user(admin_client, models, drafts):
    rows = list_rows(admin_client, models.Draft)

    assert len(rows) == 4
    assert "Plan → Final plan" in rows[0]
    assert "admin" in rows[0]
    assert "Added" in rows[1]
    assert "Note → Short note" in rows[2]
    assert "admin" not in rows[2]


@pytest.mark.parametrize(("action", "text"), [("add", "Added"), ("change", "→")])
def test_history_list_filters_the_events_by_action(admin_client, models, drafts, action, text):
    rows = list_rows(admin_client, models.Draft, {"action": action})

    assert len(rows) == 2
    assert all(text in row for row in rows)


def test_history_list_filters_the_events_by_user_and_object(admin_client, admin_user, models, drafts):
    by_user = list_rows(admin_client, models.Draft, {"user": admin_user.pk})
    by_object = list_rows(admin_client, models.Draft, {"object": drafts.note.pk})

    assert len(by_user) == 2
    assert all("Final plan" in row for row in by_user)
    assert len(by_object) == 2
    assert all("Short note" in row for row in by_object)


def test_history_list_names_a_deleted_object_as_each_event_had_it(admin_client, models, drafts):
    admin_client.post(url(models.Draft, "delete", drafts.plan.pk))

    rows = list_rows(admin_client, models.Draft, {"action": "add"})

    assert "Plan (deleted)" in rows[0]


def test_history_list_counts_the_first_snapshot_of_an_object_as_added(admin_client, models):
    memo = models.Memo.objects.create(text="Draft")
    memo.text = "Sent"
    memo.save()

    added = list_rows(admin_client, models.Memo, {"action": "add"})
    changed = list_rows(admin_client, models.Memo, {"action": "change"})

    assert len(added) == 1
    assert "Added" in added[0]
    assert len(changed) == 1
    assert "Draft → Sent" in changed[0]


def test_history_list_exports_the_events(admin_client, models, drafts):
    response = admin_client.post(url(models.Draft, "history_export"), {"format": "csv", "query": "action=change"})

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert [row["object"] for row in rows] == ["Final plan", "Short note"]
    assert rows[0]["user"] == "admin"
    assert rows[0]["changes"] == "Title: Plan → Final plan"


def test_history_list_queries_stay_the_same_for_more_events(admin_client, django_user_model, models):
    ada, bob = (django_user_model.objects.create_user(name) for name in ("ada", "bob"))

    def add_drafts(count):
        for number in range(count):
            draft = models.Draft.objects.create(title=f"Draft {number}", owner=ada)
            draft.owner, draft.status = bob, "done"
            draft.save()

    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin_client.get(url(models.Draft, "history_list"))
        return len(captured)

    add_drafts(1)
    few = queries()
    add_drafts(5)

    assert queries() == few
    assert "ada → bob" in list_rows(admin_client, models.Draft)[0]


def plan_nodes(plan):
    yield plan["Node Type"]
    for child in plan.get("Plans", ()):
        yield from plan_nodes(child)


@pytest.mark.parametrize("name", ["Draft", "Plain"])
@pytest.mark.parametrize("query", [{}, {"o": "0"}])
def test_history_list_reads_its_page_in_the_order_of_an_index(admin_user, rf, models, name, query):
    """A page of a long history reads its rows from an index, not from a sort of the whole table."""
    model = getattr(models, name)
    request = rf.get(url(model, "history_list"), query)
    request.user = admin_user
    rows = site.get_model_admin(model).get_history_admin().get_changelist_instance(request).queryset

    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")

    plan = json.loads(rows[:50].explain(format="json"))[0]["Plan"]

    assert "Sort" not in set(plan_nodes(plan))


def test_model_without_pghistory_lists_the_admin_entries(admin_client, models):
    plain = models.Plain.objects.create(name="First")

    admin_client.post(url(models.Plain, "change", plain.pk), {"name": "Second"})

    assert "First → Second" in list_rows(admin_client, models.Plain)[0]
