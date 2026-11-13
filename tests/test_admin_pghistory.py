"""The admin's pghistory backend, which runs on PostgreSQL with ``settings.postgres``."""

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
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


@pytest.mark.parametrize("name", ["Draft", "Plain"])
def test_admin_pages_render(admin_client, models, name):
    model = getattr(models, name)
    obj = model.objects.create()
    for view, args in [
        ("changelist", ()),
        ("add", ()),
        ("change", (obj.pk,)),
        ("history", (obj.pk,)),
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
