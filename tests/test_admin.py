"""Tests for django_formwork.admin, driven through the demo app's admin pages."""

from datetime import date
from types import SimpleNamespace

import django_filters
import pytest
from admin_app.admin import ItemAdmin, LowStockFilter
from admin_app.models import Category, Item, Part, Tag
from bs4 import BeautifulSoup
from django.contrib.admin import EmptyFieldListFilter, RelatedOnlyFieldListFilter
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import Permission
from django.core import checks
from django.urls import reverse

from django_formwork import admin
from django_formwork.admin import site
from django_formwork.admin.checks import check_model_admin
from django_formwork.admin.info import describe_fields, describe_search, describe_table
from django_formwork.admin.widgets import RELATION_SEARCH_KEY

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def admin_urls(settings):
    settings.ROOT_URLCONF = "admin_app.urls"


def url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


def management(prefix, total=0, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def item_data(category, **fields):
    return {
        "name": "Gamma desk",
        "slug": "gamma-desk",
        "category": str(category.pk),
        "status": "draft",
        "price": "10.00",
        "quantity": "3",
        "released": "",
        "website": "",
        "notes": "",
        "data": "{}",
        **management("parts"),
        **management("reviews"),
        **fields,
    }


@pytest.fixture
def catalog():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    office = Category.objects.create(name="Office", slug="office")
    sale = Tag.objects.create(name="sale")
    alpha = Item.objects.create(
        name="Alpha kettle",
        category=kitchen,
        status=Item.Status.ARCHIVED,
        is_featured=True,
        quantity=0,
        released=date(2026, 1, 10),
    )
    alpha.tags.add(sale)
    beta = Item.objects.create(
        name="Beta lamp", category=office, status=Item.Status.DRAFT, quantity=50, website="https://example.com"
    )
    lid = Part.objects.create(item=alpha, name="Lid", quantity=1)
    return SimpleNamespace(kitchen=kitchen, office=office, sale=sale, alpha=alpha, beta=beta, lid=lid)


@pytest.fixture
def staff_client(client, django_user_model):
    def login(*codenames):
        user = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        client.force_login(user)
        return client

    return login


@pytest.mark.parametrize("model", list(site._registry), ids=lambda model: model._meta.label)
def test_admin_pages_render(admin_client, catalog, model):
    obj = model.objects.first()
    for view, args in [
        ("changelist", ()),
        ("add", ()),
        ("change", (obj.pk,)),
        ("history", (obj.pk,)),
        ("delete", (obj.pk,)),
    ]:
        assert admin_client.get(url(model, view, *args)).status_code == 200, view


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [("index", {}), ("app_list", {"app_label": "admin_app"}), ("password_change", {}), ("password_change_done", {})],
)
def test_site_pages_render(admin_client, name, kwargs):
    assert admin_client.get(reverse(f"admin:{name}", kwargs=kwargs)).status_code == 200


