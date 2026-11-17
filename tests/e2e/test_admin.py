"""E2e tests for the admin's changelist filters, selection, columns and imports, and its inline rows."""

import re

import django_filters
import pytest
from admin_app.admin import ItemAdmin, LowStockFilter, PartInline, TagAdmin
from admin_app.models import Category, Item, Part, Tag
from django import forms
from django.contrib.admin import EmptyFieldListFilter, ShowFacets
from django.core.exceptions import PermissionDenied
from django.db.models import ForeignKey
from django.utils import timezone
from django.utils.html import format_html
from playwright.sync_api import expect

from django_formwork.admin import VERTICAL, ActionLocation, TabularInline, action, site, slot

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


def test_a_page_size_picked_under_the_list_stays_through_a_search(admin_page, live_server, kitchen, monkeypatch):
    item_admin = site.get_model_admin(Item)
    monkeypatch.setattr(item_admin, "list_per_page", 1)
    monkeypatch.setattr(item_admin, "list_per_page_options", (2,))
    for name in ("Kettle", "Toaster", "Kettle lid"):
        Item.objects.create(name=name, category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    rows = admin_page.locator("#changelist tbody tr")
    expect(rows).to_have_count(1)

    admin_page.get_by_label("Rows per page").click()
    admin_page.get_by_role("option", name="2", exact=True).click()
    expect(admin_page).to_have_url(re.compile(r"\?per_page=2$"))
    expect(rows).to_have_count(2)

    admin_page.locator("[data-search] input:not([type=hidden])").fill("kettle")
    expect(admin_page).to_have_url(re.compile(r"\?(?=.*q=kettle)(?=.*per_page=2)"))
    expect(rows).to_have_count(2)
    assert admin_page.errors == []


def test_a_date_filter_preset_filters_the_list(admin_page, live_server, kitchen):
    today = timezone.localdate()
    Item.objects.create(name="Kettle", category=kitchen, released=today)
    Item.objects.create(name="Toaster", category=kitchen, released=today.replace(year=today.year - 1))
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.get_by_role("button", name="More filters").click()
    admin_page.get_by_role("menuitem", name="Released").click()
    admin_page.get_by_role("button", name="This year").click()

    first, after = today.replace(month=1, day=1), today.replace(year=today.year + 1, month=1, day=1)
    expect(admin_page).to_have_url(re.compile(rf"\?released__gte={first}&released__lt={after}$"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(1)
    expect(admin_page.locator("#changelist tbody")).to_contain_text("Kettle")
    assert admin_page.errors == []


def test_a_filter_value_narrows_the_list_until_clear_in_the_menu_resets_it(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", [django_filters.RangeFilter(field_name="quantity")])
    monkeypatch.setattr(site.get_model_admin(Item), "show_facets", ShowFacets.NEVER)
    Item.objects.create(name="Kettle", category=kitchen, quantity=5)
    Item.objects.create(name="Toaster", category=kitchen, quantity=40)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    rows = admin_page.locator("#changelist tbody tr")
    at_least = admin_page.locator("[name=quantity__gte]")
    marked = admin_page.locator("[data-filter=quantity].formwork-dirty")
    options = admin_page.get_by_role("button", name="Filter options")
    clear = admin_page.get_by_role("link", name="Clear all filters")
    options.click()
    expect(clear).to_have_attribute("aria-disabled", "true")

    at_least.fill("10")
    at_least.blur()

    expect(admin_page).to_have_url(re.compile(r"\?quantity__gte=10$"))
    expect(rows).to_have_count(1)
    expect(marked).to_be_visible()
    options.click()
    expect(clear).to_have_attribute("href", "/admin/admin_app/item/")

    clear.click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect(rows).to_have_count(2)
    expect(at_least).to_have_value("")
    expect(marked).to_have_count(0)
    expect(clear).to_be_hidden()
    options.click()
    expect(clear).to_have_attribute("aria-disabled", "true")
    assert admin_page.errors == []


def expect_filters(page, *labels):
    """The filters in the search row, in order."""
    row = page.locator("#changelist-filter-bar [data-filter]:visible")
    expect(row).to_have_text([re.compile(rf"^\s*{label}") for label in labels])


def test_a_filter_picked_from_more_opens_in_the_row_and_stays_while_it_has_a_value(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen, quantity=5)
    Item.objects.create(name="Toaster", category=kitchen, quantity=40)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    more = admin_page.get_by_role("button", name="More filters")
    expect_filters(admin_page, "Status", "Category")
    expect(more.locator("[data-more-count]")).to_have_text("4")

    more.click()
    admin_page.get_by_role("menuitem", name="Stock").click()

    expect(admin_page.locator("#id_stock_wrapper")).to_have_attribute("open", "")
    expect_filters(admin_page, "Status", "Stock")
    expect(more.locator("[data-more-count]")).to_have_text("4")

    admin_page.get_by_role("option", name="Low", exact=True).click()
    expect(admin_page).to_have_url(re.compile(r"\?stock=low$"))
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(1)
    expect_filters(admin_page, "Status", "Stock")

    more.click()
    admin_page.get_by_role("link", name="Clear all filters").click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect_filters(admin_page, "Status", "Category")

    admin_page.go_back()
    expect(admin_page).to_have_url(re.compile(r"\?stock=low$"))
    expect_filters(admin_page, "Status", "Stock")
    assert admin_page.errors == []


@pytest.mark.parametrize("leave", ["pointer", "keyboard"])
def test_an_empty_filter_picked_from_more_stays_in_the_row_while_it_has_the_focus(
    admin_page, live_server, kitchen, leave
):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.get_by_role("button", name="More filters").click()
    admin_page.get_by_role("menuitem", name="Tags").click()
    expect(admin_page.locator("#id_tags__id__exact_wrapper")).to_have_attribute("open", "")
    admin_page.set_viewport_size({"width": 1300, "height": 720})
    admin_page.evaluate("() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))")
    expect_filters(admin_page, "Status", "Tags")

    admin_page.keyboard.press("Escape")
    if leave == "pointer":
        admin_page.locator("h1").click()
    else:
        admin_page.keyboard.press("Tab")

    expect_filters(admin_page, "Status", "Category")
    assert admin_page.errors == []


def test_a_wide_list_shows_three_filters_and_a_narrower_one_shows_those_that_fit(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 1920, "height": 720})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    bar = admin_page.locator("#changelist-filter-bar")
    waiting = admin_page.get_by_role("button", name="More filters").locator("[data-more-count]")
    expect_filters(admin_page, "Status", "Category", "Is featured")
    expect(waiting).to_have_text("3")

    admin_page.set_viewport_size({"width": 1300, "height": 720})
    expect_filters(admin_page, "Status", "Category")
    expect(waiting).to_have_text("4")
    expect(bar).not_to_have_attribute("data-stacked", "")
    assert admin_page.errors == []


@pytest.mark.parametrize(
    ("query", "labels"),
    [
        ("?stock=low", ["Status", "Category", "Stock"]),
        (
            "?status__exact=active&is_featured__exact=1&released__gte=2026-01-01&stock=low",
            ["Status", "Is featured", "Released", "Stock"],
        ),
    ],
)
def test_a_wide_list_shows_every_filter_with_a_value_and_fills_the_row_up_to_three(
    admin_page, live_server, kitchen, query, labels
):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 1920, "height": 720})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{query}")

    expect_filters(admin_page, *labels)
    assert admin_page.errors == []


def test_a_filter_with_a_long_option_keeps_its_width(admin_page, live_server):
    Item.objects.create(name="Kettle", category=Category.objects.create(name="Kitchen and household appliances"))
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    category = admin_page.locator("#changelist-filter-bar [data-filter=category__id__exact]")
    trigger = category.locator("summary")
    expect(trigger).to_be_visible()

    assert trigger.bounding_box()["width"] <= category.bounding_box()["width"]
    assert admin_page.errors == []


def test_a_narrow_list_gives_the_filters_a_row_of_their_own(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 390, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    bar = admin_page.locator("#changelist-filter-bar")
    expect(bar).to_have_attribute("data-stacked", "")
    search = bar.locator("[data-search]").bounding_box()
    below = search["y"] + search["height"]

    assert bar.get_by_role("button", name="More filters").bounding_box()["y"] < below
    assert bar.get_by_role("link", name="Add item").bounding_box()["y"] < below
    assert bar.locator("[data-filter=status__exact]").bounding_box()["y"] >= below
    assert admin_page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert admin_page.errors == []


MANY_FILTERS = [
    "status",
    "category",
    "is_featured",
    "released",
    LowStockFilter,
    "tags",
    "available_from",
    ("website", EmptyFieldListFilter),
    ("notes", EmptyFieldListFilter),
    django_filters.RangeFilter(field_name="quantity"),
    django_filters.RangeFilter(field_name="price"),
]


def test_the_more_menu_finds_a_filter_by_name_and_enter_puts_it_in_the_row(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", MANY_FILTERS)
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    found = admin_page.get_by_role("menu", name="More filters").get_by_role("menuitem")

    admin_page.get_by_role("button", name="More filters").click()
    find = admin_page.get_by_role("searchbox", name="Find a filter")
    expect(find).to_be_focused()
    find.fill("zz")
    expect(found).to_have_count(0)
    expect(admin_page.get_by_text("No filter matches.")).to_be_visible()

    find.fill("pri")
    expect(found).to_have_text(["Price"])
    find.press("Enter")

    expect(admin_page.locator("[name=price__gte]")).to_be_focused()
    expect_filters(admin_page, "Status", "Price")
    assert admin_page.errors == []


def test_a_list_whose_filters_all_fit_keeps_the_counts_switch_behind_an_options_button(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", ["status", "is_featured"])
    Item.objects.create(name="Kettle", category=kitchen, status="active")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    options = admin_page.get_by_role("button", name="Filter options")
    expect(admin_page.get_by_role("button", name="More filters")).to_have_count(0)

    options.click()
    admin_page.get_by_label("Show counts").check()

    expect(admin_page).to_have_url(re.compile(r"\?_facets=True$"))
    expect(options).to_be_visible()
    expect(options.locator("[data-more-count]")).to_be_hidden()
    admin_page.locator("#id_status__exact").click()
    expect(admin_page.get_by_role("option", name="Active")).to_contain_text("1")
    assert admin_page.errors == []


def test_the_filters_fit_the_row_in_the_first_frame(admin_page, live_server, kitchen):
    """A held admin.js keeps the page from DOMContentLoaded, as a slow connection does."""
    Item.objects.create(name="Kettle", category=kitchen)
    held = []

    def hold(route):
        held.append(route)

    admin_page.route("**/formwork_admin/admin.js", hold)
    admin_page.add_init_script(
        """requestAnimationFrame(() => setTimeout(() => {
            const filters = [...document.querySelectorAll("#changelist-filter-bar [data-filter]")];
            window.firstFrame = filters.filter((filter) => filter.checkVisibility()).length;
        }))"""
    )

    admin_page.goto(f"{live_server.url}/admin/admin_app/item/", wait_until="commit")
    admin_page.wait_for_function("window.firstFrame !== undefined")
    first_frame = admin_page.evaluate("window.firstFrame")
    for route in held:
        route.continue_()
    admin_page.wait_for_load_state()

    assert first_frame == 2
    expect_filters(admin_page, "Status", "Category")
    assert admin_page.errors == []


def test_a_list_that_a_link_loads_shows_only_the_filters_that_fit_from_its_first_frame(
    admin_page, live_server, kitchen
):
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/")
    admin_page.evaluate("""() => {
        window.filters = [];
        const sample = () => {
            const filters = [...document.querySelectorAll("#changelist-filter-bar [data-filter]")];
            if (filters.length) window.filters.push(filters.filter((filter) => filter.checkVisibility()).length);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
        window.swapped = new Promise((resolve) => document.addEventListener("htmx:after:swap", resolve, { once: true }));
    }""")

    model_list(admin_page).get_by_role("link", name="Items").click()

    admin_page.evaluate(
        "window.swapped.then(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))"
    )
    expect_filters(admin_page, "Status", "Category")
    assert set(admin_page.evaluate("window.filters")) == {2}
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


def test_a_cell_that_a_script_widens_before_the_page_loads_fits_the_columns_again(admin_page, live_server, kitchen):
    """A script that fills a cell after the table is parsed gets the columns fitted to it on load."""
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 1280, "height": 800})
    url = f"{live_server.url}/admin/admin_app/item/"
    released = admin_page.locator("#changelist-table thead th", has_text="Released")
    admin_page.goto(url)
    expect(released).to_be_visible()
    script = "<script>document.querySelector('#changelist-table > tbody a').textContent = 'K'.repeat(160);</script>"

    def widen(route):
        response = route.fetch()
        route.fulfill(response=response, body=response.text().replace("</body>", f"{script}</body>"))

    admin_page.route(url, widen)
    admin_page.goto(url)

    expect(released).to_be_hidden()
    assert admin_page.errors == []


def test_a_list_that_a_link_loads_shows_only_the_columns_that_fit_from_its_first_frame(
    admin_page, live_server, kitchen
):
    """No frame of the crossfade to the list shows a column that then hides."""
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 480, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/")
    admin_page.evaluate("""() => {
        window.columns = [];
        const sample = () => {
            const cells = document.querySelectorAll("#changelist-table > thead > tr > th");
            if (cells.length) window.columns.push([...cells].filter((cell) => cell.checkVisibility()).length);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
        window.swapped = new Promise((resolve) => document.addEventListener("htmx:after:swap", resolve, { once: true }));
    }""")
    admin_page.locator("label.drawer-button").click()

    model_list(admin_page).get_by_role("link", name="Items").click()

    admin_page.evaluate(
        "window.swapped.then(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))"
    )
    expect(admin_page.locator("#changelist-table thead th", has_text="Released")).to_be_hidden()
    assert len(set(admin_page.evaluate("window.columns"))) == 1
    assert admin_page.errors == []


def test_changed_cells_are_counted_above_the_list_until_discarded(admin_page, live_server, kitchen):
    for name in ("Kettle", "Toaster"):
        Item.objects.create(name=name, category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    bar = admin_page.locator("[data-save-bar]")
    count = bar.locator("[data-change-count]")
    save = bar.get_by_role("button", name="Save changes")
    discard = bar.get_by_role("button", name="Discard")
    quantities = admin_page.locator("#changelist-table [data-editable] input")
    expect(count).to_have_text("0")
    expect(save).to_be_disabled()
    expect(discard).to_be_disabled()

    quantities.nth(0).fill("5")
    quantities.nth(1).fill("7")
    expect(count).to_have_text("2")
    expect(save).to_be_enabled()
    expect(admin_page.locator("#changelist-table td.formwork-dirty")).to_have_count(2)

    quantities.nth(1).fill("3")
    expect(count).to_have_text("1")

    discard.click()
    expect(count).to_have_text("0")
    expect(save).to_be_disabled()
    expect(quantities.nth(0)).to_have_value("3")
    expect(admin_page.locator("#changelist-table td.formwork-dirty")).to_have_count(0)
    assert admin_page.errors == []


def test_list_actions_wait_until_the_changes_are_saved(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    actions = admin_page.locator("#changelist-actions")
    delete = actions.get_by_role("button", name="Delete", exact=True)
    menu = actions.get_by_role("button", name="Actions")
    expect(delete).to_be_disabled()
    expect(menu).to_have_attribute("aria-disabled", "true")
    admin_page.locator("#changelist tbody input[type=checkbox]").click()
    expect(delete).to_be_enabled()
    expect(menu).to_have_attribute("aria-disabled", "false")

    admin_page.locator("#changelist-table [data-editable] input").fill("5")
    expect(delete).to_be_disabled()
    expect(menu).to_have_attribute("aria-disabled", "true")

    admin_page.get_by_role("button", name="Save changes").click()
    expect(admin_page.get_by_role("status").filter(has_text="was changed successfully")).to_be_visible()
    item.refresh_from_db()
    assert item.quantity == 5
    assert admin_page.errors == []


def test_a_list_save_that_failed_saves_after_the_fix(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    quantity = admin_page.locator("#changelist-table [data-editable] input")
    save = admin_page.get_by_role("button", name="Save changes")
    quantity.fill("-1")
    save.click()
    expect(quantity).to_have_attribute("aria-invalid", "true")
    expect(admin_page.locator("[data-change-count]")).to_have_text("1")
    expect(save).to_be_enabled()

    quantity.fill("4")
    save.click()

    expect(admin_page.get_by_role("status").filter(has_text="was changed successfully")).to_be_visible()
    item.refresh_from_db()
    assert item.quantity == 4
    assert admin_page.errors == []


def test_a_list_cell_error_shows_in_a_tooltip_and_keeps_the_row_height(admin_page, live_server, kitchen):
    Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    row = admin_page.locator("#changelist-table tbody tr[data-pk]")
    quantity = row.locator("[data-editable] input")
    height = row.bounding_box()["height"]
    quantity.fill("-1")
    admin_page.get_by_role("button", name="Save changes").click()

    tooltip = admin_page.get_by_role("tooltip")
    expect(quantity).to_be_focused()
    expect(tooltip).to_contain_text("greater than")
    expect(tooltip).to_have_css("opacity", "1")
    assert tooltip.bounding_box()["y"] >= quantity.bounding_box()["y"] + quantity.bounding_box()["height"]
    assert row.bounding_box()["height"] == height

    admin_page.keyboard.press("Escape")
    expect(tooltip).to_be_hidden()
    quantity.hover()
    expect(tooltip).to_have_css("opacity", "1")
    assert admin_page.errors == []


def test_an_editable_list_shows_the_fields_of_the_hovered_row_and_of_changed_cells(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", ["status", "quantity"])
    Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    Item.objects.create(name="Mug", category=kitchen, quantity=5)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    rows = admin_page.locator("#changelist-table tbody tr[data-pk]")
    kettle = rows.filter(has_text="Kettle")
    status = kettle.locator("summary")
    quantity = kettle.locator("[name$=-quantity]")
    no_border = "rgba(0, 0, 0, 0)"
    admin_page.mouse.move(0, 0)
    expect(status).to_have_css("border-top-color", no_border)
    expect(quantity).to_have_css("border-top-color", no_border)

    kettle.get_by_role("link", name="Kettle").hover()
    expect(status).not_to_have_css("border-top-color", no_border)

    quantity.fill("4")
    quantity.blur()
    rows.filter(has_text="Mug").get_by_role("link", name="Mug").hover()
    expect(status).to_have_css("border-top-color", no_border)
    expect(quantity).not_to_have_css("border-top-color", no_border)
    assert admin_page.errors == []


def test_an_editable_value_lines_up_with_its_column_header(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", ["status", "quantity", "is_featured"])
    Item.objects.create(name="Kettle", category=kitchen, quantity=3)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    head = admin_page.locator("#changelist-table thead")
    row = admin_page.locator("#changelist-table tbody tr[data-pk]")
    status = row.locator("summary [x-html=labelHtml] .badge").bounding_box()
    quantity_end = row.locator("[name$=-quantity]").evaluate(
        "el => el.getBoundingClientRect().right - parseFloat(getComputedStyle(el).borderRightWidth) - parseFloat(getComputedStyle(el).paddingRight)"
    )
    featured = row.locator("[name$=-is_featured]").bounding_box()
    status_head = head.get_by_role("link", name="Status").bounding_box()
    quantity_head = head.get_by_role("link", name="Quantity").bounding_box()
    featured_head = head.get_by_role("link", name="Is featured").bounding_box()

    assert status["x"] == pytest.approx(status_head["x"], abs=0.5)
    assert quantity_end == pytest.approx(quantity_head["x"] + quantity_head["width"], abs=0.5)
    assert featured["x"] == pytest.approx(featured_head["x"], abs=0.5)


def test_an_inline_cell_error_shows_in_a_tooltip(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    Part.objects.create(item=item, name="Lid")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    quantity = admin_page.locator("[name=parts-0-quantity]")
    row = admin_page.locator("[data-formset-row=parts-0] tr")
    height = row.bounding_box()["height"]
    quantity.fill("-1")
    admin_page.get_by_role("button", name="Save", exact=True).click()

    expect(quantity).to_have_attribute("aria-invalid", "true")
    tooltip = admin_page.get_by_role("tooltip")
    quantity.hover()
    expect(tooltip).to_contain_text("greater than")
    expect(tooltip).to_have_css("opacity", "1")
    assert row.bounding_box()["height"] == height
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


def test_a_long_list_scrolls_with_the_page_and_its_toolbar_and_header_stick_under_the_top_bar(
    admin_page, live_server, kitchen
):
    Item.objects.bulk_create(Item(name=f"Kettle {i}", category=kitchen) for i in range(40))
    admin_page.set_viewport_size({"width": 1280, "height": 720})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    header = admin_page.locator("#changelist-table thead th", has_text="Name")
    bar = admin_page.locator(".drawer-content > header").bounding_box()

    admin_page.mouse.wheel(0, 600)

    expect(admin_page.locator("#changelist-table tbody tr", has_text="Kettle 0")).not_to_be_in_viewport()
    assert admin_page.evaluate("window.scrollY") > 0
    toolbar = admin_page.locator("#changelist-toolbar").bounding_box()
    assert toolbar["y"] == bar["y"] + bar["height"]
    assert header.bounding_box()["y"] == toolbar["y"] + toolbar["height"]
    assert admin_page.errors == []


def test_a_list_with_all_columns_shown_keeps_its_header_on_top_of_its_rows(admin_page, live_server, kitchen):
    """The table then scrolls sideways in its box, where the header cannot stick to the page."""
    Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 480, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")

    admin_page.locator("#changelist-table [data-col-toggle] button").click()

    expect(admin_page.locator("#changelist-table thead th", has_text="Released")).to_be_visible()
    toolbar = admin_page.locator("#changelist-toolbar").bounding_box()
    header = admin_page.locator("#changelist-table thead th", has_text="Name").bounding_box()
    row = admin_page.locator("#changelist-table tbody tr").bounding_box()
    assert header["y"] == pytest.approx(toolbar["y"] + toolbar["height"], abs=1)
    assert row["y"] == pytest.approx(header["y"] + header["height"], abs=1)
    assert admin_page.errors == []


def rows_slot(**options):
    def rows(self, request, queryset):
        return format_html("<p data-rows>{} rows</p>", queryset.count())

    return slot(**options)(rows)


def test_a_lazy_slot_at_the_bottom_loads_as_it_scrolls_into_view(admin_page, live_server, kitchen, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_bottom", rows_slot(lazy=True))
    Item.objects.bulk_create(Item(name=f"Kettle {i}", category=kitchen) for i in range(40))
    admin_page.set_viewport_size({"width": 1280, "height": 720})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    admin_page.wait_for_load_state("networkidle")
    bottom = admin_page.locator("#changelist-bottom")
    expect(bottom.locator("[data-slot-skeleton]")).to_be_attached()

    bottom.scroll_into_view_if_needed()

    expect(bottom.locator("[data-rows]")).to_have_text("40 rows")
    expect(bottom.locator("[data-slot-skeleton]")).not_to_be_attached()
    assert admin_page.errors == []


def test_a_lazy_slot_loads_again_for_a_search_and_keeps_its_content_meanwhile(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(ItemAdmin, "list_top", rows_slot(lazy=True))
    for name in ("Kettle", "Toaster", "Kettle lid"):
        Item.objects.create(name=name, category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    top = admin_page.locator("#changelist-top")
    expect(top.locator("[data-rows]")).to_have_text("3 rows")
    held = []

    def hold(route):
        held.append(route)

    admin_page.route(re.compile(r"/slots/top/"), hold)

    admin_page.locator("#changelist-table thead a", has_text="Name").click()
    expect(admin_page).to_have_url(re.compile(r"\?o="))
    admin_page.locator("[data-search] input:not([type=hidden])").fill("kettle")
    expect(admin_page.locator("#changelist tbody tr")).to_have_count(2)

    expect(top).to_have_css("opacity", "0.5")
    expect(top.locator("[data-rows]")).to_have_text("3 rows")
    assert len(held) == 1
    held[0].continue_()
    expect(top.locator("[data-rows]")).to_have_text("2 rows")
    expect(top).to_have_css("opacity", "1")
    assert admin_page.errors == []


def test_a_long_list_on_a_phone_keeps_the_selection_and_the_save_in_view(admin_page, live_server, kitchen):
    """A phone scrolls the page past the rows, and the toolbar above them stays under the top bar."""
    Item.objects.bulk_create(Item(name=f"Kettle {i}", category=kitchen, quantity=3) for i in range(40))
    admin_page.set_viewport_size({"width": 390, "height": 700})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    actions = admin_page.locator("#changelist-actions")
    delete = actions.get_by_role("button", name="Delete", exact=True)
    save = admin_page.locator("[data-save-bar]").get_by_role("button", name="Save", exact=True)
    first = admin_page.locator("#changelist-table input[data-index='0']")
    first.check()

    admin_page.mouse.wheel(0, 900)

    expect(first).not_to_be_in_viewport()
    expect(actions).to_contain_text("1 selected")
    expect(delete).to_be_in_viewport(ratio=1)
    expect(delete).to_be_enabled()
    expect(save).to_be_in_viewport(ratio=1)
    assert admin_page.errors == []


def test_ctrl_k_opens_the_navigation_filter_on_a_phone(admin_page, live_server):
    admin_page.set_viewport_size({"width": 390, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/")

    admin_page.keyboard.press("Control+k")
    expect(admin_page.locator("#formwork-admin-nav-filter")).to_be_focused()
    assert admin_page.errors == []


def model_list(page):
    return page.get_by_role("navigation", name="Models").locator("div:has(> ul[data-nav-app])")


def test_a_sidebar_link_changes_the_page_and_leaves_the_sidebar_where_it_was(admin_page, live_server):
    admin_page.set_viewport_size({"width": 1280, "height": 320})
    admin_page.goto(f"{live_server.url}/admin/")
    models = model_list(admin_page)
    models.evaluate("(el) => el.scrollTo(0, el.scrollHeight)")
    top = models.evaluate("(el) => el.scrollTop")
    admin_page.evaluate("window.unloaded = false")

    models.get_by_role("link", name="Items").click()

    expect(admin_page.locator("h1")).to_have_text("Items")
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    expect(admin_page).to_have_title(re.compile(r"^Items"))
    expect(models.locator("[aria-current=page]")).to_have_text("Items")
    assert models.evaluate("(el) => el.scrollTop") == top > 0
    assert admin_page.evaluate("window.unloaded") is False

    admin_page.go_back()
    expect(admin_page.locator("h1")).to_have_text("Dashboard")
    assert models.evaluate("(el) => el.scrollTop") == top
    assert admin_page.errors == []


def test_a_sidebar_link_starts_the_next_list_without_the_last_selection(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    Tag.objects.create(pk=item.pk, name="eco")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    admin_page.locator("#changelist tbody input[type=checkbox]").click()
    expect(admin_page.locator("#changelist-actions")).to_contain_text("1 selected")
    admin_page.evaluate("window.unloaded = false")

    model_list(admin_page).get_by_role("link", name="Tags").click()

    expect(admin_page.locator("#changelist tbody")).to_contain_text("eco")
    expect(admin_page.locator("#changelist tbody input[type=checkbox]")).not_to_be_checked()
    expect(admin_page.locator("#changelist-actions")).to_contain_text("0 selected")
    assert admin_page.evaluate("window.unloaded") is False
    assert admin_page.errors == []


def forbidden(self, request):
    raise PermissionDenied


@pytest.mark.parametrize("change", ["files", "error"])
def test_a_sidebar_link_loads_the_whole_page_when_it_needs_new_files_or_fails(
    admin_page, live_server, monkeypatch, change
):
    """A page with files of its own, or an error page, is not morphed into this one."""
    if change == "files":
        media = forms.Media(js=[forms.Script("formwork/sections.js", type="module")])
        monkeypatch.setattr(TagAdmin, "media", property(lambda self: media))
    else:
        monkeypatch.setattr(TagAdmin, "get_queryset", forbidden)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    admin_page.evaluate("window.unloaded = false")

    model_list(admin_page).get_by_role("link", name="Tags").click()

    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/tag/")
    admin_page.wait_for_function("window.unloaded === undefined", timeout=5000)


def hold(page, url):
    """Holds the responses for url until each held route continues."""
    routes = []

    def keep(route):
        routes.append(route)

    page.route(url, keep)
    return routes


@pytest.mark.parametrize("slow", [False, True], ids=["fast", "slow"])
def test_a_sidebar_link_on_a_phone_closes_the_navigation(admin_page, live_server, slow):
    """The navigation closes at the tap, so a slow page shows its skeleton; the page then takes the focus."""
    admin_page.set_viewport_size({"width": 390, "height": 800})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/")
    admin_page.locator("label.drawer-button").click()
    models = model_list(admin_page)
    routes = hold(admin_page, f"{live_server.url}/admin/admin_app/tag/") if slow else []

    models.get_by_role("link", name="Tags").click()

    if slow:
        expect(models).to_be_hidden()
        expect(admin_page.locator("#content")).to_have_attribute("aria-busy", "true")
    for route in routes:
        route.continue_()
    expect(admin_page.locator("h1")).to_have_text("Tags")
    expect(models).to_be_hidden()
    expect(admin_page.locator("#content")).to_be_focused()
    assert admin_page.errors == []


def test_the_sidebar_shows_the_current_model_on_a_page_load(admin_page, live_server):
    admin_page.set_viewport_size({"width": 1280, "height": 320})

    admin_page.goto(f"{live_server.url}/admin/admin_app/tag/")

    expect(model_list(admin_page).locator("[aria-current=page]")).to_be_in_viewport(ratio=1)
    assert admin_page.errors == []


SKELETON_PAGES = {
    "list": ("/admin/", '[data-nav-app] a[href="/admin/admin_app/item/"]', "", "Items"),
    "change": ("/admin/admin_app/item/", "#changelist tbody a", "{pk}/change/", ""),
    "add": ("/admin/admin_app/item/", '#content a[href="/admin/admin_app/item/add/"]', "add/", ""),
}


@pytest.mark.parametrize("kind", SKELETON_PAGES)
def test_a_slow_page_shows_its_skeleton_until_it_arrives(admin_page, live_server, kitchen, kind):
    start, link, target, heading = SKELETON_PAGES[kind]
    item = Item.objects.create(name="Kettle", category=kitchen)
    url = f"{live_server.url}/admin/admin_app/item/{target.format(pk=item.pk)}"
    admin_page.goto(f"{live_server.url}{start}")
    routes = hold(admin_page, url)
    content = admin_page.locator("#content")

    admin_page.locator(link).click()

    expect(content).to_have_attribute("aria-busy", "true")
    expect(content.locator("h1")).to_have_text(heading)
    expect(content.locator("[data-skeleton-icon] .icon")).to_be_visible()
    expect(model_list(admin_page).locator("[aria-current=page]")).to_have_text("Items")
    for route in routes:
        route.continue_()
    expect(admin_page).to_have_url(url)
    expect(content.locator("[data-skeleton-icon]")).to_have_count(0)
    expect(content).not_to_have_attribute("aria-busy", "true")
    assert admin_page.errors == []


def test_a_link_under_the_pointer_loads_its_page_before_the_click(admin_page, live_server):
    """The click takes the loaded page, and no skeleton shows, then or later."""
    url = f"{live_server.url}/admin/admin_app/tag/"
    admin_page.goto(f"{live_server.url}/admin/")
    requests = []
    admin_page.on("request", lambda request: requests.append(request) if request.url == url else None)
    link = model_list(admin_page).get_by_role("link", name="Tags")
    with admin_page.expect_response(url):
        link.hover()
    admin_page.evaluate(
        "new MutationObserver(() => { window.busy = true }).observe(document.getElementById('content'), {attributeFilter: ['aria-busy']})"
    )

    link.click()

    expect(admin_page.locator("h1")).to_have_text("Tags")
    admin_page.wait_for_timeout(300)
    assert len(requests) == 1
    assert admin_page.evaluate("window.busy") is None
    assert admin_page.errors == []


def test_a_link_that_a_form_with_changes_holds_back_leaves_the_sidebar(admin_page, live_server, kitchen):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    admin_page.locator("[name=name]").fill("Kettle")
    models = model_list(admin_page)

    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    models.get_by_role("link", name="Tags").click()

    expect(models.locator("[aria-current=page]")).to_have_text("Items")
    expect(admin_page.locator("[name=name]")).to_have_value("Kettle")
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
    field = admin_page.locator("#id_category_field")

    field.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    expect(dialog.locator("[name=name]")).to_be_focused()
    dialog.locator("[name=name]").fill("Garden")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    garden = Category.objects.get(name="Garden")
    expect(field.locator("summary")).to_match_aria_snapshot("- text: Garden")
    expect(field.get_by_role("link", name="Edit selected category")).to_have_attribute(
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
    field = admin_page.locator("#id_category_field")
    field.get_by_label("Workshop").check()

    field.get_by_role("link", name="Add another category").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("Garden")
    dialog.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(field.get_by_label("Garden")).to_be_checked()
    expect(field.get_by_label("Workshop")).not_to_be_checked()
    garden = Category.objects.get(name="Garden")
    expect(field.get_by_role("link", name="Edit selected category")).to_have_attribute(
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
    select = admin_page.locator("#id_category_field select")
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


def test_a_category_looked_up_in_the_dialog_is_chosen_and_saved(admin_page, live_server, kitchen, monkeypatch):
    """The dialog's list still picks after its search morphed the rows."""
    monkeypatch.setattr(site.get_model_admin(Item), "raw_id_fields", ["category"])
    garden = Category.objects.create(name="Garden", slug="garden")
    item = Item.objects.create(name="Spade", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    field = admin_page.locator("#id_category_field")

    field.get_by_role("link", name="Look up category").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[data-search] input:not([type=hidden])").fill("gard")
    expect(dialog.locator("#changelist tbody tr")).to_have_count(1)
    dialog.get_by_role("link", name="Garden").click()

    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(field.locator("summary")).to_match_aria_snapshot("- text: Garden")
    admin_page.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    item.refresh_from_db()
    assert item.category == garden
    assert admin_page.errors == []


def test_a_row_added_in_the_dialog_replaces_the_empty_list(admin_page, live_server):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    field = admin_page.locator("#id_category_field")

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
    field = admin_page.locator("#id_tags_field")

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

    group.locator("[data-formset-row=items-0]").get_by_role("link", name="Add another tag").click()
    dialog = related_dialog(admin_page)
    dialog.locator("[name=name]").fill("eco")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page.locator("dialog")).to_have_count(0)
    expect(group.locator("[data-formset-row=items-0] [data-related] summary")).to_match_aria_snapshot("- text: eco")
    add.click()
    group.locator("[name=items-1-name]").fill("Toaster")
    tags = group.locator("[data-formset-row=items-1] [data-related]")
    tags.locator("summary").click()
    tags.get_by_role("option", name="eco").click()
    admin_page.get_by_role("button", name="Save", exact=True).click()

    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/category/")
    assert sorted(Item.objects.filter(tags__name="eco").values_list("name", flat=True)) == ["Kettle", "Toaster"]
    assert admin_page.errors == []


class SlugInline(TabularInline):
    model = Item
    fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    extra = 0


def test_inline_rows_fill_their_own_slug_and_a_saved_row_keeps_its_slug(admin_page, live_server, kitchen, monkeypatch):
    """The third row moves up after the second leaves, and still fills its slug."""
    monkeypatch.setattr(site.get_model_admin(Category), "inlines", [SlugInline])
    Item.objects.create(name="Kettle", slug="kettle-classic", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/category/{kitchen.pk}/change/")
    group = admin_page.locator("#items-group")
    add = group.get_by_role("button", name=re.compile("Add another item"))

    group.locator("[name=items-0-name]").fill("Kettle Pro")
    add.click()
    add.click()
    group.locator("[name=items-1-name]").fill("Tea Pot")
    group.locator("[data-formset-row=items-1]").get_by_role("button", name="Remove").click()
    group.locator("[name=items-1-name]").fill("Mug Set")

    expect(group.locator("[name=items-0-slug]")).to_have_value("kettle-classic")
    expect(group.locator("[name=items-1-slug]")).to_have_value("mug-set")
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
    field = admin_page.locator("#id_category_field")
    field.locator("summary").click()
    field.get_by_role("option", name="Kitchen").click()

    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    with admin_page.expect_event("dialog") as prompt:
        admin_page.get_by_label("Breadcrumbs").get_by_role("link", name="Items").click()
    assert prompt.value.type == "confirm"
    expect(admin_page).to_have_url(url)
    assert admin_page.errors == []


def test_leaving_the_form_without_a_change_asks_nothing(admin_page, live_server, kitchen):
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/add/")
    prompts = []
    admin_page.on("dialog", lambda prompt: (prompts.append(prompt.type), prompt.dismiss()))
    field = admin_page.locator("#id_category_field")
    field.locator("summary").click()
    admin_page.keyboard.press("Escape")

    admin_page.get_by_label("Breadcrumbs").get_by_role("link", name="Items").click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert prompts == []
    assert admin_page.errors == []


@pytest.mark.parametrize("featured", [True, False])
def test_a_changed_switch_takes_the_color_of_a_changed_text_field(admin_page, live_server, kitchen, featured):
    """A switch turned off is marked as well as one turned on."""
    item = Item.objects.create(name="Kettle", category=kitchen, is_featured=featured)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    name = admin_page.locator("[name=name]")
    switch = admin_page.locator("[name=is_featured]")
    rest = switch.evaluate("el => getComputedStyle(el).borderColor")

    name.fill("Kettle 2")
    switch.click()

    expect(switch.locator("xpath=ancestor::fieldset[1]")).to_have_class(re.compile(r"\bformwork-dirty\b"))
    admin_page.wait_for_function(
        "([a, b]) => getComputedStyle(a).borderColor === getComputedStyle(b).borderColor",
        arg=[switch.element_handle(), name.element_handle()],
    )
    assert switch.evaluate("el => getComputedStyle(el).borderColor") != rest
    assert admin_page.errors == []


def test_a_switch_put_back_after_a_failed_save_loses_its_mark(admin_page, live_server, kitchen):
    """The server sends what the switch held at first, so the page sees the change undone."""
    item = Item.objects.create(name="Kettle", category=kitchen, is_featured=False)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    switch = admin_page.locator("[name=is_featured]")
    field = switch.locator("xpath=ancestor::fieldset[1]")
    marked = re.compile(r"\bformwork-dirty-option\b")
    switch.click()
    admin_page.locator("[name=quantity]").fill("-1")
    admin_page.get_by_role("button", name="Save", exact=True).click()
    expect(admin_page.locator("[name=quantity]")).to_have_attribute("aria-invalid", "true")
    expect(switch).to_have_class(marked)

    switch.click()

    expect(switch).not_to_have_class(marked)
    expect(field).not_to_have_class(re.compile(r"\bformwork-dirty\b"))
    assert admin_page.errors == []


def test_the_save_bar_stays_in_view_while_the_form_has_changes(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    admin_page.set_viewport_size({"width": 1280, "height": 480})
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    bar = admin_page.locator("[data-save-bar]")
    name = admin_page.locator("[name=name]")
    expect(bar).not_to_be_in_viewport()

    name.fill("Kettle 2")
    expect(bar).to_be_in_viewport()
    expect(bar.locator("[data-change-count]")).to_have_text("1")

    name.fill("Kettle")
    expect(bar).not_to_be_in_viewport()

    name.fill("Kettle 2")
    bar.get_by_role("button", name="Discard").click()
    expect(name).to_have_value("Kettle")
    expect(bar).not_to_be_in_viewport()
    prompts = []
    admin_page.on("dialog", lambda prompt: (prompts.append(prompt.type), prompt.dismiss()))
    admin_page.get_by_label("Breadcrumbs").get_by_role("link", name="Items").click()
    expect(admin_page).to_have_url(f"{live_server.url}/admin/admin_app/item/")
    assert prompts == []
    assert admin_page.errors == []


def test_a_way_to_save_from_the_menu_comes_first_next_time_but_not_from_the_shortcut(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    main = admin_page.locator("[data-save]")
    name = admin_page.locator("[name=name]")

    name.fill("Kettle 2")
    with admin_page.expect_navigation():
        admin_page.keyboard.press("ControlOrMeta+s")
    expect(name).to_have_value("Kettle 2")
    expect(main).to_have_attribute("name", "_save")

    name.fill("Kettle 3")
    admin_page.get_by_role("button", name="More ways to save").click()
    with admin_page.expect_navigation():
        admin_page.get_by_role("menuitem", name="Save and continue editing").click()
    expect(main).to_have_attribute("name", "_continue")
    expect(main).to_have_text("Save and continue editing")
    item.refresh_from_db()
    assert item.name == "Kettle 3"
    assert admin_page.errors == []


def test_an_inline_row_marked_for_deletion_counts_as_a_change(admin_page, live_server, kitchen):
    item = Item.objects.create(name="Kettle", category=kitchen)
    Part.objects.create(item=item, name="Lid")
    admin_page.goto(f"{live_server.url}/admin/admin_app/item/{item.pk}/change/")
    count = admin_page.locator("[data-save-bar] [data-change-count]")

    admin_page.locator("[name=parts-0-DELETE]").check(force=True)

    expect(count).to_have_text("1")
    assert admin_page.errors == []


def test_another_inline_page_asks_before_it_drops_the_changes_on_this_one(
    admin_page, live_server, kitchen, monkeypatch
):
    monkeypatch.setattr(PartInline, "per_page", 2)
    item = Item.objects.create(name="Kettle", category=kitchen)
    for name in ["Lid", "Handle", "Spout"]:
        Part.objects.create(item=item, name=name)
    url = f"{live_server.url}/admin/admin_app/item/{item.pk}/change/"
    admin_page.goto(url)
    first = admin_page.locator("[name=parts-0-name]")
    count = admin_page.locator("[data-save-bar] [data-change-count]")
    first.fill("Cap")

    admin_page.once("dialog", lambda prompt: prompt.dismiss())
    with admin_page.expect_event("dialog"):
        admin_page.locator("#parts-page-next").click()
    expect(admin_page).to_have_url(url)
    expect(first).to_have_value("Cap")

    admin_page.once("dialog", lambda prompt: prompt.accept())
    admin_page.locator("#parts-page-next").click()
    expect(admin_page).to_have_url(f"{url}?parts-page=2")
    expect(first).to_have_value("Spout")
    expect(admin_page.locator("#parts-page-2")).to_be_focused()
    expect(count).to_have_text("0")

    admin_page.locator("#parts-page-prev").click()
    expect(admin_page).to_have_url(url)
    expect(first).to_have_value("Lid")
    assert admin_page.errors == []


@pytest.fixture
def paged_kettle(live_server, kitchen, monkeypatch):
    monkeypatch.setattr(PartInline, "per_page", 2)
    monkeypatch.setattr(PartInline, "extra", 0)
    item = Item.objects.create(name="Kettle", category=kitchen)
    for name in ["Lid", "Handle", "Spout"]:
        Part.objects.create(item=item, name=name)
    return f"{live_server.url}/admin/admin_app/item/{item.pk}/change/"


def test_inline_pager_keeps_its_place_next_to_a_shorter_page(admin_page, paged_kettle):
    admin_page.set_viewport_size({"width": 1280, "height": 400})
    admin_page.goto(paged_kettle)
    pager = admin_page.locator("#parts-group [data-inline-pages]")
    first = admin_page.locator("[name=parts-0-name]")
    pager.evaluate("pager => pager.scrollIntoView({block: 'end'})")
    top = pager.bounding_box()["y"]

    admin_page.locator("#parts-page-next").click()
    expect(first).to_have_value("Spout")
    assert pager.bounding_box()["y"] == pytest.approx(top, abs=1)

    admin_page.locator("#parts-page-prev").click()
    expect(first).to_have_value("Lid")
    assert pager.bounding_box()["y"] == pytest.approx(top, abs=1)
    assert admin_page.errors == []


def test_another_inline_page_adds_after_its_own_rows_and_discard_stays_on_it(admin_page, paged_kettle):
    admin_page.goto(paged_kettle)
    admin_page.locator("#parts-page-next").click()
    expect(admin_page.locator("[name=parts-0-name]")).to_have_value("Spout")

    admin_page.locator("#parts-group").get_by_role("button", name="Add another").click()
    added = admin_page.locator("[name=parts-1-name]")
    added.fill("Base")
    admin_page.locator("[data-discard]").click()

    expect(added).to_have_count(0)
    expect(admin_page).to_have_url(f"{paged_kettle}?parts-page=2")
    expect(admin_page.locator("[name=parts-0-name]")).to_have_value("Spout")
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
    tip = menu.locator("xpath=ancestor::*[@data-tip][1]")
    expect(tip).to_have_attribute("data-tip", "Save your changes first")
    expect(tip).to_have_class(re.compile(r"\btooltip\b"))

    admin_page.keyboard.press("ControlOrMeta+s")
    expect(admin_page.get_by_role("status").filter(has_text="was changed successfully")).to_be_visible()
    menu.click()
    admin_page.get_by_role("menuitem", name="Archive this item").click()

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
    group.locator(f"[data-formset-row=parts-{initial}]").get_by_role("button", name="Remove").click()
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
