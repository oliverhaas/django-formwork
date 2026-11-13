"""Tests for django_formwork.admin, driven through the demo app's admin pages."""

import json
from datetime import date, datetime
from types import ModuleType, SimpleNamespace

import django
import django_filters
import pytest
from admin_app.admin import ItemAdmin, LowStockFilter, PartInline, ReviewInline
from admin_app.models import Category, Item, Note, Part, Tag
from bs4 import BeautifulSoup
from django import forms
from django.contrib import admin as django_admin
from django.contrib.admin import EmptyFieldListFilter, RelatedOnlyFieldListFilter, ShowFacets
from django.contrib.admin import widgets as django_widgets
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.admin import GenericTabularInline as DjangoGenericTabularInline
from django.core import checks
from django.db import models
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils import timezone, translation

from django_formwork import admin
from django_formwork.admin import ActionLocation, site
from django_formwork.admin.checks import check_model_admin
from django_formwork.admin.contenttypes import GenericStackedInline
from django_formwork.admin.info import describe_fields, describe_search, describe_table
from django_formwork.admin.models import HistoryEntry
from django_formwork.admin.widgets import RELATION_SEARCH_KEY, AdminDateWidget
from django_formwork.forms import FormworkModelForm
from django_formwork.widgets import Select, SelectMultiple, Textarea, TextInput

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
    editors = Group.objects.create(name="Editors")
    return SimpleNamespace(kitchen=kitchen, office=office, sale=sale, alpha=alpha, beta=beta, lid=lid, editors=editors)


@pytest.fixture
def staff_client(client, django_user_model):
    def login(*codenames):
        user = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        client.force_login(user)
        return client

    return login


@pytest.mark.parametrize(
    "model",
    [model for model in site._registry if model._meta.app_label != "history_app"],
    ids=lambda model: model._meta.label,
)
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


def test_unknown_url_sends_a_signed_out_visitor_to_login(client):
    response = client.get("/admin/admin_app/nope/")

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("admin:login"))


@pytest.mark.parametrize(
    ("target", "location"),
    [
        ("/admin/admin_app/item", "/admin/admin_app/item/"),
        ("/admin/admin_app/nope", None),
        ("/admin/admin_app/nope/", None),
    ],
)
def test_unknown_url_adds_a_missing_slash_or_is_not_found(admin_client, target, location):
    response = admin_client.get(target)

    assert response.status_code == (301 if location else 404)
    assert response.get("Location") == location


def test_switched_off_catch_all_answers_404_to_a_signed_out_visitor(client, monkeypatch, settings):
    monkeypatch.setattr(site, "final_catch_all_view", False)
    urlconf = ModuleType("admin_urls_without_catch_all")
    urlconf.urlpatterns = [path("admin/", site.urls)]
    settings.ROOT_URLCONF = urlconf

    assert client.get("/admin/admin_app/nope/").status_code == 404


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
        lambda c: {"status__exact": "archived"},
        lambda c: {"is_featured__exact": "1"},
        lambda c: {"category__id__exact": c.kitchen.pk},
        lambda c: {"tags__id__exact": c.sale.pk},
        lambda c: {"stock": "out"},
        lambda c: {"released__gte": "2026-01-01", "released__lt": "2026-02-01"},
        lambda c: {"released__year": "2026", "released__month": "1"},
        lambda c: {"name__startswith": "Alpha"},
    ],
    ids=[
        "search",
        "choices",
        "boolean",
        "foreign_key",
        "many_to_many",
        "simple_list_filter",
        "date_range",
        "date_hierarchy",
        "other_lookup",
    ],
)
def test_changelist_filters_rows(admin_client, catalog, params):
    response = admin_client.get(url(Item, "changelist"), params(catalog))

    assert response.status_code == 200
    assert b"Alpha kettle" in response.content
    assert b"Beta lamp" not in response.content