def test_anonymous_request_redirects_to_login(client):
    response = client.get(url(Item, "changelist"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


def test_anonymous_htmx_request_sends_the_browser_to_login(client):
    response = client.get(url(Item, "changelist"), headers={"HX-Request": "true"})

    assert response.status_code == 204
    assert response["HX-Redirect"].startswith(reverse("admin:login"))


@pytest.mark.parametrize(("is_staff", "admitted"), [(True, True), (False, False)])
def test_login_admits_staff_only(client, django_user_model, is_staff, admitted):
    django_user_model.objects.create_user("ada", password="pw-12345", is_staff=is_staff)

    client.post(reverse("admin:login"), {"username": "ada", "password": "pw-12345"})

    assert (client.get(reverse("admin:index")).status_code == 200) is admitted


def test_logout_ends_the_session(admin_client):
    assert admin_client.post(reverse("admin:logout")).status_code == 200
    assert admin_client.get(reverse("admin:index")).status_code == 302


def test_login_page_redirects_a_signed_in_user(admin_client):
    response = admin_client.get(reverse("admin:login"))

    assert response.status_code == 302
    assert response["Location"] == reverse("admin:index")


@pytest.mark.parametrize(
    "params",
    [
        lambda c: {"q": "kettle"},
        lambda c: {"status": "archived"},
        lambda c: {"is_featured": "true"},
        lambda c: {"category": c.kitchen.pk},
        lambda c: {"tags": c.sale.pk},
        lambda c: {"stock": "out"},
        lambda c: {"released_0": "2026-01-01", "released_1": "2026-01-31"},
    ],
    ids=["search", "choices", "boolean", "foreign_key", "many_to_many", "simple_list_filter", "date_range"],
)
def test_changelist_filters_rows(admin_client, catalog, params):
    response = admin_client.get(url(Item, "changelist"), params(catalog))

    assert response.status_code == 200
    assert b"Alpha kettle" in response.content
    assert b"Beta lamp" not in response.content


@pytest.mark.parametrize(
    ("list_filter", "params"),
    [
        ([("website", EmptyFieldListFilter)], lambda c: {"website__isempty": "true"}),
        ([("category", RelatedOnlyFieldListFilter)], lambda c: {"category": c.kitchen.pk}),
    ],
    ids=["empty_field", "related_only"],
)
def test_changelist_accepts_django_list_filter_tuples(admin_client, catalog, monkeypatch, list_filter, params):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", list_filter)

    response = admin_client.get(url(Item, "changelist"), params(catalog))

    assert b"Alpha kettle" in response.content
    assert b"Beta lamp" not in response.content


def test_declared_range_filter_reads_min_and_max(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(
        site.get_model_admin(Item), "list_filter", [django_filters.RangeFilter(field_name="quantity", label="Stock")]
    )

    response = admin_client.get(url(Item, "changelist"), {"quantity_min": "10"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert b"Beta lamp" in response.content
    assert b"Alpha kettle" not in response.content
    assert soup.find("input", attrs={"name": "quantity_min"})["value"] == "10"
    assert soup.find("input", attrs={"name": "quantity_max"}) is not None
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.parametrize(
    ("params", "shown"),
    [({}, False), ({"q": "kettle"}, False), ({"status": "archived"}, True)],
    ids=["unfiltered", "search_only", "filtered"],
)
def test_filter_row_starts_open_while_a_filter_is_active(admin_client, catalog, params, shown):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    row = soup.find(id="changelist-filter-row")
    assert ("display: none" not in row.get("style", "")) is shown


def test_clear_all_filters_keeps_the_search(admin_client, catalog):
    soup = BeautifulSoup(
        admin_client.get(url(Item, "changelist"), {"status": "archived", "q": "kettle"}).content, "html.parser"
    )

    assert soup.find(id="changelist-filter-count").get_text(strip=True) == "1"
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == "?q=kettle"


def test_clear_all_filters_is_dimmed_while_only_a_search_is_active(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), {"q": "kettle"}).content, "html.parser")

    assert soup.select_one("[data-clear-filters]") is None
    assert soup.select_one("#changelist-filter-row a[aria-disabled=true]").get("href") is None


def test_filters_keep_the_list_filter_order(admin_client, catalog, monkeypatch):
    list_filter = [LowStockFilter, "status", django_filters.RangeFilter(field_name="quantity"), "category"]
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", list_filter)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    fieldsets = soup.select("#changelist-filter-row fieldset")
    assert [fieldset["id"] for fieldset in fieldsets] == [
        "id_stock_field",
        "id_status_field",
        "id_quantity_field",
        "id_category_field",
    ]


@pytest.mark.parametrize(("icon", "shown"), [("package", "icon-package"), (None, "icon-star")])
def test_navigation_shows_the_model_icon_or_a_placeholder_shape(admin_client, catalog, monkeypatch, icon, shown):
    monkeypatch.setattr(site.get_model_admin(Item), "icon", icon)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one(f'a[aria-current="page"] .{shown}') is not None


def test_placeholder_shapes_differ_within_an_app_and_survive_a_restart(monkeypatch):
    for model in (Category, Tag, Item):
        monkeypatch.setattr(site.get_model_admin(model), "icon", None)

    shapes = {model._meta.label_lower: site.get_model_admin(model).get_icon() for model in (Category, Tag, Item)}

    assert shapes == {"admin_app.category": "circle", "admin_app.tag": "square", "admin_app.item": "star"}


@pytest.mark.parametrize(("orientation", "inline"), [(admin.HORIZONTAL, True), (admin.VERTICAL, False)])
def test_radio_fields_orientation_marks_the_choice_list(admin_client, catalog, monkeypatch, orientation, inline):
    monkeypatch.setattr(site.get_model_admin(Item), "radio_fields", {"status": orientation, "category": orientation})

    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")

    for name in ["status", "category"]:
        wrapper = soup.find("input", attrs={"name": name, "type": "radio"}).find_parent("div").find_parent("div")
        assert ("flex-row" in wrapper.get("class", [])) is inline


@pytest.mark.parametrize(("order", "first"), [("quantity", b"Alpha kettle"), ("-quantity", b"Beta lamp")])
def test_changelist_sorts_by_column(admin_client, catalog, order, first):
    content = admin_client.get(url(Item, "changelist"), {"o": order}).content

    second = ({b"Alpha kettle", b"Beta lamp"} - {first}).pop()
    assert content.index(first) < content.index(second)


def test_changelist_pages_rows(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_per_page", 1)

    content = admin_client.get(url(Item, "changelist"), {"p": 2}).content

    assert b"Alpha kettle" in content
    assert b"Beta lamp" not in content


def test_changelist_wraps_only_columns_with_long_text(admin_client, catalog):
    catalog.beta.name = "Beta lamp with a shade long enough for a second line"
    catalog.beta.save()

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    _checkbox, name, category, *_rest = soup.select(f"tr[data-pk='{catalog.alpha.pk}'] > td")
    assert "min-w-48" in name["class"]
    assert "whitespace-nowrap" in category["class"]


@pytest.mark.parametrize(("model", "toggle"), [(Item, True), (Tag, False)])
def test_changelist_adds_the_column_toggle_to_lists_of_several_columns(admin_client, catalog, model, toggle):
    soup = BeautifulSoup(admin_client.get(url(model, "changelist")).content, "html.parser")

    rows = soup.select("#changelist-table > :is(thead, tbody) > tr")
    assert [row.find_all(recursive=False)[-1].has_attr("data-col-toggle") for row in rows] == [toggle] * len(rows)
    assert soup.find(id="changelist-scroll").has_attr("data-columns") is toggle


@pytest.mark.parametrize(
    ("links", "pinned"), [(("name",), ["Name"]), (("price",), ["Name", "Price"]), (None, ["Name"])]
)
def test_changelist_pins_the_first_and_the_link_columns(admin_client, catalog, monkeypatch, links, pinned):
    monkeypatch.setattr(site.get_model_admin(Item), "list_display_links", links)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    header = soup.select("#changelist-table > thead > tr > th[data-col]")
    assert [th.get_text(strip=True) for th in header if th.has_attr("data-pin")] == pinned


def test_empty_changelist_row_spans_every_column(admin_client):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    header = soup.select("#changelist-table > thead > tr > th")
    assert int(soup.select_one("#changelist-table tr[data-empty] > td")["colspan"]) == len(header)


def test_content_morph_gets_the_page_content_only(admin_client, catalog):
    response = admin_client.get(
        url(Item, "changelist"), {"q": "kettle"}, headers={"HX-Request": "true", "HX-Target": "main#content"}
    )
    soup = BeautifulSoup(response.content, "html.parser")

    assert b"Alpha kettle" in response.content
    assert b"<html" not in response.content
    assert soup.find("aside") is None
    assert soup.find(id="changelist-filters").find("input", attrs={"name": "q"})["value"] == "kettle"


def test_method_action_runs_on_the_selected_rows(admin_client, catalog):
    admin_client.post(url(Item, "changelist"), {"action": "mark_active", "_selected_action": [catalog.beta.pk]})

    assert Item.objects.get(pk=catalog.beta.pk).status == Item.Status.ACTIVE
    assert Item.objects.get(pk=catalog.alpha.pk).status == Item.Status.ARCHIVED


def test_action_without_selection_changes_nothing(admin_client, catalog):
    response = admin_client.post(url(Item, "changelist"), {"action": "mark_active"})

    assert response.status_code == 302
    assert not Item.objects.filter(status=Item.Status.ACTIVE).exists()


def test_action_across_all_rows_keeps_the_filters(admin_client, catalog):
    admin_client.post(f"{url(Item, 'changelist')}?q=kettle", {"action": "mark_active", "select_across": "1"})

    assert Item.objects.get(pk=catalog.alpha.pk).status == Item.Status.ACTIVE
    assert Item.objects.get(pk=catalog.beta.pk).status == Item.Status.DRAFT


def test_delete_selected_confirms_before_deleting(admin_client, catalog):
    data = {"action": "delete_selected", "_selected_action": [catalog.beta.pk]}

    assert admin_client.post(url(Item, "changelist"), data).status_code == 200
    assert Item.objects.filter(pk=catalog.beta.pk).exists()

    admin_client.post(url(Item, "changelist"), {**data, "post": "yes"})

    assert not Item.objects.filter(pk=catalog.beta.pk).exists()
    assert LogEntry.objects.filter(action_flag=DELETION, object_id=str(catalog.beta.pk)).exists()


def test_delete_selected_keeps_protected_rows(admin_client, catalog):
    data = {"action": "delete_selected", "_selected_action": [catalog.kitchen.pk], "post": "yes"}

    response = admin_client.post(url(Category, "changelist"), data)

    assert response.status_code == 200
    assert Category.objects.filter(pk=catalog.kitchen.pk).exists()


def test_list_editable_saves_the_changed_rows(admin_client, catalog):
    data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "77", "_save": "1"}

    response = admin_client.post(url(Item, "changelist"), data)

    assert response.status_code == 302
    assert Item.objects.get(pk=catalog.alpha.pk).quantity == 77
    assert LogEntry.objects.filter(action_flag=CHANGE, object_id=str(catalog.alpha.pk)).exists()


def test_list_editable_invalid_value_saves_nothing(admin_client, catalog):
    data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "-1", "_save": "1"}

    response = admin_client.post(url(Item, "changelist"), data)

    assert response.status_code == 200
    assert Item.objects.get(pk=catalog.alpha.pk).quantity == 0


def test_list_editable_error_marks_its_cell(admin_client, catalog):
    data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "-1", "_save": "1"}

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")

    assert [cell.find("input")["name"] for cell in soup.select("#changelist-table td[data-invalid]")] == [
        "form-0-quantity"
    ]


@pytest.mark.parametrize(
    ("button", "target"),
    [
        ("_save", lambda item: url(Item, "changelist")),
        ("_continue", lambda item: url(Item, "change", item.pk)),
        ("_addanother", lambda item: url(Item, "add")),
    ],
)
def test_add_redirects_per_submit_button(admin_client, catalog, button, target):
    response = admin_client.post(url(Item, "add"), {**item_data(catalog.office), button: "1"})

    item = Item.objects.get(name="Gamma desk")
    assert response.status_code == 302
    assert response["Location"] == target(item)
    assert LogEntry.objects.filter(action_flag=ADDITION, object_id=str(item.pk)).exists()


def test_saved_message_links_to_the_object(admin_client, catalog):
    response = admin_client.post(url(Item, "add"), {**item_data(catalog.office), "_continue": "1"}, follow=True)

    toast = BeautifulSoup(response.content, "html.parser").select_one("#formwork-admin-toasts [role=status]")
    item = Item.objects.get(name="Gamma desk")
    assert toast.select_one("a")["href"] == url(Item, "change", item.pk)
    assert "<a" not in toast.get_text()


def test_content_morph_brings_pending_messages_out_of_band(admin_client, catalog):
    admin_client.post(url(Item, "changelist"), {"action": "mark_active"})

    response = admin_client.get(url(Item, "changelist"), headers={"HX-Request": "true", "HX-Target": "main#content"})

    toasts = BeautifulSoup(response.content, "html.parser").select_one("#formwork-admin-toasts")
    assert toasts["hx-swap-oob"] == "beforeend"
    assert toasts.select_one("[role=alert]") is not None


def test_add_saves_inline_rows(admin_client, catalog):
    data = item_data(catalog.office, **management("parts", total=1), **{"parts-0-name": "Leg", "parts-0-quantity": "4"})

    admin_client.post(url(Item, "add"), data)

    assert list(Part.objects.filter(item__name="Gamma desk").values_list("name", "quantity")) == [("Leg", 4)]


def test_change_deletes_marked_inline_rows(admin_client, catalog):
    alpha = catalog.alpha
    data = item_data(
        catalog.kitchen,
        name=alpha.name,
        status=alpha.status,
        quantity="0",
        **management("parts", total=1, initial=1),
        **{
            "parts-0-id": catalog.lid.pk,
            "parts-0-item": alpha.pk,
            "parts-0-name": "Lid",
            "parts-0-quantity": "1",
            "parts-0-DELETE": "on",
        },
    )

    response = admin_client.post(url(Item, "change", alpha.pk), data)

    assert response.status_code == 302
    assert not Part.objects.filter(pk=catalog.lid.pk).exists()


def test_change_with_errors_saves_nothing(admin_client, catalog):
    response = admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, name=""))

    assert response.status_code == 200
    assert Item.objects.get(pk=catalog.beta.pk).name == "Beta lamp"


