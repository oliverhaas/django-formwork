"""E2e tests for the admin's changelist filters, selection, columns and imports, and its inline rows."""

import re

import django_filters
import pytest
from admin_app.models import Category, Item, Part, Tag
from django.utils import timezone
from playwright.sync_api import expect

from django_formwork.admin import TabularInline, site

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


def test_save_changes_hides_while_the_editable_columns_do(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 390, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    save = admin_page.get_by_role("button", name="Save changes")
    expect(admin_page.locator("#changelist-table thead th", has_text="Quantity")).to_be_hidden()
    expect(save).to_be_hidden()

    admin_page.locator("#changelist-table [data-col-toggle] button").click()
    expect(save).to_be_visible()
    assert admin_page.errors == []


def test_ctrl_k_opens_the_navigation_filter_on_a_phone(admin_page, live_server):
    admin_page.set_viewport_size({"width": 390, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/")

    admin_page.keyboard.press("Control+k")
    expect(admin_page.locator("#formwork-admin-nav-filter")).to_be_focused()
    assert admin_page.errors == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_scrollbar_gutter_takes_the_page_color(admin_page, live_server, scheme):
    admin_page.emulate_media(color_scheme=scheme)
    admin_page.goto(f"{live_server.url}/admin/")

    colors = admin_page.evaluate(
        "[document.documentElement, document.body].map((el) => getComputedStyle(el).backgroundColor)"
    )
    assert colors[0] == colors[1]


def related_dialog(page):
    return page.locator("dialog[open] iframe").content_frame.locator("body")


def test_a_category_added_in_the_dialog_is_chosen_and_saved(admin_page, live_server, kitchen):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    field = admin_page.locator('[data-related="admin_app.category"]')

    field.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    expect(dialog.locator("[name=name]")).to_be_focused()
    dialog.locator("[name=name]").fill("Garden")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    garden = Category.objects.get(name="Garden")
    expect(field.locator("summary")).to_match_aria_snapshot("- text: Garden")
    expect(field.get_by_role("link", name="Change selected category")).to_have_attribute(
        "href", f"/admin/admin_app/category/{garden.pk}/change/"
    )
    admin_page.locator("[name=name]").fill("Spade")
    admin_page.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert Item.objects.get(name="Spade").category == garden
    assert admin_page.errors == []


def test_a_row_added_in_the_dialog_replaces_the_empty_list(admin_page, live_server):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    field = admin_page.locator('[data-related="admin_app.category"]')

    field.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("Garden")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page.locator("dialog")).to_have_count(0)
    field.locator("summary").click()

    expect(field.get_by_role("option")).to_have_text(["Garden"])
    expect(field.get_by_role("option", name="Garden")).to_have_attribute("aria-selected", "true")
    expect(field.get_by_role("status")).to_have_count(0)
    assert admin_page.errors == []


def test_a_tag_added_in_the_dialog_joins_the_picked_tags(admin_page, live_server, kitchen):
    Tag.objects.create(name="sale")
    item = Item.objects.create(name="Kettle", category=kitchen)
    item.tags.add(Tag.objects.get(name="sale"))
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    field = admin_page.locator('[data-related="admin_app.tag"]')

    def hold_the_refresh(route):
        if route.request.headers.get("hx-request") != "true":
            route.continue_()

    admin_page.route(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/", hold_the_refresh)
    field.get_by_role("link", name="Add another tag").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("eco")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page.locator("dialog")).to_have_count(0)
    admin_page.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert sorted(item.tags.values_list("name", flat=True)) == ["eco", "sale"]
    assert admin_page.errors == []


class ItemInline(TabularInline):
    model = Item
    fields = ["name", "status", "tags"]
    extra = 0


def test_a_tag_added_in_the_dialog_shows_in_inline_rows_added_after(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Category), "inlines", [ItemInline])
    admin_page.goto(f"{live_server.url}/admin/admin_app/category/{kitchen.pk}/change/")
    group = admin_page.locator("#items-group")
    add = group.get_by_role("button", name=re.compile("Add another item"))
    add.click()
    group.locator("[name=items-0-name]").fill("Kettle")

    group.locator("#items-0").get_by_role("link", name="Add another tag").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("eco")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(group.locator("#items-0 [data-related] summary")).to_match_aria_snapshot("- text: eco")
    add.click()
    group.locator("[name=items-1-name]").fill("Toaster")
    tags = group.locator("#items-1 [data-related]")
    tags.locator("summary").click()
    tags.get_by_role("option", name="eco").click()
    admin_page.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/category/")
    assert sorted(Item.objects.filter(tags__name="eco").values_list("name", flat=True)) == ["Kettle", "Toaster"]
    assert admin_page.errors == []


def test_escape_in_the_dialog_closes_it_unless_the_form_has_changes(admin_page, live_server):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    add = admin_page.get_by_role("link", name="Add another category")

    add.click()
    expect(related_dialog(admin_page).locator("[name=name]")).to_be_focused()
    admin_page.keyboard.press("Escape")
    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(add).to_be_focused()

    add.click()
    name = related_dialog(admin_page).locator("[name=name]")
    name.fill("Garden")
    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    with admin_page.expect_event("dialog") as prompt:
        admin_page.keyboard.press("Escape")
    assert prompt.value.type == "beforeunload"
    expect(name).to_have_value("Garden")
    assert admin_page.errors == []


def test_leaving_the_form_asks_first_after_a_pick_in_a_dropdown(admin_page, live_server, kitchen):
    url = f"{live_server.url}/admin/admin_app/item/add/"
    admin_page.goto(url)
    field = admin_page.locator('[data-related="admin_app.category"]')
    field.locator("summary").click()
    field.get_by_role("option", name="Kitchen").click()

    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    with admin_page.expect_event("dialog") as prompt:
        admin_page.get_by_label("Breadcrumbs").get_by_role("link", name="Items").click()
    assert prompt.value.type == "beforeunload"
    expect(admin_page).to_have_url(url)
    assert admin_page.errors == []


def test_leaving_the_form_without_a_change_asks_nothing(admin_page, live_server, kitchen):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    prompts = []
    admin_page.on("dialog", lambda prompt: (prompts.append(prompt.type), prompt.dismiss()))
    field = admin_page.locator('[data-related="admin_app.category"]')
    field.locator("summary").click()
    admin_page.keyboard.press("Escape")

    admin_page.get_by_label("Breadcrumbs").get_by_role("link", name="Items").click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert prompts == []
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