@pytest.mark.parametrize(
    ("list_filter", "params"),
    [
        ([("website", EmptyFieldListFilter)], lambda c: {"website__isempty": "1"}),
        ([("category", RelatedOnlyFieldListFilter)], lambda c: {"category__id__exact": c.kitchen.pk}),
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

    response = admin_client.get(url(Item, "changelist"), {"quantity__gte": "10"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert b"Beta lamp" in response.content
    assert b"Alpha kettle" not in response.content
    assert soup.find("input", attrs={"name": "quantity__gte"})["value"] == "10"
    assert soup.find("input", attrs={"name": "quantity__lte"}) is not None
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.parametrize(
    ("isnull", "shown", "hidden"), [("True", b"Beta lamp", b"Alpha kettle"), ("False", b"Alpha kettle", b"Beta lamp")]
)
def test_date_filter_picks_the_rows_without_a_date_or_with_one(admin_client, catalog, isnull, shown, hidden):
    response = admin_client.get(url(Item, "changelist"), {"released__isnull": isnull})
    soup = BeautifulSoup(response.content, "html.parser")

    assert shown in response.content
    assert hidden not in response.content
    assert soup.find("input", attrs={"name": "released__isnull"})["value"] == isnull
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.parametrize(
    ("params", "shown"),
    [({}, False), ({"q": "kettle"}, False), ({"status__exact": "archived"}, True)],
    ids=["unfiltered", "search_only", "filtered"],
)
def test_filter_row_starts_open_while_a_filter_is_active(admin_client, catalog, params, shown):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    row = soup.find(id="changelist-filter-row")
    assert ("display: none" not in row.get("style", "")) is shown


def test_clear_all_filters_keeps_the_search(admin_client, catalog):
    soup = BeautifulSoup(
        admin_client.get(url(Item, "changelist"), {"status__exact": "archived", "q": "kettle"}).content, "html.parser"
    )

    assert soup.find(id="changelist-filter-count").get_text(strip=True) == "1"
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == "?q=kettle"


def test_clear_all_filters_keeps_other_lookups(admin_client, catalog):
    response = admin_client.get(url(Item, "changelist"), {"status__exact": "archived", "name__startswith": "Alpha"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == "?name__startswith=Alpha"
    assert soup.select_one('#changelist-filters input[name="name__startswith"]')["value"] == "Alpha"


def test_lookup_through_a_relation_outside_list_filter_is_refused(admin_client, catalog):
    assert admin_client.get(url(Item, "changelist"), {"category__slug__exact": "kitchen"}).status_code == 400


@pytest.mark.parametrize("params", [{"nonsense": "1"}, {"quantity__exact": "many"}], ids=["field", "value"])
def test_lookup_the_list_cannot_apply_starts_over_with_the_error_flag(admin_client, catalog, params):
    response = admin_client.get(url(Item, "changelist"), params)

    assert response.status_code == 302
    assert response["Location"] == f"{url(Item, 'changelist')}?e=1"
    assert b"cannot apply" in admin_client.get(response["Location"]).content


@pytest.mark.parametrize(
    ("params", "pushed"),
    [
        (
            {"released__gte": "2026-01-01", "released__lte": "2026-01-31"},
            "?released__gte=2026-01-01&released__lt=2026-02-01",
        ),
        ({"released__gte": "", "released__lte": "", "released__isnull": "True"}, "?released__isnull=True"),
        ({"tags__id__exact": "null"}, "?tags__isnull=True"),
        ({"is_featured__exact": "True"}, "?is_featured__exact=1"),
        ({"released__gte": "2026-01-01", "released__lt": "2026-02-01", "status__exact": "archived"}, None),
    ],
    ids=["date_range", "no_date", "empty_relation", "boolean", "already_django"],
)
def test_filter_form_request_shows_django_params_in_the_address_bar(admin_client, catalog, params, pushed):
    response = admin_client.get(url(Item, "changelist"), params, headers={"HX-Request": "true"})

    expected = None if pushed is None else f"{url(Item, 'changelist')}{pushed}"
    assert response.headers.get("HX-Push-Url") == expected


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
        "id_status__exact_field",
        "id_quantity_field",
        "id_category__id__exact_field",
    ]


def option_texts(soup, name):
    options = soup.select(f"#id_{name}_wrapper [role=option] > [data-value]")
    return {option["data-value"]: option.get_text(" ", strip=True) for option in options}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("status__exact", lambda c: {"archived": "Archived 1", "draft": "Draft 0"}),
        ("category__id__exact", lambda c: {str(c.kitchen.pk): "Kitchen 1", str(c.office.pk): "Office 1"}),
        ("is_featured__exact", lambda c: {"1": "Yes 1", "0": "No 0"}),
        ("stock", lambda c: {"out": "Out of stock 1", "low": "Low 0"}),
        ("tags__id__exact", lambda c: {str(c.sale.pk): "sale 1", "null": "- 0"}),
        ("website__isempty", lambda c: {"1": "Empty 1", "0": "Not empty 0"}),
    ],
    ids=["choices", "own_filter_left_out", "boolean", "simple_list_filter", "many_to_many", "empty_field"],
)
def test_facet_counts_apply_the_other_filters(admin_client, catalog, monkeypatch, name, expected):
    list_filter = ["status", "category", "is_featured", LowStockFilter, "tags", ("website", EmptyFieldListFilter)]
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", list_filter)

    response = admin_client.get(url(Item, "changelist"), {"_facets": "True", "category__id__exact": catalog.kitchen.pk})

    assert expected(catalog).items() <= option_texts(BeautifulSoup(response.content, "html.parser"), name).items()


@pytest.mark.usefixtures("catalog")
@pytest.mark.parametrize("name", ["category__id__exact", "tags__id__exact"])
def test_relation_filters_name_their_empty_option_as_the_others_do(admin_client, monkeypatch, name):
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", ["status", "category", "tags"])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert option_texts(soup, name)[""] == option_texts(soup, "status__exact")[""]


@pytest.mark.parametrize(("name", "offered"), [("category__id__exact", False), ("tags__id__exact", True)])
def test_relation_filters_offer_rows_without_a_relation_where_the_field_allows_them(
    admin_client, catalog, monkeypatch, name, offered
):
    monkeypatch.setattr(site.get_model_admin(Item), "empty_value_display", "(none)", raising=False)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert (option_texts(soup, name).get("null") == "(none)") is offered


def test_relation_filter_lists_rows_as_the_related_admin_orders_and_limits_them(admin_client, catalog, monkeypatch):
    archive = Category.objects.create(name="Archive", slug="archive")
    monkeypatch.setattr(site.get_model_admin(Category), "ordering", ["-name"])
    monkeypatch.setattr(Item._meta.get_field("category").remote_field, "limit_choices_to", ~models.Q(slug="archive"))

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    offered = [value for value in option_texts(soup, "category__id__exact") if value not in {"", "null"}]
    assert offered == [str(catalog.office.pk), str(catalog.kitchen.pk)]
    assert str(archive.pk) not in offered


def test_empty_relation_option_reads_and_writes_django_isnull(admin_client, catalog):
    response = admin_client.get(url(Item, "changelist"), {"tags__isnull": "True"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert b"Beta lamp" in response.content
    assert b"Alpha kettle" not in response.content
    assert soup.find("input", attrs={"name": "tags__id__exact"})["value"] == "null"
    assert soup.select_one("#changelist-filter-row [data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.usefixtures("catalog")
@pytest.mark.parametrize(
    ("show_facets", "params", "expected"),
    [
        (ShowFacets.ALLOW, {}, (False, True)),
        (ShowFacets.ALLOW, {"_facets": "True"}, (True, True)),
        (ShowFacets.ALWAYS, {}, (True, False)),
        (ShowFacets.NEVER, {"_facets": "True"}, (False, False)),
    ],
    ids=["allow", "allow_switched_on", "always", "never"],
)
def test_show_facets_decides_the_counts_and_the_switch(admin_client, monkeypatch, show_facets, params, expected):
    monkeypatch.setattr(site.get_model_admin(Item), "show_facets", show_facets)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    counted = option_texts(soup, "status__exact")["archived"] == "Archived 1"
    switch = soup.find("input", attrs={"name": "_facets"}) is not None
    assert (counted, switch) == expected


def test_facet_counts_count_a_row_once_when_the_search_repeats_it(admin_client, catalog, monkeypatch):
    catalog.alpha.tags.add(Tag.objects.create(name="sale price"))
    monkeypatch.setattr(site.get_model_admin(Item), "search_fields", ["tags__name"])

    response = admin_client.get(url(Item, "changelist"), {"_facets": "True", "q": "sale"})

    assert option_texts(BeautifulSoup(response.content, "html.parser"), "status__exact")["archived"] == "Archived 1"


def test_sort_links_keep_the_counts_switched_on(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), {"_facets": "True"}).content, "html.parser")

    assert "_facets=True" in soup.select_one("thead a[href*='o=']")["href"]


@pytest.mark.parametrize(("icon", "shown"), [("package", "icon-package"), (None, "icon-star")])
def test_navigation_shows_the_model_icon_or_a_placeholder_shape(admin_client, catalog, monkeypatch, icon, shown):
    monkeypatch.setattr(site.get_model_admin(Item), "icon", icon)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one(f'a[aria-current="page"] .{shown}') is not None


def test_keyboard_reaches_a_skip_link_then_the_navigation_then_the_content(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    order = [
        el.name for el in soup.body.find_all(["a", "aside", "main"]) if el.name != "a" or el.get("href") == "#content"
    ]
    assert order == ["a", "aside", "main"]


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
        assert "choice-group" in soup.find("fieldset", id=f"id_{name}_field")["class"]


@pytest.mark.parametrize(
    ("actions", "order", "first"),
    [(["mark_active"], "5", b"Alpha kettle"), (["mark_active"], "-5", b"Beta lamp"), (None, "4", b"Alpha kettle")],
    ids=["ascending", "descending", "without_the_action_column"],
)
@pytest.mark.usefixtures("catalog")
def test_changelist_sorts_by_the_column_number_in_o(admin_client, monkeypatch, actions, order, first):
    monkeypatch.setattr(site.get_model_admin(Item), "actions", actions)

    content = admin_client.get(url(Item, "changelist"), {"o": order}).content

    second = ({b"Alpha kettle", b"Beta lamp"} - {first}).pop()
    assert content.index(first) < content.index(second)


def sort_links(response):
    headers = BeautifulSoup(response.content, "html.parser").select("#changelist-table thead th[data-col]")
    return {th.get_text(" ", strip=True): th.a["href"] for th in headers if th.a}


def test_header_sorts_by_its_column_first_and_keeps_the_other_sorted_columns(admin_client, catalog):
    links = sort_links(admin_client.get(url(Item, "changelist"), {"o": "-3.1"}))

    assert links["Status 1"] == "?o=3.1"
    assert links["Name 2"] == "?o=-1.-3"
    assert links["Price"] == "?o=4.-3.1"


def remove_links(response):
    headers = BeautifulSoup(response.content, "html.parser").select("#changelist-table thead th[data-col]")
    return {th.get_text(" ", strip=True): link["href"] for th in headers for link in th.select("a[aria-label]")}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"o": "-3.1"}, {"Status 1": "?o=1", "Name 2": "?o=-3"}),
        ({"o": "4", "p": "2"}, {"Price": "?o="}),
        ({}, {"Name": "?o="}),
    ],
    ids=["two_sorted_columns", "one_sorted_column", "admin_ordering"],
)
def test_sorted_header_links_to_the_order_without_its_column(admin_client, catalog, monkeypatch, params, expected):
    monkeypatch.setattr(site.get_model_admin(Item), "ordering", ["name"])

    assert remove_links(admin_client.get(url(Item, "changelist"), params)) == expected


def test_blank_order_marks_no_column_and_keeps_the_model_ordering(admin_client, catalog):
    response = admin_client.get(url(Category, "changelist"), {"o": ""})

    soup = BeautifulSoup(response.content, "html.parser")
    assert soup.select("thead th[aria-sort]") == []
    assert [field["value"] for field in soup.select("input[name=o][form=changelist-filters]")] == [""]
    assert response.content.index(b"Kitchen") < response.content.index(b"Office")


def test_header_marks_the_admin_ordering_while_no_column_is_picked(admin_client, catalog):
    response = admin_client.get(url(Category, "changelist"))

    assert BeautifulSoup(response.content, "html.parser").select_one("thead th[aria-sort]")["aria-sort"] == "ascending"
    assert sort_links(response)["Name"] == "?o=-1"


def test_changelist_sorts_a_column_that_follows_a_relation(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", "category__name"])

    content = admin_client.get(url(Item, "changelist"), {"o": "-2"}).content

    assert content.index(b"Beta lamp") < content.index(b"Alpha kettle")


def test_changelist_shows_the_choice_label_in_a_column_that_follows_a_relation(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", "category__slug"])
    monkeypatch.setattr(Category._meta.get_field("slug"), "choices", [("kitchen", "Kitchenware"), ("office", "Desk")])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert "Kitchenware" in soup.select_one(f"tr[data-pk='{catalog.alpha.pk}']").get_text()


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


def status_action(**options):
    @admin.action(**options)
    def set_status(modeladmin, request, queryset):
        queryset.update(status=Item.Status.ACTIVE)
        modeladmin.message_user(request, "Status set.")

    return set_status


def action_labels(response, field):
    buttons = BeautifulSoup(response.content, "html.parser").select(f'button[name="{field}"]')
    return {button["value"]: button.get_text(" ", strip=True) for button in buttons}


def run_on_change_form(client, obj, name, selected=None):
    data = {"CHANGE_FORM-action": name, "_selected_action": [obj.pk] if selected is None else selected}
    return client.post(url(Item, "change", obj.pk), data)


@pytest.mark.parametrize(
    ("location", "labels"),
    [
        (ActionLocation.CHANGE_LIST, ("Verify these items", None)),
        (ActionLocation.CHANGE_FORM, (None, "Verify this item")),
        ([ActionLocation.CHANGE_LIST, ActionLocation.CHANGE_FORM], ("Verify these items", "Verify this item")),
    ],
    ids=["list", "change_form", "both"],
)
def test_action_shows_where_its_location_puts_it(admin_client, catalog, monkeypatch, location, labels):
    action = status_action(
        description="Verify this %(verbose_name)s",
        description_plural="Verify these %(verbose_name_plural)s",
        location=location,
    )
    monkeypatch.setattr(ItemAdmin, "actions", [action])

    listed = action_labels(admin_client.get(url(Item, "changelist")), "action")
    offered = action_labels(admin_client.get(url(Item, "change", catalog.alpha.pk)), "CHANGE_FORM-action")

    assert (listed.get("set_status"), offered.get("set_status")) == labels


@pytest.mark.skipif(django.VERSION < (6, 1), reason="Django 6.0's @admin.action takes no location")
def test_change_form_offers_an_action_from_djangos_decorator(admin_client, catalog, monkeypatch):
    @django_admin.action(description="Verify", location=django_admin.ActionLocation.CHANGE_FORM)
    def verify(modeladmin, request, queryset):
        pass

    monkeypatch.setattr(ItemAdmin, "actions", [verify])

    response = admin_client.get(url(Item, "change", catalog.alpha.pk))

    assert action_labels(response, "CHANGE_FORM-action") == {"verify": "Verify"}


def test_change_form_action_runs_on_its_row_and_reloads_the_page(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(location=ActionLocation.CHANGE_FORM)])

    response = run_on_change_form(admin_client, catalog.alpha, "set_status")

    assert response.status_code == 302
    assert response["Location"] == url(Item, "change", catalog.alpha.pk)
    assert b"Status set." in admin_client.get(response["Location"]).content
    assert Item.objects.get(pk=catalog.alpha.pk).status == Item.Status.ACTIVE
    assert Item.objects.get(pk=catalog.beta.pk).status == Item.Status.DRAFT


@pytest.mark.parametrize("selected", [["beta"], ["alpha", "beta"], []], ids=["other_row", "two_rows", "no_row"])
def test_change_form_action_refuses_any_selection_but_its_row(admin_client, catalog, monkeypatch, selected):
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(location=ActionLocation.CHANGE_FORM)])

    pks = [getattr(catalog, name).pk for name in selected]
    response = run_on_change_form(admin_client, catalog.alpha, "set_status", selected=pks)

    assert response.status_code == 400
    assert not Item.objects.filter(status=Item.Status.ACTIVE).exists()