def test_toggle_next_to_labelled_fields_moves_to_their_input_line(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert "sm:pt-9" in soup.select_one("[data-field='is_featured']")["class"]
    assert "sm:pt-9" not in soup.select_one("[data-field='released']")["class"]


def test_submit_row_follows_djangos_order(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    row = soup.select_one("[data-save]").parent
    assert [button["name"] for button in row.find_all("button", recursive=False)] == [
        "_save",
        "_addanother",
        "_continue",
    ]
    assert row.find_all("a", recursive=False)[-1]["href"] == url(Item, "delete", catalog.alpha.pk)


def test_save_as_replaces_save_and_add_another(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "save_as", True)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    row = soup.select_one("[data-save]").parent
    assert [button["name"] for button in row.find_all("button", recursive=False)] == [
        "_save",
        "_saveasnew",
        "_continue",
    ]


def test_view_only_change_form_offers_close_instead_of_save(staff_client, catalog):
    soup = BeautifulSoup(staff_client("view_item").get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert soup.select_one("[data-save]") is None
    assert soup.find("a", string="Close")["href"] == url(Item, "changelist")


def test_add_without_change_permission_offers_save_and_view(staff_client, catalog):
    soup = BeautifulSoup(staff_client("add_item", "view_item").get(url(Item, "add")).content, "html.parser")

    assert soup.select_one("[data-continue]").get_text(strip=True) == "Save and view"


def test_delete_confirmation_puts_the_confirm_button_first(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "delete", catalog.beta.pk)).content, "html.parser")

    controls = soup.find("input", {"name": "post"}).parent.find_all(["button", "a"], recursive=False)
    assert controls[0]["type"] == "submit"
    assert controls[1]["href"] == url(Item, "change", catalog.beta.pk)


def test_protected_delete_offers_no_confirm_button(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Category, "delete", catalog.kitchen.pk)).content, "html.parser")

    assert soup.find("input", {"name": "post"}) is None


