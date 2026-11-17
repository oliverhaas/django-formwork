"""Every page of the example admin renders with the seeded sample data."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils.text import capfirst
from markupsafe import escape

from django_formwork.admin import site
from django_formwork.admin.options import SLOTS


def admin_url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


@pytest.fixture
def seeded(db):
    call_command("seed", scale=0.02, stdout=StringIO())


@pytest.mark.parametrize("model", list(site._registry), ids=lambda model: model._meta.label)
def test_admin_pages_render(admin_client, admin_user, rf, seeded, model):
    obj = model._default_manager.order_by("pk").first()
    request = rf.get("/")
    request.user = admin_user

    changelist = admin_client.get(admin_url(model, "changelist"), {"q": "a"})
    add = admin_client.get(admin_url(model, "add"))
    change = admin_client.get(admin_url(model, "change", obj.pk))

    assert changelist.status_code == 200
    assert str(escape(capfirst(model._meta.verbose_name_plural))) in changelist.content.decode()
    assert add.status_code == (200 if site.get_model_admin(model).has_add_permission(request) else 403)
    assert change.status_code == 200
    assert str(escape(obj)) in change.content.decode()


def slots(view):
    return [
        (model, slot)
        for model, model_admin in site._registry.items()
        for slot in SLOTS
        if getattr(model_admin, f"{view}_{slot}", None)
    ]


def slot_id(value):
    return value if isinstance(value, str) else value._meta.label


@pytest.mark.parametrize(
    "search",
    [{"q": "a", "shows": "data-chart"}, {"q": "no row has this", "shows": "match the filters"}],
    ids=["rows", "no rows"],
)
@pytest.mark.parametrize(("model", "slot"), slots("list"), ids=slot_id)
def test_list_slots_render(admin_client, seeded, model, slot, search):
    """A list's slot draws its chart, and says so when the search leaves no rows."""
    response = admin_client.get(admin_url(model, "slot", slot), {"q": search["q"]})

    assert response.status_code == 200
    assert search["shows"] in response.content.decode()


@pytest.mark.parametrize(("model", "slot"), slots("change"), ids=slot_id)
def test_change_slots_render_for_every_row(admin_user, rf, seeded, model, slot):
    request = rf.get("/")
    request.user = admin_user
    method = getattr(site.get_model_admin(model), f"change_{slot}")

    for obj in model._default_manager.all():
        assert "card" in method(request, obj)