def test_change_form_action_answers_with_its_own_response(admin_client, catalog, monkeypatch):
    @admin.action(location=ActionLocation.CHANGE_FORM)
    def download(modeladmin, request, queryset):
        return HttpResponse(",".join(item.name for item in queryset), content_type="text/csv")

    monkeypatch.setattr(ItemAdmin, "actions", [download])

    response = run_on_change_form(admin_client, catalog.alpha, "download")

    assert response.status_code == 200
    assert response.content == b"Alpha kettle"


@pytest.mark.parametrize(("view", "params"), [("add", {}), ("change", {"_popup": "1"})], ids=["add", "dialog"])
def test_change_form_offers_no_actions_on_the_add_page_or_in_a_dialog(admin_client, catalog, monkeypatch, view, params):
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(location=ActionLocation.CHANGE_FORM)])

    args = [] if view == "add" else [catalog.alpha.pk]
    response = admin_client.get(url(Item, view, *args), params)

    assert response.status_code == 200
    assert action_labels(response, "CHANGE_FORM-action") == {}


@pytest.mark.parametrize(("permissions", "shown"), [(["delete", "change"], True), (["delete"], False)])
def test_action_shows_with_any_one_of_its_permissions(admin_client, catalog, monkeypatch, permissions, shown):
    monkeypatch.setattr(ItemAdmin, "has_delete_permission", lambda self, request, obj=None: False)
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(permissions=permissions)])

    listed = action_labels(admin_client.get(url(Item, "changelist")), "action")

    assert ("set_status" in listed) is shown