def test_filter_count_shows_zero_without_filters(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.find(id="changelist-filter-count").get_text(strip=True) == "0"


@pytest.mark.parametrize("search_fields", [["name"], []], ids=["search", "no_search"])
def test_list_without_filters_keeps_the_filter_button(admin_client, catalog, monkeypatch, search_fields):
    monkeypatch.setattr(site.get_model_admin(Tag), "search_fields", search_fields)

    soup = BeautifulSoup(admin_client.get(url(Tag, "changelist")).content, "html.parser")

    assert soup.select_one("#changelist-filters [aria-controls=changelist-filter-row]") is not None
    row = soup.find(id="changelist-filter-row")
    assert row.find("fieldset") is None
    assert "No filters" in row.get_text()


def test_change_of_a_missing_object_redirects(admin_client):
    assert admin_client.get(url(Item, "change", 999)).status_code == 302


def test_delete_view_deletes_and_logs(admin_client, catalog):
    response = admin_client.post(url(Item, "delete", catalog.beta.pk))

    assert response.status_code == 302
    assert not Item.objects.filter(pk=catalog.beta.pk).exists()
    assert LogEntry.objects.filter(action_flag=DELETION, object_id=str(catalog.beta.pk)).exists()


def test_delete_view_refuses_a_protected_object(admin_client, catalog):
    response = admin_client.post(url(Category, "delete", catalog.kitchen.pk))

    assert response.status_code == 200
    assert Category.objects.filter(pk=catalog.kitchen.pk).exists()


def test_history_and_index_show_admin_changes(admin_client, catalog):
    data = item_data(catalog.office, name="Beta lamp", quantity="9")
    admin_client.post(url(Item, "change", catalog.beta.pk), data)

    assert b"Quantity" in admin_client.get(url(Item, "history", catalog.beta.pk)).content
    assert b"Beta lamp" in admin_client.get(reverse("admin:index")).content


def test_view_permission_shows_rows_read_only(staff_client, catalog):
    client = staff_client("view_item")

    assert client.get(url(Item, "changelist")).status_code == 200
    assert client.get(url(Item, "change", catalog.beta.pk)).status_code == 200
    assert client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office)).status_code == 403
    assert client.get(url(Item, "add")).status_code == 403
    assert client.post(url(Item, "delete", catalog.beta.pk)).status_code == 403
    assert Item.objects.filter(pk=catalog.beta.pk, name="Beta lamp").exists()


