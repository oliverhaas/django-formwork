"""E2e tests for the admin's changelist filters, selection, columns and imports, and its inline rows."""

import re

import django_filters
import pytest
from admin_app.models import Category, Item, Part
from django.utils import timezone
from playwright.sync_api import expect

from django_formwork.admin import site

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def admin_page(page, live_server, settings, _e2e_settings, django_user_model):
    settings.ROOT_URLCONF = "admin_app.urls"
    django_user_model.objects.create_superuser("ada", password="pw-12345")
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type in {"error", "warning"} else None)
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("[name=username]", "ada")
    page.fill("[name=password]", "pw-12345")
    page.click("button[type=submit]")
    expect(page).to_have_url(f"{live_server.url}/admin/")
    page.errors = errors
    return page


@pytest.fixture
def kitchen():
    return Category.objects.create(name="Kitchen", slug="kitchen")


def test_selection_works_after_a_search_swap(admin_page, live_server, kitchen):
    for name in ("Kettle", "Toaster", "Kettle lid"):
        Item.objects.create(name=name, category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.locator("[data-search] input:not([type=hidden])").fill("kettle")
    expect(admin_page).to_have_url(re.compile(r"\?q=kettle$"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(2)
    admin_page.locator("#changelist tbody input[type=checkbox]").first.click()

    expect(admin_page.locator("#changelist-actions")).to_contain_text("1 selected")
    assert admin_page.errors == []


def test_a_date_filter_preset_filters_the_list(admin_page, live_server, kitchen):
    today = timezone.localdate()
    Item.objects.create(name="Kettle", category=kitchen, released=today)
    Item.objects.create(name="Toaster", category=kitchen, released=today.replace(year=today.year - 1))
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.get_by_role("button", name="Filters").click()
    admin_page.locator("#id_released").click()
    admin_page.get_by_role("button", name="This year").click()

    first, last = today.replace(month=1, day=1), today.replace(month=12, day=31)
    expect(admin_page).to_have_url(re.compile(rf"released_0={first}&released_1={last}"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(1)
    expect(admin_page.locator("#changelist tbody")).to_contain_text("Kettle")
    assert admin_page.errors == []


def test_filter_toggle_shows_the_row_and_counts_active_filters(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", [django_filters.RangeFilter(field_name="quantity")])
    Item.objects.create(name="Kettle", category=kitchen, quantity=5)
    Item.objects.create(name="Toaster", category=kitchen, quantity=40)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    row = admin_page.locator("#changelist-filter-row")
    toggle = admin_page.get_by_role("button", name="Filters")
    expect(row).to_be_hidden()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    admin_page.locator("[name=quantity_min]").fill("10")
    admin_page.locator("[name=quantity_min]").blur()

    expect(admin_page).to_have_url(re.compile(r"\?quantity_min=10$"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(1)
    expect(toggle.locator(".badge")).to_have_text("1")
    clear = admin_page.get_by_role("link", name="Clear all filters")
    expect(clear).to_have_attribute("href", "/admin/admin_app/item/")

    clear.click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(2)
    expect(toggle.locator(".badge")).to_have_text("0")
    expect(row).to_be_visible()
    expect(admin_page.locator("[name=quantity_min]")).to_have_value("")
    assert admin_page.errors == []


def test_info_dialog_keeps_its_content_after_a_search_swap(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    info = admin_page.get_by_role("button", name="About items")
    body = admin_page.locator("#changelist-info-body")
    info.click()
    expect(body).to_contain_text("Rows")
    admin_page.keyboard.press("Escape")

    admin_page.locator("[data-search] input:not([type=hidden])").fill("kettle")
    expect(admin_page).to_have_url(re.compile(r"\?q=kettle$"))
    info.click()

    expect(body).to_contain_text("Rows")
    assert admin_page.errors == []


def test_columns_that_do_not_fit_hide_behind_a_toggle(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 480, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    released = admin_page.locator("#changelist-table thead th", has_text="Released")
    toggle = admin_page.locator("#changelist-table [data-col-toggle] button")
    expect(released).to_be_hidden()
    expect(admin_page.locator("#changelist-table thead th", has_text="Name")).to_be_visible()
    expect(toggle).to_have_attribute("title", re.compile("Released"))

    toggle.click()
    expect(released).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")

    admin_page.reload()
    expect(released).to_be_visible()

    toggle.click()
    expect(released).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    assert admin_page.errors == []


def test_inline_rows_stay_contiguous_after_a_removal(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    Part.objects.create(item=item, name="Lid")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    group = admin_page.locator("#parts-group")
    add = group.get_by_role("button", name=re.compile("Add another part"))
    initial = int(group.locator("[name=parts-TOTAL_FORMS]").input_value())

    add.click()
    add.click()
    group.locator(f"#parts-{initial}").get_by_role("button", name="Remove").click()
    group.locator(f"[name=parts-{initial}-name]").fill("Handle")
    admin_page.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator(".toast .alert").first).to_be_visible()
    assert sorted(item.parts.values_list("name", flat=True)) == ["Handle", "Lid"]
    assert admin_page.errors == []


def test_an_import_checks_the_file_then_saves_it(admin_page, live_server, kitchen, tmp_path):
    kettle = Item.objects.create(name="Kettle", category=kitchen, quantity=1)
    path = tmp_path / "items.csv"
    path.write_text(f"id,name,category__name,quantity\n{kettle.pk},Kettle,Kitchen,5\n,Toaster,Kitchen,2\n")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.get_by_role("link", name="Import").click()
    admin_page.locator("input[type=file]").set_input_files(path)
    admin_page.get_by_role("button", name="Check file").click()
    expect(admin_page.locator("section[id^=import-preview] tbody")).to_contain_text("Toaster")
    admin_page.get_by_role("button", name="Import 2 rows").click()

    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect(admin_page.locator(".toast")).to_contain_text("Imported 2 items: 1 added, 1 changed.")
    kettle.refresh_from_db()
    assert kettle.quantity == 5
    assert Item.objects.get(name="Toaster").category == kitchen
    assert admin_page.errors == []