@pytest.mark.parametrize(
    ("permissions", "status"),
    [(["view"], Item.Status.ACTIVE), (["change"], Item.Status.ARCHIVED)],
    ids=["view", "change"],
)
def test_view_only_user_runs_the_change_form_actions_that_allow_viewing(
    admin_client, catalog, monkeypatch, permissions, status
):
    monkeypatch.setattr(ItemAdmin, "has_change_permission", lambda self, request, obj=None: False)
    action = status_action(permissions=permissions, location=ActionLocation.CHANGE_FORM)
    monkeypatch.setattr(ItemAdmin, "actions", [action])

    run_on_change_form(admin_client, catalog.alpha, "set_status")

    assert Item.objects.get(pk=catalog.alpha.pk).status == status


def test_get_actions_override_from_before_django_6_1_keeps_its_actions_in_the_list(admin_client, catalog, monkeypatch):
    def get_actions(self, request):
        return {"mark_active": (ItemAdmin.mark_active, "mark_active", "Activate")}

    monkeypatch.setattr(ItemAdmin, "get_actions", get_actions)

    listed = action_labels(admin_client.get(url(Item, "changelist")), "action")
    offered = action_labels(admin_client.get(url(Item, "change", catalog.alpha.pk)), "CHANGE_FORM-action")
    admin_client.post(url(Item, "changelist"), {"action": "mark_active", "_selected_action": [catalog.beta.pk]})

    assert listed == {"mark_active": "Activate"}
    assert offered == {}
    assert Item.objects.get(pk=catalog.beta.pk).status == Item.Status.ACTIVE