def test_view_permission_cannot_run_delete_selected(staff_client, catalog):
    client = staff_client("view_item")

    client.post(
        url(Item, "changelist"), {"action": "delete_selected", "_selected_action": [catalog.beta.pk], "post": "yes"}
    )

    assert Item.objects.filter(pk=catalog.beta.pk).exists()


def test_staff_without_permissions_sees_no_models(staff_client):
    client = staff_client()

    assert client.get(url(Item, "changelist")).status_code == 403
    assert url(Item, "changelist").encode() not in client.get(reverse("admin:index")).content


def test_changelist_info_button_loads_the_info_dialog(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one(f"[hx-get='{url(Item, 'info')}']")["hx-target"] == "#changelist-info-body"


def test_info_dialog_names_what_the_search_looks_in(admin_client, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "search_help_text", "Names and categories.")

    text = BeautifulSoup(admin_client.get(url(Item, "info")).content, "html.parser").get_text(" ", strip=True)

    assert "category__name" in text
    assert "Names and categories." in text


def test_info_dialog_shows_the_table_to_superusers_only(admin_client, staff_client):
    assert b"admin_app_item" in admin_client.get(url(Item, "info")).content
    assert b"admin_app_item" not in staff_client("view_item").get(url(Item, "info")).content


def test_info_dialog_needs_view_permission(staff_client):
    assert staff_client().get(url(Item, "info")).status_code == 403


@pytest.mark.parametrize(
    ("entry", "path", "lookup"),
    [
        ("name", ("Name",), "contains"),
        ("^name", ("Name",), "starts with"),
        ("=category__slug", ("Category", "Slug"), "is"),
        ("@notes", ("Notes",), "full text"),
        ("category__name__exact", ("Category", "Name"), "exact"),
        ("parts__name", ("Parts", "Name"), "contains"),
    ],
)
def test_describe_search_reads_entries_as_django_does(entry, path, lookup):
    (field,) = describe_search(Item, [entry])

    assert (field.path, field.lookup) == (path, lookup)


def test_describe_fields_reads_types_and_relations():
    fields = {field.name: field for field in describe_fields(Item._meta)}

    assert fields["price"].kind == "DecimalField(10, 2)"
    assert (fields["category"].column, fields["category"].related) == ("category_id", "admin_app.Category")
    assert fields["tags"].column == "admin_app_item_tags"


def test_describe_table_lists_the_primary_key_first():
    table = describe_table(Item)

    assert table.name == "admin_app_item"
    assert table.indexes[0].kind == "primary_key"
    assert any(index.kind == "foreign_key" and index.columns == ("category_id",) for index in table.indexes)


def test_relation_search_returns_matching_rows(admin_client, catalog):
    params = {"widget": "select", "site": "admin", "model": "admin_app.item", "field": "category", "q": "kit"}

    response = admin_client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    assert b"Kitchen" in response.content
    assert b"Office" not in response.content


def test_relation_search_denies_non_staff(client, django_user_model, catalog):
    client.force_login(django_user_model.objects.create_user("guest"))
    params = {"widget": "select", "site": "admin", "model": "admin_app.item", "field": "category", "q": "kit"}

    response = client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    assert response.status_code == 403


def test_view_on_site_redirects_to_the_object(admin_client, catalog):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(Item)

    response = admin_client.get(reverse("admin:view_on_site", args=[content_type.pk, catalog.alpha.pk]))

    assert response.status_code == 302
    assert response["Location"].endswith(f"/items/{catalog.alpha.pk}/")


def test_registered_admins_pass_the_checks():
    assert checks.run_checks(tags=[checks.Tags.admin]) == []


@pytest.mark.parametrize(
    ("options", "error_id"),
    [
        ({"list_display": ["nope"]}, "formwork_admin.E108"),
        ({"list_display": ["name"], "list_editable": ["quantity"]}, "formwork_admin.E122"),
        ({"list_display": ["name", "quantity"], "list_editable": ["name"]}, "formwork_admin.E124"),
        ({"autocomplete_fields": ["nope"]}, "formwork_admin.E037"),
        ({"autocomplete_fields": ["name"]}, "formwork_admin.E038"),
        ({"list_filter": [42]}, "formwork_admin.E116"),
    ],
)
def test_checks_report_misconfigured_options(options, error_id):
    model_admin = type("BrokenAdmin", (admin.ModelAdmin,), options)(Item, site)

    assert [error.id for error in check_model_admin(model_admin)] == [error_id]


def test_string_action_resolves_to_the_admin_method():
    assert site.get_model_admin(Item).get_action("mark_active")[0] is ItemAdmin.mark_active
