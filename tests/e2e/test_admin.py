"""E2e tests for the admin's changelist filters, selection, columns and imports, and its inline rows."""

import re

import django_filters
import pytest
from admin_app.models import Category, Item, Part, Tag
from django import forms
from django.db.models import ForeignKey
from django.utils import timezone
from playwright.sync_api import expect

from django_formwork.admin import VERTICAL, ActionLocation, TabularInline, action, site

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

    first, after = today.replace(month=1, day=1), today.replace(year=today.year + 1, month=1, day=1)
    expect(admin_page).to_have_url(re.compile(rf"\?released__gte={first}&released__lt={after}$"))
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
    admin_page.locator("[name=quantity__gte]").fill("10")
    admin_page.locator("[name=quantity__gte]").blur()

    expect(admin_page).to_have_url(re.compile(r"\?quantity__gte=10$"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(1)
    expect(toggle.locator(".badge")).to_have_text("1")
    clear = admin_page.get_by_role("link", name="Clear all filters")
    expect(clear).to_have_attribute("href", "/admin/admin_app/item/")

    clear.click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(2)
    expect(toggle.locator(".badge")).to_have_text("0")
    expect(row).to_be_visible()
    expect(admin_page.locator("[name=quantity__gte]")).to_have_value("")
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


def test_changed_cells_show_in_the_save_bar_until_discarded(admin_page, live_server, kitchen):
    for name in ("Kettle", "Toaster"):
        Item.objects.create(name=name, category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    bar = admin_page.locator("[data-save-bar]")
    quantities = admin_page.locator("#changelist-table [data-editable] input")
    expect(bar).to_be_hidden()

    count = bar.locator("[data-change-count]")
    quantities.nth(0).fill("5")
    quantities.nth(1).fill("7")
    expect(count).to_have_text("2")
    expect(admin_page.locator("#changelist-table td.formwork-dirty")).to_have_count(2)

    quantities.nth(1).fill("3")
    expect(count).to_have_text("1")

    bar.get_by_role("button", name="Discard").click()
    expect(bar).to_be_hidden()
    expect(quantities.nth(0)).to_have_value("3")
    expect(admin_page.locator("#changelist-table td.formwork-dirty")).to_have_count(0)
    assert admin_page.errors == []


def test_list_actions_wait_until_the_changes_are_saved(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    activate = admin_page.locator("#changelist-actions").get_by_role("button", name="Mark selected items as active")
    admin_page.locator("#changelist tbody input[type=checkbox]").click()
    expect(activate).to_be_enabled()

    admin_page.locator("#changelist-table [data-editable] input").fill("5")
    expect(activate).to_be_disabled()

    admin_page.get_by_role("button", name="Save changes").click()
    expect(admin_page.get_by_role("status").filter(has_text="was changed successfully")).to_be_visible()
    item.refresh_from_db()
    assert item.quantity == 5
    assert admin_page.errors == []


def test_other_results_ask_before_they_replace_the_changes(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    url = f"{live_server.url}/admin/admin_app/item/"
    admin_page.goto(url)
    quantity = admin_page.locator("#changelist-table [data-editable] input")
    sort = admin_page.locator("#changelist-table thead a", has_text="Price")
    quantity.fill("5")

    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    with admin_page.expect_event("dialog") as prompt:
        sort.click()
    assert prompt.value.type == "confirm"
    admin_page.wait_for_load_state("networkidle")
    expect(admin_page).to_have_url(url)
    expect(quantity).to_have_value("5")

    admin_page.once("dialog", lambda prompt: prompt.accept())
    sort.click()
    expect(admin_page).to_have_url(re.compile(r"\?o=4$"))
    expect(quantity).to_have_value("3")
    assert admin_page.errors == []


def test_a_long_list_scrolls_its_rows_under_the_header(admin_page, live_server, kitchen):
    Item.objects.bulk_create(Item(name=f"Kettle {i}", category=kitchen) for i in range(40))
    admin_page.set_viewport_size({"width": 1280, "height": 720})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    header = admin_page.locator("#changelist-table thead th", has_text="Name")
    top = header.bounding_box()["y"]

    admin_page.locator("#changelist-scroll").evaluate("(el) => el.scrollBy(0, 400)")

    expect(admin_page.locator("#changelist-footer")).to_be_in_viewport()
    assert admin_page.evaluate("document.documentElement.scrollHeight") <= 720
    assert header.bounding_box()["y"] == top
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


def test_a_category_added_in_the_dialog_is_chosen_in_a_radio_list(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "radio_fields", {"category": VERTICAL})
    Category.objects.create(name="Workshop", slug="workshop")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    field = admin_page.locator('[data-related="admin_app.category"]')
    field.get_by_label("Workshop").check()

    field.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("Garden")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(field.get_by_label("Garden")).to_be_checked()
    expect(field.get_by_label("Workshop")).not_to_be_checked()
    garden = Category.objects.get(name="Garden")
    expect(field.get_by_role("link", name="Change selected category")).to_have_attribute(
        "href", f"/admin/admin_app/category/{garden.pk}/change/"
    )
    admin_page.locator("[name=name]").fill("Spade")
    admin_page.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert Item.objects.get(name="Spade").category == garden
    assert admin_page.errors == []


def test_a_category_added_in_the_dialog_is_chosen_in_a_native_select(admin_page, live_server, kitchen, monkeypatch):
    overrides = {ForeignKey: {"widget": forms.Select}}
    monkeypatch.setattr(site.get_model_admin(Item), "formfield_overrides", overrides)
    item = Item.objects.create(name="Spade", category=Category.objects.create(name="Workshop", slug="workshop"))
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    select = admin_page.locator('[data-related="admin_app.category"] select')
    select.select_option(label="Kitchen")

    admin_page.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("Patio")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    patio = Category.objects.get(name="Patio")
    expect(select).to_have_value(str(patio.pk))
    admin_page.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    item.refresh_from_db()
    assert item.category == patio
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


@action(description="Archive this %(verbose_name)s", location=ActionLocation.CHANGE_FORM)
def archive(modeladmin, request, queryset):
    queryset.update(status=Item.Status.ARCHIVED)
    modeladmin.message_user(request, "Archived.")


def test_change_form_actions_wait_until_the_changes_are_saved(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(type(site.get_model_admin(Item)), "actions", [archive])
    item = Item.objects.create(name="Kettle", category=kitchen)
    url = f"{live_server.url}/admin/admin_app/item/{item.pk}/change/"
    admin_page.goto(url)
    menu = admin_page.get_by_role("button", name="Actions")

    admin_page.locator("[name=name]").fill("Kettle 2")
    expect(menu).to_have_attribute("aria-disabled", "true")
    expect(menu.locator("xpath=..")).to_have_attribute("data-tip", "Save your changes first")
    expect(menu.locator("xpath=..")).to_have_class(re.compile(r"\btooltip\b"))

    admin_page.get_by_role("button", name="Save and continue editing").click()
    expect(admin_page.get_by_role("status").filter(has_text="was changed successfully")).to_be_visible()
    menu.click()
    admin_page.get_by_role("button", name="Archive this item").click()

    expect(admin_page.get_by_role("status").filter(has_text="Archived.")).to_be_visible()
    expect(admin_page).to_have_url(url)
    item.refresh_from_db()
    assert (item.name, item.status) == ("Kettle 2", Item.Status.ARCHIVED)
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