def test_delete_selected_confirms_before_deleting(admin_client, catalog):
    data = {"action": "delete_selected", "_selected_action": [catalog.beta.pk]}

    assert admin_client.post(url(Item, "changelist"), data).status_code == 200
    assert Item.objects.filter(pk=catalog.beta.pk).exists()

    admin_client.post(url(Item, "changelist"), {**data, "post": "yes"})

    assert not Item.objects.filter(pk=catalog.beta.pk).exists()
    assert HistoryEntry.objects.filter(action="delete", object_id=str(catalog.beta.pk)).exists()


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
    assert HistoryEntry.objects.filter(action="change", object_id=str(catalog.alpha.pk)).exists()


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


def test_list_editable_failed_save_keeps_the_valid_changes_marked(admin_client, catalog):
    page = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    first, second = (page.find("input", attrs={"name": f"form-{i}-id"})["value"] for i in range(2))
    data = {
        **management("form", 2, 2),
        "form-0-id": first,
        "form-0-quantity": "77",
        "form-1-id": second,
        "form-1-quantity": "-1",
        "_save": "1",
    }

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")

    marked = soup.select("#changelist-table td[data-formwork-changed]")
    assert [cell.find("input")["name"] for cell in marked] == ["form-0-quantity"]


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
    assert HistoryEntry.objects.filter(action="add", object_id=str(item.pk)).exists()


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


def folded_inlines(response):
    soup = BeautifulSoup(response.content, "html.parser")
    return [(group["id"], group.has_attr("open")) for group in soup.select("details[id$='-group']")]


@pytest.mark.parametrize(("inline", "field"), [(PartInline, "parts-0-quantity"), (ReviewInline, "reviews-0-text")])
def test_collapse_class_folds_an_inline_until_a_row_has_an_error(admin_client, catalog, monkeypatch, inline, field):
    monkeypatch.setattr(inline, "classes", ["collapse"])
    change = url(Item, "change", catalog.beta.pk)
    prefix = field.split("-")[0]

    shown = admin_client.get(change)
    failed = admin_client.post(change, item_data(catalog.office, **management(prefix, total=1), **{field: "4"}))

    assert folded_inlines(shown) == [(f"{prefix}-group", False)]
    assert folded_inlines(failed) == [(f"{prefix}-group", True)]


@pytest.mark.parametrize(
    ("inline", "max_num", "name"), [(PartInline, 1, "part"), (ReviewInline, 1, "review"), (ReviewInline, 3, "reviews")]
)
def test_inline_of_one_row_at_most_is_named_in_the_singular(admin_client, monkeypatch, inline, max_num, name):
    monkeypatch.setattr(inline, "max_num", max_num)
    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")
    group = soup.select_one(f"#{inline.model._meta.model_name}s-group")

    assert group.h2.get_text(strip=True) == name.capitalize()
    assert name in group.select_one("p[x-show='!total']").get_text().split()


NOTES = "admin_app-note-content_type-object_id"


class NoteInline(GenericStackedInline):
    model = Note
    extra = 0


@pytest.fixture
def notes_inline(monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "inlines", [*model_admin.inlines, NoteInline])


def test_generic_inline_shows_the_parents_rows_as_formwork_fields(admin_client, catalog, notes_inline):
    Note.objects.create(target=catalog.alpha, text="Check the hinges")
    Note.objects.create(target=catalog.beta, text="Oil the wheels")

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert soup.select_one(f"input[name='{NOTES}-TOTAL_FORMS']")["value"] == "1"
    assert soup.select_one(f"input[name='{NOTES}-0-text']")["value"] == "Check the hinges"
    assert soup.select_one(f"#id_{NOTES}-0-text_field label .text-error") is not None


def test_generic_inline_saves_a_row_for_the_parent(admin_client, catalog, notes_inline):
    data = item_data(catalog.office, **management(NOTES, total=1), **{f"{NOTES}-0-text": "Check the hinges"})

    admin_client.post(url(Item, "add"), data)

    assert [note.target for note in Note.objects.all()] == [Item.objects.get(name="Gamma desk")]


class ExtraMedia:
    css = {"all": ["admin_app/extra.css"]}
    js = ["admin_app/extra.js"]


def media_files(response):
    head = BeautifulSoup(response.content, "html.parser").head
    return {tag.get("src") or tag.get("href") for tag in head.select("script[src*=admin_app], link[href*=admin_app]")}


@pytest.mark.parametrize("view", ["changelist", "add", "change", "delete", "history"])
def test_admin_media_class_loads_on_every_page_of_the_admin(admin_client, catalog, monkeypatch, view):
    monkeypatch.setattr(ItemAdmin, "Media", ExtraMedia, raising=False)
    args = [] if view in ("changelist", "add") else [catalog.alpha.pk]

    response = admin_client.get(url(Item, view, *args))

    assert media_files(response) == {"/static/admin_app/extra.css", "/static/admin_app/extra.js"}


def test_inline_media_class_loads_on_the_change_form(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ReviewInline, "Media", ExtraMedia, raising=False)

    response = admin_client.get(url(Item, "change", catalog.alpha.pk))

    assert media_files(response) == {"/static/admin_app/extra.css", "/static/admin_app/extra.js"}


def test_change_with_errors_saves_nothing(admin_client, catalog):
    response = admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, name=""))

    assert response.status_code == 200
    assert Item.objects.get(pk=catalog.beta.pk).name == "Beta lamp"


def test_field_errors_show_under_their_fields(admin_client, catalog):
    data = {
        **item_data(catalog.office, name=""),
        **management("reviews", total=1),
        "reviews-0-id": "",
        "reviews-0-author": "",
        "reviews-0-rating": "5",
        "reviews-0-text": "Sturdy",
    }

    soup = BeautifulSoup(admin_client.post(url(Item, "change", catalog.beta.pk), data).content, "html.parser")

    for field_id in ("id_name", "id_reviews-0-author"):
        assert "required" in soup.select_one(f"#{field_id}_field .formwork-disclosure-text").get_text()
        assert soup.select_one(f"#{field_id}_field .tooltip") is None


def test_a_form_that_sets_its_error_display_keeps_it(admin_client, catalog, monkeypatch):
    class TooltipForm(FormworkModelForm):
        class Meta:
            error_display = "tooltip"

    monkeypatch.setattr(site.get_model_admin(Item), "form", TooltipForm)

    response = admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, name=""))

    tooltip = BeautifulSoup(response.content, "html.parser").select_one("#id_name_field .tooltip-content")
    assert "required" in tooltip.get_text()


def test_datetime_field_saves_the_day_and_the_time_typed_apart(admin_client, catalog, monkeypatch):
    fields = ["name", "slug", "category", "status", "price", "quantity", "available_from"]
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": fields})])

    admin_client.post(
        url(Item, "add"), item_data(catalog.office, available_from_0="2026-03-01", available_from_1="09:30")
    )

    assert Item.objects.get(name="Gamma desk").available_from == datetime(
        2026, 3, 1, 9, 30, tzinfo=timezone.get_current_timezone()
    )


@pytest.fixture
def admin_request(rf, admin_user):
    request = rf.get("/")
    request.user = admin_user
    return request


@pytest.mark.parametrize(
    ("name", "widget", "expected"),
    [
        ("released", django_widgets.AdminDateWidget(), AdminDateWidget),
        ("notes", django_widgets.AdminTextareaWidget(), Textarea),
        ("website", django_widgets.AdminURLFieldWidget(), TextInput),
        ("quantity", django_widgets.AdminIntegerFieldWidget(), forms.NumberInput),
        ("status", django_widgets.AdminRadioSelect(), forms.RadioSelect),
        ("category", django_widgets.AutocompleteSelect(Item._meta.get_field("category"), django_admin.site), Select),
        ("tags", django_widgets.FilteredSelectMultiple("tags", is_stacked=False), SelectMultiple),
    ],
)
def test_change_form_puts_formwork_widgets_in_place_of_djangos(admin_request, monkeypatch, name, widget, expected):
    form = forms.modelform_factory(Item, form=FormworkModelForm, fields="__all__", widgets={name: widget})
    monkeypatch.setattr(site.get_model_admin(Item), "form", form)

    swapped = site.get_model_admin(Item).get_form(admin_request).base_fields[name].widget

    assert type(getattr(swapped, "widget", swapped)) is expected


@pytest.mark.parametrize(
    ("owner", "name", "form_of"),
    [
        (site.get_model_admin(Item), "notes", lambda request: site.get_model_admin(Item).get_changelist_form(request)),
        (ReviewInline, "text", lambda request: ReviewInline(Item, site).get_formset(request).form),
    ],
    ids=["changelist", "inline"],
)
def test_list_and_inline_forms_put_formwork_widgets_in_place_of_djangos(
    admin_request, monkeypatch, owner, name, form_of
):
    form = forms.modelform_factory(
        owner.model, form=FormworkModelForm, fields="__all__", widgets={name: django_widgets.AdminTextareaWidget}
    )
    monkeypatch.setattr(owner, "form", form)

    assert type(form_of(admin_request).base_fields[name].widget) is Textarea


def test_split_datetime_field_saves_the_day_and_the_time_posted_apart(admin_client, catalog, monkeypatch):
    class SplitForm(FormworkModelForm):
        available_from = forms.SplitDateTimeField(widget=django_widgets.AdminSplitDateTime, required=False)

    fields = ["name", "slug", "category", "status", "price", "quantity", "available_from"]
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": fields})])
    monkeypatch.setattr(site.get_model_admin(Item), "form", SplitForm)

    admin_client.post(
        url(Item, "add"), item_data(catalog.office, available_from_0="2026-03-01", available_from_1="09:30")
    )

    saved = Item.objects.filter(name="Gamma desk").values_list("available_from", flat=True)
    assert list(saved) == [datetime(2026, 3, 1, 9, 30, tzinfo=timezone.get_current_timezone())]
    assert type(SplitForm.base_fields["available_from"].widget) is django_widgets.AdminSplitDateTime


@pytest.mark.parametrize("value", [True, False, None])
def test_nullable_boolean_posts_back_the_value_it_shows(rf, value):
    db_field = models.BooleanField(null=True)
    db_field.set_attributes_from_name("flag")
    formfield = site.get_model_admin(Item).formfield_for_dbfield(db_field, rf.get("/"))
    form_class = type("FlagForm", (forms.Form,), {"flag": formfield})

    shown = BeautifulSoup(str(form_class(initial={"flag": value})["flag"]), "html.parser").find(attrs={"name": "flag"})
    posted = form_class({"flag": shown["value"]})

    assert posted.is_valid()
    assert posted.cleaned_data["flag"] is value


def test_dates_show_in_the_languages_input_format(admin_client, catalog):
    with translation.override("de"):
        form = admin_client.get(url(Item, "change", catalog.alpha.pk)).content
        changelist = admin_client.get(url(Item, "changelist"), {"released__gte": "2026-01-01"}).content

    assert BeautifulSoup(form, "html.parser").select_one('input[name="released"]')["value"] == "10.01.2026"
    assert BeautifulSoup(changelist, "html.parser").select_one(".date-range-filter input")["value"] == "01.01.2026"


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


def test_protected_delete_offers_only_a_way_back(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Category, "delete", catalog.kitchen.pk)).content, "html.parser")

    assert soup.find("input", {"name": "post"}) is None
    assert soup.select_one(f'main a.btn[href="{url(Category, "change", catalog.kitchen.pk)}"]') is not None


def test_delete_confirmation_names_both_ends_of_a_many_to_many_row(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "delete", catalog.alpha.pk)).content, "html.parser")

    rows = [li.get_text(" ", strip=True) for li in soup.select("details li")]
    assert any("Alpha kettle" in row and "sale" in row for row in rows if "relationship" in row)


@pytest.mark.parametrize(
    ("limit", "rows"), [(None, ["kettle", "sale", "Lid"]), (2, ["kettle", "sale", "1 more"]), (0, [])]
)
def test_delete_confirmation_lists_objects_up_to_the_max_display(admin_client, catalog, monkeypatch, limit, rows):
    monkeypatch.setattr(site.get_model_admin(Item), "delete_confirmation_max_display", limit)
    soup = BeautifulSoup(admin_client.get(url(Item, "delete", catalog.alpha.pk)).content, "html.parser")

    listed = [li.get_text(" ", strip=True) for li in soup.select("details li:not(:has(li))")]
    assert len(listed) == len(rows)
    assert all(word in row for word, row in zip(rows, listed, strict=True))


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
    assert HistoryEntry.objects.filter(action="delete", object_id=str(catalog.beta.pk)).exists()


def test_delete_view_refuses_a_protected_object(admin_client, catalog):
    response = admin_client.post(url(Category, "delete", catalog.kitchen.pk))

    assert response.status_code == 200
    assert Category.objects.filter(pk=catalog.kitchen.pk).exists()


def test_history_and_index_show_admin_changes(admin_client, catalog):
    data = item_data(catalog.office, name="Beta lamp", quantity="9")
    admin_client.post(url(Item, "change", catalog.beta.pk), data)

    assert b"Quantity" in admin_client.get(url(Item, "history", catalog.beta.pk)).content
    assert b"Beta lamp" in admin_client.get(reverse("admin:index")).content


def history_rows(response, selector="#history li"):
    soup = BeautifulSoup(response.content, "html.parser")
    for hidden in soup.select(".sr-only"):
        hidden.decompose()
    return [row.get_text(" ", strip=True) for row in soup.select(selector)]


def test_change_form_shows_the_values_before_and_after_a_save(admin_client, catalog):
    data = item_data(catalog.kitchen, name="Beta lamp", quantity="9")
    admin_client.post(url(Item, "change", catalog.beta.pk), data)

    newest = history_rows(admin_client.get(url(Item, "change", catalog.beta.pk)))[0]

    assert "50 → 9" in newest
    assert "Office → Kitchen" in newest


def test_history_lists_a_changed_inline_row_under_its_name(admin_client, catalog):
    alpha = catalog.alpha
    parts = {"parts-0-id": catalog.lid.pk, "parts-0-item": alpha.pk, "parts-0-name": "Lid", "parts-0-quantity": "2"}
    data = item_data(catalog.kitchen, name=alpha.name, status=alpha.status, quantity="0", **parts)
    data.update(management("parts", total=1, initial=1))
    admin_client.post(url(Item, "change", alpha.pk), data)

    newest = history_rows(admin_client.get(url(Item, "history", alpha.pk)))[0]

    assert "Part “Lid” Quantity 1 → 2" in newest


def test_show_older_loads_the_next_entries(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "history_per_page", 1)
    for quantity in ("7", "8"):
        admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, quantity=quantity))
    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.beta.pk)).content, "html.parser")
    older = soup.select_one("#history [hx-get]")["hx-get"]

    response = admin_client.get(older, headers={"HX-Request": "true"})

    assert b"<html" not in response.content
    assert "50 → 7" in history_rows(response, "li")[0]


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


def popup_response(response):
    soup = BeautifulSoup(response.content, "html.parser")
    return json.loads(soup.find(id="formwork-admin-popup-response")["data-popup-response"])


def test_popup_add_answers_with_the_new_row(admin_client):
    data = {"name": "Garden", "slug": "garden", "_popup": "1", "_to_field": "id"}

    response = admin_client.post(url(Category, "add"), data)

    assert popup_response(response) == {"value": str(Category.objects.get(slug="garden").pk), "obj": "Garden"}


def test_popup_change_answers_with_the_changed_row(admin_client, catalog):
    data = {"name": "Galley", "slug": "kitchen", "_popup": "1", "_to_field": "id"}

    response = admin_client.post(url(Category, "change", catalog.kitchen.pk), data)

    key = str(catalog.kitchen.pk)
    assert popup_response(response) == {"action": "change", "value": key, "obj": "Galley", "new_value": key}


def test_popup_delete_answers_with_the_deleted_key(admin_client, catalog):
    response = admin_client.post(url(Tag, "delete", catalog.sale.pk), {"post": "yes", "_popup": "1"})

    assert popup_response(response) == {"action": "delete", "value": str(catalog.sale.pk)}
    assert not Tag.objects.filter(pk=catalog.sale.pk).exists()


def test_popup_page_shows_the_form_alone_with_save_only(admin_client):
    response = admin_client.get(url(Category, "add"), {"_popup": "1", "_to_field": "id"})

    soup = BeautifulSoup(response.content, "html.parser")
    assert soup.find("aside") is None
    assert [button["name"] for button in soup.select("form button[type=submit]")] == ["_save"]
    assert soup.find("input", {"name": "_popup"})["value"] == "1"


def test_popup_refuses_a_to_field_that_no_relation_uses(admin_client, catalog):
    response = admin_client.get(url(Category, "change", catalog.kitchen.pk), {"_popup": "1", "_to_field": "name"})

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("codenames", "buttons"),
    [
        (("add_item", "view_category", "view_tag"), ["View selected category"]),
        (
            ("add_item", "add_category", "change_category", "view_tag"),
            ["Change selected category", "Add another category"],
        ),
    ],
)
def test_relation_buttons_follow_the_related_admins_permissions(staff_client, catalog, codenames, buttons):
    soup = BeautifulSoup(staff_client(*codenames).get(url(Item, "add")).content, "html.parser")

    field = soup.select_one('[data-related="admin_app.category"]')
    assert [link["aria-label"] for link in field.select("[data-related-popup]")] == buttons


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"radio_fields": {"category": admin.VERTICAL}},
        {"formfield_overrides": {models.ForeignKey: {"widget": forms.Select}}},
    ],
    ids=["dropdown", "radio_fields", "native_select"],
)
def test_change_button_links_to_the_chosen_row(admin_client, catalog, monkeypatch, options):
    for name, value in options.items():
        monkeypatch.setattr(site.get_model_admin(Item), name, value)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    links = soup.select('[data-related="admin_app.category"] [data-related-popup="change"]')
    assert [link.get("href") for link in links] == [url(Category, "change", catalog.kitchen.pk)]


@pytest.mark.parametrize(("widget", "buttons"), [(forms.CheckboxSelectMultiple, 1), (forms.MultipleHiddenInput, 0)])
def test_relation_buttons_show_next_to_any_visible_widget(admin_client, catalog, monkeypatch, widget, buttons):
    overrides = {models.ManyToManyField: {"widget": widget}}
    monkeypatch.setattr(site.get_model_admin(Item), "formfield_overrides", overrides)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert soup.select_one("[name=tags]") is not None
    assert len(soup.select('[data-related="admin_app.tag"] [data-related-popup="add"]')) == buttons


def test_change_button_is_dimmed_without_a_chosen_row(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")

    link = soup.select_one('[data-related="admin_app.category"] [data-related-popup="change"]')
    assert not link.has_attr("href")
    assert link["aria-disabled"] == "true"


def test_list_editable_relation_has_no_dialog_buttons(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", ["category"])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one("#changelist [name=form-0-category]") is not None
    assert soup.select("#changelist [data-related-popup]") == []


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
        ({"form": forms.modelform_factory(Item, fields="__all__")}, "formwork_admin.E016"),
        (
            {"inlines": [type("PlainFormInline", (admin.TabularInline,), {"model": Part, "form": forms.ModelForm})]},
            "formwork_admin.E016",
        ),
        ({"inlines": [type("DjangoInline", (django_admin.TabularInline,), {"model": Part})]}, "formwork_admin.E104"),
        ({"delete_confirmation_max_display": -1}, "formwork_admin.E041"),
    ],
)
def test_checks_report_misconfigured_options(options, error_id):
    model_admin = type("BrokenAdmin", (admin.ModelAdmin,), options)(Item, site)

    assert [error.id for error in check_model_admin(model_admin)] == [error_id]


@pytest.mark.parametrize(
    ("django_inline", "module"),
    [
        (django_admin.TabularInline, "django_formwork.admin"),
        (DjangoGenericTabularInline, "django_formwork.admin.contenttypes"),
    ],
)
def test_inline_check_names_the_formwork_class_to_import(django_inline, module):
    inline = type("DjangoInline", (django_inline,), {"model": Note})
    model_admin = type("BrokenAdmin", (admin.ModelAdmin,), {"inlines": [inline]})(Item, site)

    [error] = check_model_admin(model_admin)

    assert f"from {module} " in error.hint


def test_string_action_resolves_to_the_admin_method():
    assert site.get_model_admin(Item).get_action("mark_active").func is ItemAdmin.mark_active
