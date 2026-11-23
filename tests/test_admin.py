"""Tests for django_formwork.admin, driven through the demo app's admin pages."""

import contextlib
import csv
import io
import json
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import django_filters
import pytest
from admin_app.admin import ItemAdmin, LowStockFilter, PartInline, ReviewInline
from admin_app.models import Category, Item, Note, Part, Review, Tag
from bs4 import BeautifulSoup
from django import forms
from django.contrib import admin as django_admin
from django.contrib.admin import EmptyFieldListFilter, RelatedOnlyFieldListFilter, ShowFacets
from django.contrib.admin import widgets as django_widgets
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.admin import GenericTabularInline as DjangoGenericTabularInline
from django.core import checks
from django.core.paginator import Paginator
from django.db import connection, models
from django.db.models import FETCH_PEERS, Count
from django.db.models.functions import Upper
from django.db.models.signals import post_init
from django.http import HttpResponse
from django.test.utils import CaptureQueriesContext
from django.urls import path, reverse
from django.utils import timezone, translation
from django.utils.html import format_html
from django_nplus1.exceptions import NPlus1Error

from django_formwork import DisplayField, __version__, admin
from django_formwork.admin import ActionLocation, site
from django_formwork.admin.checks import check_model_admin
from django_formwork.admin.contenttypes import GenericStackedInline
from django_formwork.admin.helpers import FIRST_OBJECTS
from django_formwork.admin.info import describe_fields, describe_search, describe_table
from django_formwork.admin.models import HistoryEntry
from django_formwork.admin.paginator import page_links
from django_formwork.admin.widgets import RELATION_SEARCH_KEY, AdminDateWidget
from django_formwork.forms import FormworkModelForm
from django_formwork.formsets import FormworkBaseInlineFormSet, FormworkBaseModelFormSet
from django_formwork.search import SEARCH_PAGE_SIZE
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
        ("history_list", ()),
        ("delete", (obj.pk,)),
    ]:
        assert admin_client.get(url(model, view, *args)).status_code == 200, view


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [("index", {}), ("app_list", {"app_label": "admin_app"}), ("password_change", {}), ("password_change_done", {})],
)
def test_site_pages_render(admin_client, name, kwargs):
    assert admin_client.get(reverse(f"admin:{name}", kwargs=kwargs)).status_code == 200


@pytest.fixture
def support_client(client, django_user_model):
    user = django_user_model.objects.create_user("helper")
    user.groups.add(Group.objects.create(name="Support"))
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="admin_app"))
    client.force_login(user)
    return client


@pytest.mark.parametrize(
    ("client_fixture", "site_name", "status"),
    [("support_client", "support", 200), ("support_client", "admin", 302), ("admin_client", "support", 302)],
)
def test_second_site_admits_only_the_users_its_has_permission_names(request, client_fixture, site_name, status):
    client = request.getfixturevalue(client_fixture)

    assert client.get(reverse(f"{site_name}:index")).status_code == status


@pytest.mark.parametrize("name", ["index", "admin_app_item_changelist", "admin_app_item_change"])
def test_second_site_links_to_its_own_pages(support_client, catalog, name):
    page = reverse(f"support:{name}", args=[catalog.alpha.pk] if name.endswith("_change") else [])

    soup = BeautifulSoup(support_client.get(page).content, "html.parser")

    links = [a["href"] for a in soup.select("a[href^='/']") if not a["href"].startswith("/static/")]
    assert any(link.startswith("/support/admin_app/") for link in links)
    assert not [link for link in links if link.startswith("/admin/")]


@pytest.mark.parametrize(
    ("view", "status"),
    [("support:index", 200), ("support:admin_app_item_changelist", 200), ("support:admin_app_item_add", 403)],
)
def test_second_site_grants_its_models_without_model_permissions(client, django_user_model, view, status):
    user = django_user_model.objects.create_user("helper", is_staff=True)
    user.groups.add(Group.objects.create(name="Support"))
    client.force_login(user)

    response = client.get(reverse(view))

    assert response.status_code == status
    assert (b'href="/support/admin_app/item/"' in response.content) is (status == 200)
    assert client.get(reverse("admin:admin_app_item_changelist")).status_code == 403


@pytest.mark.parametrize(("site_name", "status"), [("support", 200), ("admin", 403)])
def test_relation_search_follows_the_access_rule_of_its_site(support_client, catalog, site_name, status):
    params = {"widget": "select", "site": site_name, "model": "admin_app.item", "field": "category", "q": "kit"}

    response = support_client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    assert response.status_code == status


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


@pytest.mark.parametrize(
    ("favicon", "href"),
    [
        ("formwork_admin/favicon.svg", "/static/formwork_admin/favicon.svg"),
        ("https://cdn.example.com/icon.png", "https://cdn.example.com/icon.png"),
        (None, None),
    ],
)
def test_pages_link_the_site_favicon(client, monkeypatch, favicon, href):
    monkeypatch.setattr(site, "favicon", favicon)

    soup = BeautifulSoup(client.get(reverse("admin:login")).content, "html.parser")

    icon = soup.find("link", rel="icon")
    assert (icon and icon["href"]) == href


def test_default_scripts_are_the_htmx_and_alpine_versions_the_tests_run():
    pins = json.loads((Path(__file__).parent.parent / "package.json").read_text())["devDependencies"]

    assert set(re.findall(r"htmx\.org@([^/]+)/", " ".join(admin.AdminSite.scripts))) == {pins["htmx.org"]}
    assert re.findall(r"alpinejs@([^/]+)/", admin.AdminSite.alpine_script) == [pins["alpinejs"]]


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
    assert soup.select_one("#changelist-filter-bar a[data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.parametrize(
    ("isnull", "shown", "hidden"), [("True", b"Beta lamp", b"Alpha kettle"), ("False", b"Alpha kettle", b"Beta lamp")]
)
def test_date_filter_picks_the_rows_without_a_date_or_with_one(admin_client, catalog, isnull, shown, hidden):
    response = admin_client.get(url(Item, "changelist"), {"released__isnull": isnull})
    soup = BeautifulSoup(response.content, "html.parser")

    assert shown in response.content
    assert hidden not in response.content
    assert soup.find("input", attrs={"name": "released__isnull"})["value"] == isnull
    assert soup.select_one("#changelist-filter-bar a[data-clear-filters]")["href"] == url(Item, "changelist")


@pytest.mark.parametrize(
    ("params", "marked"),
    [
        ({}, []),
        ({"q": "kettle"}, []),
        ({"status__exact": "archived", "tags__isnull": "True"}, ["status__exact", "tags__id__exact"]),
    ],
    ids=["unfiltered", "search_only", "filtered"],
)
def test_only_a_filter_with_a_value_carries_the_mark(admin_client, catalog, params, marked):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    assert [filter_["data-filter"] for filter_ in soup.select("[data-filter].formwork-dirty")] == marked


def test_clear_all_filters_keeps_the_search(admin_client, catalog):
    soup = BeautifulSoup(
        admin_client.get(url(Item, "changelist"), {"status__exact": "archived", "q": "kettle"}).content, "html.parser"
    )

    assert soup.select_one("#changelist-filter-bar a[data-clear-filters]")["href"] == "?q=kettle"


@pytest.mark.parametrize(
    ("params", "links"),
    [
        ({"q": "nothing"}, {"search": None}),
        ({"status__exact": "draft", "is_featured__exact": "1"}, {"filters": None}),
        ({"status__exact": "archived", "q": "nothing"}, {"search": "?status__exact=archived", "filters": "?q=nothing"}),
    ],
    ids=["search", "filters", "both"],
)
def test_empty_list_offers_to_clear_what_narrows_it(admin_client, catalog, params, links):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    empty = soup.select_one("#changelist-table tr[data-empty]")
    found = {name: empty.select_one(f"[data-clear-{name}]") for name in ("search", "filters")}
    expected = {name: href or url(Item, "changelist") for name, href in links.items()}
    assert {name: link["href"] for name, link in found.items() if link is not None} == expected


def test_clear_all_filters_keeps_other_lookups(admin_client, catalog):
    response = admin_client.get(url(Item, "changelist"), {"status__exact": "archived", "name__startswith": "Alpha"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert soup.select_one("#changelist-filter-bar a[data-clear-filters]")["href"] == "?name__startswith=Alpha"
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
    assert soup.select_one("#changelist-filter-bar a[aria-disabled=true]").get("href") is None


def test_filters_keep_the_list_filter_order_in_the_row_and_in_the_menu(admin_client, catalog, monkeypatch):
    list_filter = [LowStockFilter, "status", django_filters.RangeFilter(field_name="quantity"), "category"]
    monkeypatch.setattr(site.get_model_admin(Item), "list_filter", list_filter)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    names = ["stock", "status__exact", "quantity", "category__id__exact"]
    assert [filter_["data-filter"] for filter_ in soup.select("#changelist-filter-bar [data-filter]")] == names
    items = soup.select("#changelist-filter-bar [data-more-item]")
    assert [item["data-more-item"] for item in items] == names
    assert [item.get_text(strip=True) for item in items] == ["Stock", "Status", "Quantity", "Category"]


@pytest.fixture
def loaded_items():
    loaded = []

    def collect(sender, instance, **kwargs):
        loaded.append(instance)

    post_init.connect(collect, sender=Item)
    yield loaded
    post_init.disconnect(collect, sender=Item)


def test_simple_list_filter_loads_no_rows_past_the_page(admin_client, catalog, monkeypatch, loaded_items):
    monkeypatch.setattr(site.get_model_admin(Item), "list_per_page", 1)

    admin_client.get(url(Item, "changelist"))

    assert {item.pk for item in loaded_items if item.pk is not None} == {catalog.beta.pk}


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
    Category.objects.create(name="Archive", slug="archive")
    Category.objects.create(name="Basement", slug="basement")
    category_admin = site.get_model_admin(Category)
    monkeypatch.setattr(category_admin, "ordering", ["-name"])
    monkeypatch.setattr(category_admin, "choice_queryset", lambda queryset: queryset.exclude(slug="basement"))
    monkeypatch.setattr(Item._meta.get_field("category").remote_field, "limit_choices_to", ~models.Q(slug="archive"))

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    offered = [value for value in option_texts(soup, "category__id__exact") if value not in {"", "null"}]
    assert offered == [str(catalog.office.pk), str(catalog.kitchen.pk)]


def test_empty_relation_option_reads_and_writes_django_isnull(admin_client, catalog):
    response = admin_client.get(url(Item, "changelist"), {"tags__isnull": "True"})
    soup = BeautifulSoup(response.content, "html.parser")

    assert b"Beta lamp" in response.content
    assert b"Alpha kettle" not in response.content
    assert soup.find("input", attrs={"name": "tags__id__exact"})["value"] == "null"
    assert soup.select_one("#changelist-filter-bar a[data-clear-filters]")["href"] == url(Item, "changelist")


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


@admin.display(description="Parts", ordering="num_parts", annotate={"num_parts": Count("parts")})
def part_count(obj):
    return obj.num_parts


@admin.display(description="Parts", ordering="-num_parts", annotate={"num_parts": Count("parts")})
def part_count_most_first(obj):
    return obj.num_parts


@admin.display(description="Tags", annotate={"num_tags": Count("tags")})
def tag_count(obj):
    return obj.num_tags


@admin.display(description="Label", annotate={"label": Upper("name")})
def part_label(obj):
    return obj.label


@pytest.mark.parametrize(
    ("sort", "rows"),
    [
        ((part_count, "1"), ["Beta lamp 0", "Alpha kettle 2"]),
        ((part_count, "-1"), ["Alpha kettle 2", "Beta lamp 0"]),
        ((part_count_most_first, "1"), ["Alpha kettle 2", "Beta lamp 0"]),
    ],
    ids=["ascending", "descending", "descending-ordering"],
)
def test_display_annotation_shows_each_rows_value_and_sorts_by_it(admin_client, catalog, monkeypatch, sort, rows):
    column, order = sort
    Part.objects.create(item=catalog.alpha, name="Handle")
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", column])
    monkeypatch.setattr(site.get_model_admin(Item), "actions", None)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), {"o": order}).content, "html.parser")

    assert [row.get_text(" ", strip=True) for row in soup.select(LIST_ROWS)] == rows


def test_display_annotations_of_two_columns_do_not_multiply_each_other(admin_client, catalog, monkeypatch):
    Part.objects.create(item=catalog.alpha, name="Handle")
    catalog.alpha.tags.add(Tag.objects.create(name="new"))
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", part_count, tag_count])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert "Alpha kettle 2 2" in [row.get_text(" ", strip=True) for row in soup.select(LIST_ROWS)]


def test_display_annotation_computes_for_the_page_rows_in_one_query(admin_client, catalog, monkeypatch):
    """The count and the page's own query leave the annotation out."""
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", part_count])
    monkeypatch.setattr(site.get_model_admin(Item), "list_per_page", 2)
    Item.objects.create(name="Gamma mug", category=catalog.kitchen)

    with CaptureQueriesContext(connection) as queries:
        admin_client.get(url(Item, "changelist"))

    assert len([query for query in queries if '"admin_app_part"' in query["sql"]]) == 1


def test_display_annotation_shows_in_the_read_only_fields_of_the_form_and_its_inline_rows(
    admin_client, catalog, monkeypatch
):
    Part.objects.create(item=catalog.alpha, name="Handle")
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", None)
    monkeypatch.setattr(site.get_model_admin(Item), "readonly_fields", ["created", part_count])
    monkeypatch.setattr(PartInline, "readonly_fields", [part_label])

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    legend = soup.find("span", class_="fieldset-legend", string="Parts")
    assert legend.find_next_sibling("div").get_text(strip=True) == "2"
    assert {"LID", "HANDLE"} <= set(soup.select_one("#parts-group").get_text(" ", strip=True).split())


class ItemSummaryForm(FormworkModelForm):
    summary = DisplayField(source=lambda item: f"{item.name} in {item.category}")


@pytest.mark.parametrize("readonly_fields", [["created"], ["created", "summary"]], ids=["declared", "listed"])
def test_a_display_field_of_the_admin_form_shows_with_the_read_only_fields(
    admin_client, catalog, monkeypatch, readonly_fields
):
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", None)
    monkeypatch.setattr(site.get_model_admin(Item), "readonly_fields", readonly_fields)
    monkeypatch.setattr(site.get_model_admin(Item), "form", ItemSummaryForm)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    legend = soup.find("span", class_="fieldset-legend", string="Summary")
    assert legend.find_next_sibling("div").get_text(strip=True) == "Alpha kettle in Kitchen"
    assert len(soup.find_all("span", class_="fieldset-legend", string="Created")) == 1


@pytest.mark.parametrize(
    ("codenames", "name"), [(("view_item", "change_item"), "created"), (("view_item",), "name")], ids=["read", "view"]
)
def test_change_form_holds_each_read_only_value_as_a_display_field(rf, django_user_model, catalog, codenames, name):
    user = django_user_model.objects.create_user("staff", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    request = rf.get("/")
    request.user = user

    form = site.get_model_admin(Item).get_form(request, catalog.alpha, change=True)

    assert isinstance(form.base_fields[name], DisplayField)


@admin.display(description="Number")
def part_number(obj):
    return f"#{obj.pk}"


def test_a_blank_inline_row_shows_no_value_for_a_read_only_field(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(PartInline, "readonly_fields", [part_number])

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    parts = soup.select_one("#parts-group").get_text(" ", strip=True)
    assert f"#{catalog.lid.pk}" in parts
    assert "#None" not in parts


def test_inline_form_holds_each_read_only_value_as_a_display_field(admin_request, catalog, monkeypatch):
    monkeypatch.setattr(PartInline, "readonly_fields", [part_number])

    formset = PartInline(Item, site).get_formset(admin_request, catalog.alpha)

    assert isinstance(formset.form.base_fields["part_number"], DisplayField)


@admin.display(description="Blurb", max_lines=2)
def blurb(obj):
    return f"{obj.name} " * 40


def test_a_value_with_max_lines_is_cut_in_the_list_and_on_the_change_form(admin_client, catalog, monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "list_display", ["name", blurb])
    monkeypatch.setattr(model_admin, "fieldsets", None)
    monkeypatch.setattr(model_admin, "readonly_fields", ["created", blurb])

    listed = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    changed = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    cells = listed.select("#changelist-table tbody td .formwork-clamp-body")
    assert len(cells) == Item.objects.count()
    assert all("line-clamp-2" in cell["class"] for cell in cells)
    legend = changed.find("span", class_="fieldset-legend", string="Blurb")
    assert "line-clamp-2" in legend.find_next_sibling("div").select_one(".formwork-clamp-body")["class"]


def test_display_rejects_max_lines_outside_the_clamped_counts():
    with pytest.raises(ValueError, match="max_lines"):
        admin.display(max_lines=11)(lambda obj: obj)


class PartNoteForm(FormworkModelForm):
    note = DisplayField(source=lambda part: f"Note on {part.name}")


def test_an_inline_leaves_out_a_display_field_that_its_fields_leave_out(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(PartInline, "form", PartNoteForm)
    monkeypatch.setattr(PartInline, "fields", ["name", "quantity"])

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert "Note on" not in soup.select_one("#parts-group").get_text()


def test_changelist_shows_the_choice_label_in_a_column_that_follows_a_relation(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_display", ["name", "category__slug"])
    monkeypatch.setattr(Category._meta.get_field("slug"), "choices", [("kitchen", "Kitchenware"), ("office", "Desk")])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert "Kitchenware" in soup.select_one(f"tr[data-pk='{catalog.alpha.pk}']").get_text()


@pytest.mark.parametrize(
    ("fetch_mode", "expectation"),
    [(FETCH_PEERS, contextlib.nullcontext()), (None, pytest.raises(NPlus1Error))],
    ids=["peers", "manager"],
)
def test_changelist_loads_a_relation_of_its_columns_for_all_rows_at_once(
    admin_client, catalog, monkeypatch, fetch_mode, expectation
):
    item_admin = site.get_model_admin(Item)
    monkeypatch.setattr(item_admin, "list_display", ["name", "category", "category__slug"])
    monkeypatch.setattr(item_admin, "fetch_mode", fetch_mode)

    with expectation:
        admin_client.get(url(Item, "changelist"))


def test_changelist_pages_rows(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_per_page", 1)

    content = admin_client.get(url(Item, "changelist"), {"p": 2}).content

    assert b"Alpha kettle" in content
    assert b"Beta lamp" not in content


def pages(links, *, narrow):
    return [link.page for link in links if (link.narrow if narrow else link.wide)]


@pytest.mark.parametrize(
    ("number", "wide", "narrow"),
    [
        (7, [1, None, 5, 6, 7, 8, 9, None, 13], [1, None, 7, None, 13]),
        (4, [1, 2, 3, 4, 5, 6, None, 13], [1, None, 4, None, 13]),
        (12, [1, None, 10, 11, 12, 13], [1, None, 12, 13]),
    ],
)
def test_page_links_on_a_phone_keep_the_first_current_and_last_page(number, wide, narrow):
    links = page_links(Paginator(range(13), 1), number)

    assert pages(links, narrow=False) == wide
    assert pages(links, narrow=True) == narrow


@pytest.mark.parametrize(("per_page", "offered"), [("2", True), ("all", True), ("3", False), ("x", False)])
def test_changelist_shows_an_offered_page_size_and_keeps_it_in_its_links(
    admin_client, catalog, monkeypatch, per_page, offered
):
    """A size the admin does not offer shows the admin's own size, and the links drop it."""
    item_admin = site.get_model_admin(Item)
    monkeypatch.setattr(item_admin, "list_per_page", 1)
    monkeypatch.setattr(item_admin, "list_per_page_options", (2,))

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), {"per_page": per_page}).content, "html.parser")

    assert len(soup.select("#changelist-table tbody tr[data-pk]")) == (2 if offered else 1)
    sort_link = soup.select_one("#changelist-table thead th[data-col] a[href*='o=']")["href"]
    assert (f"per_page={per_page}" in sort_link) is offered


@pytest.mark.parametrize(("options", "sizes"), [((2,), ["1", "2", "all"]), ((), [])])
def test_changelist_offers_the_page_sizes_next_to_the_pages(admin_client, catalog, monkeypatch, options, sizes):
    """Without sizes, the list keeps Django's Show all link."""
    item_admin = site.get_model_admin(Item)
    monkeypatch.setattr(item_admin, "list_per_page", 1)
    monkeypatch.setattr(item_admin, "list_per_page_options", options)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    footer = soup.find(id="changelist-footer")
    assert [option["data-value"] for option in footer.select("[role=option] [data-value]")] == sizes
    assert (footer.find("a", string="Show all") is None) is bool(sizes)


def test_changelist_offers_no_page_size_while_every_size_shows_all_rows(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select("#changelist-footer [role=option]") == []


@pytest.mark.parametrize(
    ("options", "parts"),
    [
        ({"actions": ["mark_active"], "list_editable": ["quantity"]}, [True, True]),
        ({"actions": None, "list_editable": ["quantity"]}, [False, True]),
        ({"actions": ["mark_active"], "list_editable": []}, [True, False]),
        ({"actions": None, "list_editable": []}, None),
    ],
)
def test_changelist_toolbar_holds_the_actions_and_the_save_the_list_has(
    admin_client, catalog, monkeypatch, options, parts
):
    """A list without actions and without editable cells has no toolbar."""
    item_admin = site.get_model_admin(Item)
    for name, value in options.items():
        monkeypatch.setattr(item_admin, name, value)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    toolbar = soup.find(id="changelist-toolbar")
    found = toolbar and [
        toolbar.find(id="changelist-actions") is not None,
        toolbar.find(attrs={"data-save-bar": True}) is not None,
    ]
    assert found == parts
    assert toolbar is None or toolbar.find_next("table")["id"] == "changelist-table"


@pytest.mark.parametrize(
    ("view", "select"),
    [("change", "#id_status_wrapper"), ("changelist", "#id_status__exact_wrapper")],
    ids=["form", "filter"],
)
def test_select_of_a_choice_field_shows_the_badges_of_the_list(admin_client, catalog, view, select):
    args = [catalog.alpha.pk] if view == "change" else []
    soup = BeautifulSoup(admin_client.get(url(Item, view, *args)).content, "html.parser")

    rows = soup.select(f"{select} [role=option] > [data-value]:has(.badge)")
    assert {row["data-value"]: row.select_one(".badge")["class"][2:] for row in rows} == {
        "draft": ["badge-ghost"],
        "active": ["badge-soft", "badge-success"],
        "archived": ["badge-soft", "badge-warning"],
    }


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


@pytest.mark.parametrize("editable", [["quantity"], []])
def test_changelist_gives_each_row_a_body_with_its_own_id(admin_client, catalog, monkeypatch, editable):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", editable)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    ids = [row.find_parent("tbody").get("id") for row in soup.select("#changelist-table tr[data-pk]")]
    assert None not in ids
    assert len(set(ids)) == len(ids) > 1


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


def test_button_action_shows_next_to_the_menu_and_the_menu_shows_help_text(admin_client, catalog, monkeypatch):
    @admin.action(help_text="Sets the status.")
    def describe(modeladmin, request, queryset):
        pass

    monkeypatch.setattr(ItemAdmin, "actions", [status_action(button=True), describe])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one('[role="menu"] button[value="set_status"]') is None
    assert "Sets the status." in soup.select_one('[role="menu"] button[value="describe"]').get_text()


@pytest.mark.parametrize("across", [False, True], ids=["selected", "across"])
def test_confirm_action_asks_on_a_page_before_it_runs(admin_client, catalog, monkeypatch, across):
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(confirm="Activate %(count)s %(name)s?")])
    selection = {"select_across": "1"} if across else {"_selected_action": [catalog.beta.pk]}
    data = {"action": "set_status", **selection}

    asked = admin_client.post(url(Item, "changelist"), data)

    assert asked.status_code == 200
    assert ("Activate 2 items?" if across else "Activate 1 item?") in asked.content.decode()
    assert not Item.objects.filter(status=Item.Status.ACTIVE).exists()

    admin_client.post(url(Item, "changelist"), {**data, "post": "yes"})

    assert Item.objects.filter(status=Item.Status.ACTIVE).count() == (2 if across else 1)


def test_form_action_runs_with_the_valid_form_only(admin_client, catalog, monkeypatch):
    class RestockForm(forms.Form):
        quantity = forms.IntegerField(min_value=1)

    @admin.action(form=RestockForm)
    def restock(modeladmin, request, queryset, form):
        queryset.update(quantity=form.cleaned_data["quantity"])

    monkeypatch.setattr(ItemAdmin, "actions", [restock])
    data = {"action": "restock", "_selected_action": [catalog.beta.pk], "post": "yes"}

    invalid = admin_client.post(url(Item, "changelist"), {**data, "action-quantity": "0"})
    assert invalid.status_code == 200
    assert b"greater than or equal to 1" in invalid.content
    assert Item.objects.get(pk=catalog.beta.pk).quantity != 7

    admin_client.post(url(Item, "changelist"), {**data, "action-quantity": "7"})
    assert Item.objects.get(pk=catalog.beta.pk).quantity == 7
    assert Item.objects.get(pk=catalog.alpha.pk).quantity != 7


def test_change_form_confirm_action_runs_after_the_page_and_returns_to_the_row(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "actions", [status_action(confirm=True, location=ActionLocation.CHANGE_FORM)])

    asked = run_on_change_form(admin_client, catalog.alpha, "set_status")
    soup = BeautifulSoup(asked.content, "html.parser")

    assert asked.status_code == 200
    assert soup.select_one('input[name="CHANGE_FORM-action"]')["value"] == "set_status"
    assert not Item.objects.filter(status=Item.Status.ACTIVE).exists()

    response = admin_client.post(
        url(Item, "change", catalog.alpha.pk),
        {"CHANGE_FORM-action": "set_status", "_selected_action": [catalog.alpha.pk], "post": "yes"},
    )

    assert response["Location"] == url(Item, "change", catalog.alpha.pk)
    assert Item.objects.get(pk=catalog.alpha.pk).status == Item.Status.ACTIVE


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


def test_delete_selected_refuses_a_row_that_its_admin_keeps(admin_client, catalog, monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "has_delete_permission", lambda request, obj=None: obj != catalog.beta)
    data = {"action": "delete_selected", "_selected_action": [catalog.alpha.pk, catalog.beta.pk]}

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")
    response = admin_client.post(url(Item, "changelist"), {**data, "post": "yes"})

    assert soup.find("input", {"name": "post"}) is None
    assert response.status_code == 403
    assert Item.objects.filter(pk__in=[catalog.alpha.pk, catalog.beta.pk]).count() == 2


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


def test_list_editable_cell_control_is_described_by_its_help_and_its_error(admin_client, catalog, monkeypatch):
    class HelpForm(forms.ModelForm):
        class Meta:
            model = Item
            fields = ["quantity"]
            help_texts = {"quantity": "Units in stock."}

    monkeypatch.setattr(site.get_model_admin(Item), "form", HelpForm)
    data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "-1", "_save": "1"}

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")

    control = soup.select_one('input[name="form-0-quantity"]')
    help_text, error = (soup.find(id=ref) for ref in control["aria-describedby"].split())
    assert "stock" in help_text.get_text()
    assert "greater than" in error.get_text()


def test_list_editable_failed_save_counts_the_errors_above_the_list(admin_client, catalog):
    page = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    first, second = (page.find("input", attrs={"name": f"form-{i}-id"})["value"] for i in range(2))
    data = {
        **management("form", 2, 2),
        "form-0-id": first,
        "form-0-quantity": "-1",
        "form-1-id": second,
        "form-1-quantity": "-2",
        "_save": "1",
    }

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")

    assert "2 errors" in soup.select_one("#changelist [role=alert]").get_text()


def test_list_editable_row_error_shows_above_its_row(admin_client, catalog, monkeypatch):
    class ClashForm(forms.ModelForm):
        def clean(self):
            raise forms.ValidationError("This quantity clashes with the category.")

    monkeypatch.setattr(site.get_model_admin(Item), "form", ClashForm)
    data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "7", "_save": "1"}

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), data).content, "html.parser")

    row = soup.select_one(f'#changelist-table tr[data-pk="{catalog.alpha.pk}"]')
    assert "clashes" in row.find_previous_sibling("tr").get_text()


def test_list_editable_failed_save_keeps_every_change_marked(admin_client, catalog):
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
    assert [cell.find("input")["name"] for cell in marked] == ["form-0-quantity", "form-1-quantity"]


@pytest.mark.parametrize("posted", [False, True])
def test_list_editable_cell_is_the_field_cell_of_a_formset_row(admin_client, catalog, monkeypatch, posted):
    """The list writes out the field cells of ``formwork/tables/row.html``, with their marks and errors."""
    columns = ["category", "status", "price", "quantity", "is_featured", "released"]
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", columns)
    if posted:
        data = {**management("form", 1, 1), "form-0-id": catalog.alpha.pk, "form-0-quantity": "-1", "_save": "1"}
        response = admin_client.post(url(Item, "changelist"), data)
    else:
        response = admin_client.get(url(Item, "changelist"))
    row = next(row for row in response.context_data["cl"].rows if row["form"].instance == catalog.alpha)
    form = row["form"]
    for name in columns:
        form.fields[name].cell_cache = None
    form.template_name_row = "formwork/tables/row.html"

    listed = BeautifulSoup(response.content, "html.parser").find(id=row["row_id"])
    alone = BeautifulSoup(form.as_row(), "html.parser")

    def cell(soup, name):
        td = soup.select_one(f'td[data-field="{name}"]')
        marks = {key: value for key, value in td.attrs.items() if key.startswith(("data-formwork", "data-invalid"))}
        return marks, " ".join(td.decode_contents().split())

    assert [cell(listed, name) for name in columns] == [cell(alone, name) for name in columns]
    assert form.errors if posted else not form.is_bound


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


@pytest.fixture
def paged_parts(catalog, monkeypatch):
    monkeypatch.setattr(PartInline, "per_page", 2)
    return [Part.objects.create(item=catalog.beta, name=f"Part {n}") for n in range(5)]


def shown_pks(response, prefix="parts"):
    group = BeautifulSoup(response.content, "html.parser").select_one(f"#{prefix}-group")
    return [int(field["value"]) for field in group.select(f"input[name^='{prefix}-'][name$='-id'][value]")]


@pytest.mark.parametrize(
    ("number", "shown"), [("2", [2, 3]), ("99", [4]), ("x", [0, 1])], ids=["page", "past-the-end", "not-a-number"]
)
def test_inline_shows_the_saved_rows_of_one_page(admin_client, paged_parts, number, shown):
    response = admin_client.get(url(Item, "change", paged_parts[0].item_id), {"parts-page": number})

    assert shown_pks(response) == [paged_parts[index].pk for index in shown]


def test_inline_without_per_page_shows_every_saved_row(admin_client, paged_parts, monkeypatch):
    monkeypatch.setattr(PartInline, "per_page", None)

    response = admin_client.get(url(Item, "change", paged_parts[0].item_id))

    assert shown_pks(response) == [part.pk for part in paged_parts]


@pytest.mark.parametrize(
    ("inline", "create", "shown"),
    [
        (PartInline, lambda item, n: Part.objects.create(item=item, name=f"Part {n}"), 10),
        (ReviewInline, lambda item, n: Review.objects.create(item=item, author=f"Author {n}"), 5),
    ],
    ids=["tabular", "stacked"],
)
def test_inline_pages_its_saved_rows_by_default(admin_client, catalog, inline, create, shown):
    for n in range(12):
        create(catalog.beta, n)

    response = admin_client.get(url(Item, "change", catalog.beta.pk))

    assert len(shown_pks(response, f"{inline.model._meta.model_name}s")) == shown


@pytest.mark.parametrize(
    ("inline", "create"),
    [
        (PartInline, lambda item, n: Part.objects.create(item=item, name=f"Part {n}")),
        (ReviewInline, lambda item, n: Review.objects.create(item=item, author=f"Author {n}")),
    ],
    ids=["tabular", "stacked"],
)
def test_paged_inline_links_to_its_other_pages(admin_client, catalog, monkeypatch, inline, create):
    monkeypatch.setattr(inline, "per_page", 2)
    for n in range(5):
        create(catalog.beta, n)
    prefix = f"{inline.model._meta.model_name}s"

    response = admin_client.get(url(Item, "change", catalog.beta.pk), {f"{prefix}-page": "2"})

    pager = BeautifulSoup(response.content, "html.parser").select_one(f"#{prefix}-group [data-inline-pages]")
    assert pager.select_one("[aria-current=page]").get_text(strip=True) == "2"
    assert pager.select_one(f"a[href$='?{prefix}-page=3']") is not None
    assert "5" in pager.get_text()


def page_two(catalog, parts, **fields):
    rows = {}
    for index, (part, name) in enumerate([(parts[2], "Leg"), (parts[3], "Foot")]):
        rows |= {
            f"parts-{index}-id": part.pk,
            f"parts-{index}-item": catalog.beta.pk,
            f"parts-{index}-name": name,
            f"parts-{index}-quantity": "1",
        }
    beta = catalog.beta
    return item_data(
        catalog.office, name=beta.name, quantity="50", **management("parts", total=2, initial=2), **rows, **fields
    )


def test_paged_inline_saves_the_rows_it_posted_and_keeps_the_other_pages(admin_client, catalog, paged_parts):
    response = admin_client.post(
        url(Item, "change", catalog.beta.pk), page_two(catalog, paged_parts, **{"parts-1-DELETE": "on"})
    )

    assert response.status_code == 302
    assert list(catalog.beta.parts.order_by("pk").values_list("name", flat=True)) == [
        "Part 0",
        "Part 1",
        "Leg",
        "Part 4",
    ]


def test_save_and_continue_comes_back_at_the_inline_page(admin_client, catalog, paged_parts):
    change = url(Item, "change", catalog.beta.pk)

    response = admin_client.post(f"{change}?parts-page=2", page_two(catalog, paged_parts, _continue="1"))

    assert response["location"] == f"{change}?parts-page=2"


def test_paged_inline_leaves_the_last_page_the_share_of_max_num_and_the_blank_rows(
    admin_client, catalog, paged_parts, monkeypatch
):
    monkeypatch.setattr(PartInline, "max_num", 6)
    change = url(Item, "change", catalog.beta.pk)

    tables = [
        BeautifulSoup(admin_client.get(change, {"parts-page": page}).content, "html.parser").select_one("#parts-table")
        for page in (1, 3)
    ]

    assert [table["data-max"] for table in tables] == ["3", "2"]
    assert [table.select_one("[name=parts-TOTAL_FORMS]")["value"] for table in tables] == ["2", "2"]


def test_collapsed_inline_starts_open_at_a_page_its_url_names(admin_client, catalog, paged_parts, monkeypatch):
    monkeypatch.setattr(PartInline, "classes", ["collapse"])
    change = url(Item, "change", catalog.beta.pk)

    assert folded_inlines(admin_client.get(change)) == [("parts-group", False)]
    assert folded_inlines(admin_client.get(change, {"parts-page": "2"})) == [("parts-group", True)]


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


@pytest.mark.parametrize("view", ["changelist", "add", "change", "delete", "history_list"])
def test_admin_media_class_loads_on_every_page_of_the_admin(admin_client, catalog, monkeypatch, view):
    monkeypatch.setattr(ItemAdmin, "Media", ExtraMedia, raising=False)
    args = [] if view in ("changelist", "add", "history_list") else [catalog.alpha.pk]

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


def test_datetime_field_saves_the_day_and_the_time_it_posts(admin_client, catalog, monkeypatch):
    fields = ["name", "slug", "category", "status", "price", "quantity", "available_from"]
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": fields})])

    admin_client.post(url(Item, "add"), item_data(catalog.office, available_from="2026-03-01T09:30"))

    assert Item.objects.get(name="Gamma desk").available_from == datetime(
        2026, 3, 1, 9, 30, tzinfo=timezone.get_current_timezone()
    )


def datetime_inputs(content):
    soup = BeautifulSoup(content, "html.parser")
    return soup.select_one("#id_available_from")["value"], soup.select_one('input[name="available_from"]')["value"]


@pytest.mark.parametrize(
    ("saved", "posted"),
    [(time(9, 30), "2026-03-01T09:30"), (time(9, 30, 15), "2026-03-01T09:30:15")],
    ids=["minute", "second"],
)
def test_datetime_field_posts_seconds_only_for_a_time_with_seconds(admin_client, catalog, monkeypatch, saved, posted):
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": ["name", "available_from"]})])
    catalog.beta.available_from = datetime.combine(date(2026, 3, 1), saved, tzinfo=timezone.get_current_timezone())
    catalog.beta.save()

    shown = datetime_inputs(admin_client.get(url(Item, "change", catalog.beta.pk)).content)

    assert shown == ("2026-03-01 09:30", posted)


def test_datetime_field_keeps_the_seconds_of_a_form_with_errors(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": ["name", "available_from"]})])

    data = {"name": "", "available_from": "2026-03-01T09:30:15"}
    shown = datetime_inputs(admin_client.post(url(Item, "change", catalog.beta.pk), data).content)

    assert shown == ("2026-03-01 09:30", "2026-03-01T09:30:15")


@pytest.mark.parametrize(
    ("language", "text"), [("en", "2026-03-01 09:30"), ("de", "01.03.2026 09:30"), ("fr", "01/03/2026 09:30")]
)
def test_datetime_field_shows_the_languages_input_format(admin_client, catalog, monkeypatch, language, text):
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": ["name", "available_from"]})])
    catalog.beta.available_from = datetime(2026, 3, 1, 9, 30, tzinfo=timezone.get_current_timezone())
    catalog.beta.save()

    with translation.override(language):
        shown = datetime_inputs(admin_client.get(url(Item, "change", catalog.beta.pk)).content)

    assert shown == (text, "2026-03-01T09:30")


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


def test_split_datetime_field_saves_the_day_and_the_time_it_posts(admin_client, catalog, monkeypatch):
    class SplitForm(FormworkModelForm):
        available_from = forms.SplitDateTimeField(widget=django_widgets.AdminSplitDateTime, required=False)

    fields = ["name", "slug", "category", "status", "price", "quantity", "available_from"]
    monkeypatch.setattr(site.get_model_admin(Item), "fieldsets", [(None, {"fields": fields})])
    monkeypatch.setattr(site.get_model_admin(Item), "form", SplitForm)

    admin_client.post(url(Item, "add"), item_data(catalog.office, available_from="2026-03-01T09:30"))

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


def save_ways(soup):
    return [soup.select_one("[data-save]")["name"]] + [
        button["name"] for button in soup.select("[data-save-bar] [role=menu] button")
    ]


def test_save_button_holds_the_other_ways_to_save_in_a_menu(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert save_ways(soup) == ["_save", "_continue", "_addanother"]
    assert soup.select("[data-save-bar] a")[-1]["href"] == url(Item, "delete", catalog.alpha.pk)


def test_save_as_replaces_save_and_add_another(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "save_as", True)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert save_ways(soup) == ["_save", "_continue", "_saveasnew"]


@pytest.mark.parametrize(
    ("posts", "view", "expected"),
    [
        ([{"_continue": "1"}], "change", ["_continue", "_save", "_addanother"]),
        ([{"_addanother": "1"}], "change", ["_addanother", "_save", "_continue"]),
        ([{"_continue": "1"}], "add", ["_save", "_continue", "_addanother"]),
        ([{"_continue": "1", "_shortcut": "1"}], "change", ["_save", "_continue", "_addanother"]),
        ([{"_continue": "1"}, {"_save": "1"}], "change", ["_save", "_continue", "_addanother"]),
        (
            [{"_continue": "1"}, {"_save": "1", "_popup": "1", "_to_field": "id"}],
            "change",
            ["_continue", "_save", "_addanother"],
        ),
    ],
    ids=["continue", "add another", "add form", "shortcut", "save", "dialog"],
)
def test_save_button_offers_the_way_the_form_was_last_saved(admin_client, catalog, posts, view, expected):
    for extra in posts:
        admin_client.post(url(Item, "change", catalog.alpha.pk), {**item_data(catalog.office), **extra})

    target = url(Item, "add") if view == "add" else url(Item, "change", catalog.alpha.pk)
    assert save_ways(BeautifulSoup(admin_client.get(target).content, "html.parser")) == expected


def test_save_as_new_is_never_offered_first(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "save_as", True)

    admin_client.post(url(Item, "change", catalog.alpha.pk), {**item_data(catalog.office), "_saveasnew": "1"})

    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")
    assert soup.select_one("[data-save]")["name"] == "_save"


def test_view_only_change_form_offers_close_instead_of_save(staff_client, catalog):
    soup = BeautifulSoup(staff_client("view_item").get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert soup.select_one("[data-save]") is None
    assert soup.find("a", string="Close")["href"] == url(Item, "changelist")


def test_add_without_change_permission_offers_save_and_view(staff_client, catalog):
    soup = BeautifulSoup(staff_client("add_item", "view_item").get(url(Item, "add")).content, "html.parser")

    assert "Save and view" in soup.select_one("[data-continue]").get_text()


def test_delete_confirmation_puts_the_confirm_button_first(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "delete", catalog.beta.pk)).content, "html.parser")

    controls = soup.select("[data-confirm-buttons] > *")
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

    listed = soup.select_one("details").get_text(" ", strip=True) if soup.select_one("details") else ""
    assert [word for word in ("kettle", "sale", "Lid", "1 more") if word in listed] == rows


def test_delete_confirmation_groups_the_objects_of_a_model(admin_client, catalog):
    Part.objects.bulk_create(Part(item=catalog.alpha, name=f"Leg {number}") for number in range(10))

    soup = BeautifulSoup(admin_client.get(url(Item, "delete", catalog.alpha.pk)).content, "html.parser")

    listed = soup.select_one("details").get_text(" ", strip=True)
    assert "Parts 11" in listed
    assert "and 3 more" in listed
    assert "Part:" not in listed


def test_delete_confirmation_names_only_the_objects_it_lists(admin_client, catalog, monkeypatch):
    Part.objects.bulk_create(Part(item=catalog.alpha, name=f"Leg {number}") for number in range(20))
    named = []
    monkeypatch.setattr(Part, "__str__", lambda part: named.append(part.pk) or part.name)

    admin_client.get(url(Item, "delete", catalog.alpha.pk))

    assert len(named) == FIRST_OBJECTS


@pytest.mark.parametrize(
    "tools",
    [
        {"search_fields": ["name"], "export_formats": (), "add": False},
        {"search_fields": [], "export_formats": ("csv",), "add": False},
        {"search_fields": [], "export_formats": (), "add": True},
        {"search_fields": [], "export_formats": (), "add": False},
    ],
    ids=["search", "export", "add", "none"],
)
def test_list_without_filters_shows_only_its_search_export_and_add_button(admin_client, catalog, monkeypatch, tools):
    model_admin = site.get_model_admin(Tag)
    monkeypatch.setattr(model_admin, "search_fields", tools["search_fields"])
    monkeypatch.setattr(model_admin, "export_formats", tools["export_formats"])
    monkeypatch.setattr(model_admin, "has_add_permission", lambda request: tools["add"])

    soup = BeautifulSoup(admin_client.get(url(Tag, "changelist")).content, "html.parser")

    assert (soup.select_one("#changelist-filter-bar input[name=q]") is not None) is bool(tools["search_fields"])
    assert (soup.select_one("#changelist-filter-bar [data-export]") is not None) is bool(tools["export_formats"])
    assert (soup.select_one("#changelist-filter-bar a[aria-label='Add tag']") is not None) is tools["add"]
    assert (soup.find(id="changelist-filter-bar") is not None) is any(tools.values())
    assert soup.select_one("#changelist-filters [data-filter-more]") is None
    assert soup.select_one("#changelist-filters a[aria-disabled]") is None


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

    assert b"Quantity" in admin_client.get(url(Item, "history", catalog.beta.pk), follow=True).content
    assert b"Beta lamp" in admin_client.get(reverse("admin:index")).content


def test_index_lists_a_recent_object_once_with_what_its_saves_changed(admin_client, catalog):
    for name in ("Beta lamp", "Beta light"):
        admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, name=name, quantity="9"))
    admin_client.post(url(Item, "add"), item_data(catalog.kitchen, slug="gamma"))

    rows = history_rows(admin_client.get(reverse("admin:index")), "[aria-labelledby=recent-actions] li")

    assert [row.split(".")[0] for row in rows][:1] == ["Gamma desk Added"]
    assert len(rows) == 2
    assert rows[1].startswith("Beta light Changed")
    assert {"Quantity", "Name"} <= set(rows[1].replace(",", " ").replace(".", " ").split())


LIST_ROWS = "#changelist-table tbody tr"


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

    newest = history_rows(admin_client.get(url(Item, "history", alpha.pk), follow=True), LIST_ROWS)[0]

    assert "Part “Lid” Quantity 1 → 2" in newest


def test_show_older_loads_the_next_entries(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "history_per_page", 1)
    for quantity in ("7", "8"):
        admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.office, quantity=quantity))
    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.beta.pk)).content, "html.parser")
    older = soup.select_one("#history button[hx-get]")["hx-get"]

    response = admin_client.get(older, headers={"HX-Request": "true"})

    assert b"<html" not in response.content
    assert "50 → 7" in history_rows(response, "li")[0]


@pytest.fixture
def changes(admin_client, catalog):
    admin_client.post(url(Item, "change", catalog.beta.pk), item_data(catalog.kitchen, name="Beta lamp", quantity="9"))
    admin_client.post(url(Item, "add"), item_data(catalog.kitchen, slug="gamma"))
    return catalog


def test_history_list_shows_the_changes_of_every_object_newest_first(admin_client, changes):
    rows = history_rows(admin_client.get(url(Item, "history_list")), LIST_ROWS)

    assert len(rows) == 2
    assert "Gamma desk" in rows[0]
    assert "Added" in rows[0]
    assert "Beta lamp" in rows[1]
    assert "50 → 9" in rows[1]
    assert "Office → Kitchen" in rows[1]


@pytest.mark.parametrize(("action", "name"), [("add", "Gamma desk"), ("change", "Beta lamp")])
def test_history_list_filters_by_action(admin_client, changes, action, name):
    rows = history_rows(admin_client.get(url(Item, "history_list"), {"action": action}), LIST_ROWS)

    assert len(rows) == 1
    assert name in rows[0]


def test_history_list_links_the_object_and_names_a_deleted_one(admin_client, changes):
    admin_client.post(url(Item, "delete", changes.alpha.pk))

    soup = BeautifulSoup(admin_client.get(url(Item, "history_list")).content, "html.parser")

    assert (
        soup.select_one(f'{LIST_ROWS} a[href="{url(Item, "change", changes.beta.pk)}"]').get_text(strip=True)
        == "Beta lamp"
    )
    deleted = soup.select_one(LIST_ROWS).get_text(" ", strip=True)
    assert "Alpha kettle (deleted)" in deleted
    assert "Deleted" in deleted


def test_show_all_in_the_panel_lists_the_changes_of_its_object(admin_client, changes):
    soup = BeautifulSoup(admin_client.get(url(Item, "change", changes.beta.pk)).content, "html.parser")
    show_all = next(link["href"] for link in soup.select("#history a") if link.get_text(strip=True) == "Show all")

    rows = history_rows(admin_client.get(show_all), LIST_ROWS)

    assert len(rows) == 1
    assert "50 → 9" in rows[0]


def test_history_list_exports_the_changes_as_text(admin_client, changes):
    response = admin_client.post(url(Item, "history_export"), {"format": "csv", "query": "action=change"})

    assert response["Content-Disposition"].startswith('attachment; filename="item-history-')
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["object_id"] == str(changes.beta.pk)
    assert rows[0]["action"] == "change"
    assert "Quantity: 50 → 9" in rows[0]["changes"]


@pytest.mark.parametrize(("codenames", "status"), [((), 403), (("view_item",), 200)])
def test_history_list_needs_the_view_permission_of_the_model(staff_client, changes, codenames, status):
    assert staff_client(*codenames).get(url(Item, "history_list")).status_code == status


def test_list_links_its_history_unless_the_admin_turns_it_off(admin_client, catalog, monkeypatch):
    history_link = f'#content a[href="{url(Item, "history_list")}"]'
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    assert soup.select(history_link)

    monkeypatch.setattr(ItemAdmin, "history_admin", None, raising=False)
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert not soup.select(history_link)
    assert admin_client.get(url(Item, "history_list")).status_code == 404


def test_history_admin_subclass_sets_the_columns(admin_client, changes, monkeypatch):
    class Columns(admin.HistoryAdmin):
        list_display = ("object", "action")

    monkeypatch.setattr(ItemAdmin, "history_admin", Columns, raising=False)

    soup = BeautifulSoup(admin_client.get(url(Item, "history_list")).content, "html.parser")

    headers = [th.get_text(" ", strip=True) for th in soup.select("#changelist-table thead th")]
    assert "Action" in headers
    assert "Changes" not in headers
    assert "50 → 9" not in soup.select_one("#changelist-table").get_text()


@pytest.fixture
def mugs(changes):
    Item.objects.bulk_create(
        Item(name=f"Mug {number}", slug=f"mug-{number}", category=changes.office) for number in range(SEARCH_PAGE_SIZE)
    )
    return changes


def history_filters(client):
    return BeautifulSoup(client.get(url(Item, "history_list")).content, "html.parser").select(
        "#changelist-filter-bar [data-filter-list] > *"
    )


def test_history_list_shows_the_object_filter_first(admin_client, changes):
    assert history_filters(admin_client)[0].select_one("[id$=_wrapper]")["id"] == "id_object_wrapper"


def test_history_object_filter_searches_with_the_search_fields_of_the_model_admin(admin_client, mugs):
    search = history_filters(admin_client)[0].select_one("input[hx-get]")["hx-get"]

    soup = BeautifulSoup(admin_client.get(f"{search}&q=kitchen").content, "html.parser")

    assert {row["data-label"] for row in soup.select("button[data-value]") if row["data-value"]} == {
        "Alpha kettle",
        "Beta lamp",
        "Gamma desk",
    }


def test_history_object_filter_pages_an_admin_without_search_fields(admin_client, mugs, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "search_fields", ())

    object_filter = history_filters(admin_client)[0].select_one("#id_object_wrapper")
    page = admin_client.get(object_filter.select_one("li[hx-get]")["hx-get"])

    assert object_filter["data-show-search"] == "false"
    assert len(BeautifulSoup(page.content, "html.parser").select("button[data-value]")) == SEARCH_PAGE_SIZE


def test_history_object_filter_shows_the_description_of_the_model_admin(admin_client, changes, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "choice_description", ["category"])

    row = history_filters(admin_client)[0].select_one(f"button[data-value='{changes.alpha.pk}']")

    assert list(row.stripped_strings) == ["Alpha kettle", "Kitchen"]


def test_history_object_filter_lists_the_rows_inline_for_a_user_who_cannot_view_them(admin_client, mugs, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "has_view_permission", lambda self, request, obj=None: False)

    object_filter = history_filters(admin_client)[0]

    assert object_filter.select_one("input[hx-get]") is None
    assert object_filter.select_one(f"button[data-value='{mugs.beta.pk}']") is not None


@pytest.mark.parametrize(("field", "status"), [("", 200), ("category", 404)])
def test_relation_search_needs_search_fields_only_for_a_relation(admin_client, catalog, monkeypatch, field, status):
    monkeypatch.setattr(ItemAdmin, "search_fields", ())
    monkeypatch.setattr(site.get_model_admin(Category), "search_fields", ())
    params = {"widget": "select", "site": "admin", "model": "admin_app.item", "field": field}

    response = admin_client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    assert response.status_code == status


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


def names_slot(**options):
    def names(self, request, queryset):
        listed = ", ".join(queryset.values_list("name", flat=True))
        return format_html("<p data-names>{}</p><p data-ordered>{}</p>", listed, queryset.ordered)

    return admin.slot(**options)(names) if options else names


def test_list_top_shows_the_filtered_rows_unsorted(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot())

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist") + "?status__exact=draft&o=1").content, "html.parser")

    assert soup.select_one("#changelist-top [data-names]").get_text() == "Beta lamp"
    assert soup.select_one("#changelist-top [data-ordered]").get_text() == "False"
    assert soup.find(id="changelist-bottom") is None


def test_lazy_slot_shows_its_skeleton_and_loads_the_filtered_rows(
    admin_client, catalog, monkeypatch, settings, tmp_path
):
    (tmp_path / "slot_skeleton.html").write_text("<div data-bars>{{ opts.verbose_name }}</div>")
    settings.TEMPLATES = [{**settings.TEMPLATES[0], "DIRS": [tmp_path]}]
    monkeypatch.setattr(ItemAdmin, "list_bottom", names_slot(lazy=True, skeleton="slot_skeleton.html"))

    page = admin_client.get(url(Item, "changelist") + "?status__exact=draft&o=2&p=1")
    slot = BeautifulSoup(page.content, "html.parser").find(id="changelist-bottom")

    assert slot.select_one("[data-slot-skeleton] [data-bars]").get_text() == "item"
    assert slot.select_one("[data-names]") is None
    assert slot["hx-get"] == url(Item, "slot", "bottom") + "?status__exact=draft"
    assert b"<p data-names>Beta lamp</p><p data-ordered>False</p>" in admin_client.get(slot["hx-get"]).content


def test_lazy_slot_without_a_skeleton_shows_a_placeholder(admin_client, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot(lazy=True))

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one("#changelist-top [data-slot-skeleton] .skeleton") is not None


def test_popup_list_has_no_slots(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot())

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist") + "?_popup=1").content, "html.parser")

    assert soup.select_one("[data-slot]") is None


@pytest.mark.parametrize(("codenames", "status"), [((), 403), (("view_item",), 200)], ids=["none", "view"])
def test_slot_view_needs_view_permission(staff_client, catalog, monkeypatch, codenames, status):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot(lazy=True))

    assert staff_client(*codenames).get(url(Item, "slot", "top")).status_code == status


@pytest.mark.parametrize("slot", ["bottom", "display"])
def test_slot_view_of_a_slot_the_admin_does_not_fill_is_not_found(admin_client, monkeypatch, slot):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot(lazy=True))

    assert admin_client.get(url(Item, "slot", slot)).status_code == 404


def test_slot_view_refuses_a_filter_the_list_does_not_have(admin_client, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot(lazy=True))

    assert admin_client.get(url(Item, "slot", "top"), {"nonsense": "1"}).status_code == 400


def test_slot_skeleton_needs_a_lazy_slot():
    with pytest.raises(ValueError, match="lazy=True"):
        names_slot(skeleton="slot_skeleton.html")


def test_list_slot_that_returns_nothing_is_left_out(admin_client, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", lambda self, request, queryset: "")

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one("[data-slot]") is None


@pytest.mark.parametrize(
    ("posts", "shown"), [((), True), (("1",), False), (("1", ""), True)], ids=["untouched", "closed", "reopened"]
)
def test_list_top_is_hidden_while_the_user_has_it_closed(admin_client, catalog, monkeypatch, posts, shown):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot())
    for closed in posts:
        assert admin_client.post(url(Item, "slot", "top"), {"closed": closed}).status_code == 204

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    slot = soup.find(id="changelist-top")
    assert (slot.select_one("[data-names]") is not None) is shown
    assert slot.has_attr("hidden") is not shown
    assert soup.select_one("[data-slot-toggle] button")["aria-expanded"] == str(shown).lower()


@pytest.mark.parametrize("options", [{}, {"lazy": True}], ids=["eager", "lazy"])
def test_closed_list_top_does_not_run_and_loads_the_filtered_rows_when_it_shows(
    admin_client, catalog, monkeypatch, options
):
    runs = []

    def top(self, request, queryset):
        runs.append(queryset.count())
        return "<p data-top></p>"

    monkeypatch.setattr(ItemAdmin, "list_top", admin.slot(**options)(top))
    admin_client.post(url(Item, "slot", "top"), {"closed": "1"})

    page = admin_client.get(url(Item, "changelist") + "?status__exact=draft")
    slot = BeautifulSoup(page.content, "html.parser").find(id="changelist-top")

    assert runs == []
    assert slot["hx-trigger"] == "formwork-admin:open"
    assert b"data-top" in admin_client.get(slot["hx-get"]).content
    assert runs == [1]


def test_closing_the_top_of_a_list_leaves_the_other_lists_open(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_top", names_slot())
    monkeypatch.setattr(type(site.get_model_admin(Category)), "list_top", names_slot(), raising=False)

    admin_client.post(url(Item, "slot", "top"), {"closed": "1"})
    soup = BeautifulSoup(admin_client.get(url(Category, "changelist")).content, "html.parser")

    assert soup.select_one("#changelist-top [data-names]") is not None


def test_only_the_top_slot_of_a_list_closes(admin_client, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "list_bottom", names_slot())

    assert admin_client.post(url(Item, "slot", "bottom"), {"closed": "1"}).status_code == 404
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    assert soup.select_one("[data-slot-toggle]") is None


def object_slot(**options):
    def named(self, request, obj):
        return format_html("<p data-name>{}</p>", obj.name) if obj.name != "Beta lamp" else ""

    return admin.slot(**options)(named) if options else named


def test_change_top_shows_the_object_above_the_fields(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "change_top", object_slot())
    alpha = Item.objects.get(name="Alpha kettle")

    soup = BeautifulSoup(admin_client.get(url(Item, "change", alpha.pk)).content, "html.parser")

    slot = soup.find(id="changeform-top")
    assert slot.select_one("[data-name]").get_text() == "Alpha kettle"
    assert slot.find_next(attrs={"data-field": "name"}) is not None
    assert soup.find(id="changeform-bottom") is None


def test_change_bottom_follows_the_form(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "change_bottom", object_slot())
    alpha = Item.objects.get(name="Alpha kettle")

    soup = BeautifulSoup(admin_client.get(url(Item, "change", alpha.pk)).content, "html.parser")

    slot = soup.find(id="changeform-bottom")
    assert slot.select_one("[data-name]").get_text() == "Alpha kettle"
    assert slot.find_parent("form") is None
    assert slot.find_previous(attrs={"data-save-bar": True}) is not None


def test_change_slot_that_returns_nothing_is_left_out(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "change_top", object_slot())
    beta = Item.objects.get(name="Beta lamp")

    soup = BeautifulSoup(admin_client.get(url(Item, "change", beta.pk)).content, "html.parser")

    assert soup.select_one("[data-slot]") is None


def test_lazy_change_slot_shows_a_placeholder_and_loads_the_object(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "change_bottom", object_slot(lazy=True))
    alpha = Item.objects.get(name="Alpha kettle")

    soup = BeautifulSoup(admin_client.get(url(Item, "change", alpha.pk)).content, "html.parser")
    slot = soup.find(id="changeform-bottom")

    assert slot.select_one("[data-slot-skeleton] .skeleton") is not None
    assert slot["hx-get"] == url(Item, "change_slot", alpha.pk, "bottom")
    assert admin_client.get(slot["hx-get"]).content == b"<p data-name>Alpha kettle</p>"


@pytest.mark.parametrize("query", ["add/", "{pk}/change/?_popup=1"], ids=["add", "popup"])
def test_add_page_and_dialog_have_no_change_slots(admin_client, catalog, monkeypatch, query):
    monkeypatch.setattr(ItemAdmin, "change_top", object_slot())
    alpha = Item.objects.get(name="Alpha kettle")

    response = admin_client.get(url(Item, "changelist") + query.format(pk=alpha.pk))

    assert response.status_code == 200
    assert BeautifulSoup(response.content, "html.parser").select_one("[data-slot]") is None


@pytest.mark.parametrize(("codenames", "status"), [((), 403), (("view_item",), 200)], ids=["none", "view"])
def test_change_slot_view_needs_view_permission(staff_client, catalog, monkeypatch, codenames, status):
    monkeypatch.setattr(ItemAdmin, "change_top", object_slot(lazy=True))
    alpha = Item.objects.get(name="Alpha kettle")

    assert staff_client(*codenames).get(url(Item, "change_slot", alpha.pk, "top")).status_code == status


@pytest.mark.parametrize(("pk", "slot"), [(None, "bottom"), (None, "display"), (0, "top")])
def test_change_slot_view_of_a_missing_slot_or_object_is_not_found(admin_client, catalog, monkeypatch, pk, slot):
    monkeypatch.setattr(ItemAdmin, "change_top", object_slot(lazy=True))
    pk = Item.objects.get(name="Alpha kettle").pk if pk is None else pk

    assert admin_client.get(url(Item, "change_slot", pk, slot)).status_code == 404


def test_row_details_open_under_their_row_and_a_row_without_any_has_no_toggle(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "row_details", object_slot())

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    (toggle,) = soup.select("#changelist-table details[data-row-toggle] summary")
    details = soup.find(id=toggle["aria-controls"])
    assert details.select_one("[data-name]").get_text() == "Alpha kettle"
    assert details.find_parent("tbody").find("a", string="Alpha kettle") is not None


def test_lazy_row_details_show_a_placeholder_on_every_row_and_load_the_object(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "row_details", object_slot(lazy=True))
    alpha = Item.objects.get(name="Alpha kettle")

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    slots = soup.select("#changelist-table [data-row-details] [data-slot]")

    assert len(slots) == Item.objects.count()
    assert all(slot.select_one("[data-slot-skeleton] .skeleton") for slot in slots)
    assert url(Item, "row_details", alpha.pk) in {slot["hx-get"] for slot in slots}
    assert admin_client.get(url(Item, "row_details", alpha.pk)).content == b"<p data-name>Alpha kettle</p>"


def test_popup_list_has_no_row_details(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(ItemAdmin, "row_details", object_slot())

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist") + "?_popup=1").content, "html.parser")

    assert soup.select("[data-row-toggle], [data-row-details]") == []


@pytest.mark.parametrize(("codenames", "status"), [((), 403), (("view_item",), 200)], ids=["none", "view"])
def test_row_details_view_needs_view_permission(staff_client, catalog, monkeypatch, codenames, status):
    monkeypatch.setattr(ItemAdmin, "row_details", object_slot(lazy=True))
    alpha = Item.objects.get(name="Alpha kettle")

    assert staff_client(*codenames).get(url(Item, "row_details", alpha.pk)).status_code == status


@pytest.mark.parametrize(
    ("details", "pk"), [(None, None), (object_slot(lazy=True), 0)], ids=["no-details", "no-object"]
)
def test_row_details_view_of_an_admin_without_them_or_a_missing_object_is_not_found(
    admin_client, catalog, monkeypatch, details, pk
):
    monkeypatch.setattr(ItemAdmin, "row_details", details)
    pk = Item.objects.get(name="Alpha kettle").pk if pk is None else pk

    assert admin_client.get(url(Item, "row_details", pk)).status_code == 404


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


def test_relation_options_show_the_description_of_the_related_admin(admin_client, catalog, monkeypatch):
    """The first page of the form and the rows of the search read the same."""
    monkeypatch.setattr(site.get_model_admin(Category), "choice_description", ["slug"])
    params = {"widget": "select", "site": "admin", "model": "admin_app.item", "field": "category", "q": "kit"}

    form = admin_client.get(url(Item, "change", catalog.alpha.pk))
    search = admin_client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    for response in (form, search):
        row = BeautifulSoup(response.content, "html.parser").select_one(f"button[data-value='{catalog.kitchen.pk}']")
        assert list(row.stripped_strings) == ["Kitchen", "kitchen"]


def test_relation_options_load_the_relations_their_description_reads(rf, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "choice_description", ["category", "status"])
    part_admin = admin.ModelAdmin(Part, site)

    def load():
        field = part_admin.formfield_for_foreignkey(Part._meta.get_field("item"), rf.get("/"))
        with CaptureQueriesContext(connection) as queries:
            descriptions = [label.description for value, label in field.choices if value]
        return len(queries), descriptions

    queries, descriptions = load()
    Item.objects.create(name="Zeta lamp", category=Category.objects.create(name="Workshop", slug="workshop"))

    assert descriptions == ["Kitchen · Archived", "Office · Draft"]
    assert load()[0] == queries


def test_editable_relation_of_a_list_loads_its_options_for_all_rows_at_once(admin_client, catalog, monkeypatch):
    Category.objects.bulk_create(
        Category(name=f"Aisle {number:02}", slug=f"aisle-{number:02}") for number in range(SEARCH_PAGE_SIZE)
    )
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", ["category"])

    def load():
        with CaptureQueriesContext(connection) as queries:
            soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
        return len(queries), len(soup.select("#changelist-table [name$=-category]"))

    queries, selects = load()
    Item.objects.create(name="Gamma mug", category=Category.objects.create(name="Workshop", slug="workshop"))

    assert selects == 2
    assert load() == (queries, 3)


def test_inline_rows_load_the_choices_of_a_relation_at_once(admin_client, catalog, monkeypatch):
    Tag.objects.bulk_create(Tag(name=f"aisle {number:02}") for number in range(SEARCH_PAGE_SIZE))
    for name in ["spring", "summer", "winter"]:
        Item.objects.create(name=f"{name} mug", category=catalog.kitchen).tags.add(Tag.objects.create(name=name))
    inline = type("TagsInline", (admin.TabularInline,), {"model": Item, "fields": ["name", "tags"], "extra": 0})
    monkeypatch.setattr(site.get_model_admin(Category), "inlines", [inline])

    def load(*, share):
        inline.share_choices = share
        with CaptureQueriesContext(connection) as queries:
            response = admin_client.get(url(Category, "change", catalog.kitchen.pk))
        return len(queries), str(BeautifulSoup(response.content, "html.parser").select_one("#items-group"))

    (shared, rows), (alone, own_rows) = load(share=None), load(share=False)

    assert rows == own_rows
    assert shared < alone


def test_relation_search_keeps_the_model_ordering_under_an_annotated_admin(admin_client):
    """A related admin that annotates its rows still lists them in the model's ordering."""
    for name in ["Bravo", "Alpha", "Charlie"]:
        Category.objects.create(name=name, slug=name.lower())
    params = {"widget": "select", "site": "admin", "model": "admin_app.item", "field": "category"}

    response = admin_client.get(reverse("formwork:search", args=[RELATION_SEARCH_KEY]), params)

    rows = BeautifulSoup(response.content, "html.parser").select("button[data-value]")
    assert [row["data-label"] for row in rows] == ["Alpha", "Bravo", "Charlie"]


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


@pytest.mark.parametrize("view", ["change", "changelist"])
def test_popup_refuses_a_to_field_that_no_relation_uses(admin_client, catalog, view):
    args = (catalog.kitchen.pk,) if view == "change" else ()

    response = admin_client.get(url(Category, view, *args), {"_popup": "1", "_to_field": "name"})

    assert response.status_code == 400


@pytest.mark.parametrize("raw_id_fields", [(), ("category",)])
def test_raw_id_field_gets_a_lookup_button_to_the_related_list(admin_client, catalog, monkeypatch, raw_id_fields):
    monkeypatch.setattr(site.get_model_admin(Item), "raw_id_fields", raw_id_fields)

    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")

    links = soup.select('[data-related="admin_app.category"] [data-related-popup="lookup"]')
    assert [link["href"] for link in links] == [url(Category, "changelist")] * len(raw_id_fields)


def test_lookup_lists_only_the_rows_the_relation_offers(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "raw_id_fields", ["category"])
    monkeypatch.setattr(Item._meta.get_field("category").remote_field, "limit_choices_to", {"slug": "office"})
    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")
    lookup = soup.select_one('[data-related-popup="lookup"]')["href"]

    response = admin_client.get(f"{lookup}&_popup=1&_to_field=id")

    picks = BeautifulSoup(response.content, "html.parser").select("[data-popup-pick]")
    assert [json.loads(link["data-popup-pick"]) for link in picks] == [
        {"value": str(catalog.office.pk), "obj": "Office"}
    ]


def test_dialog_list_keeps_the_dialog_in_its_search_sort_and_add(admin_client, catalog):
    response = admin_client.get(url(Category, "changelist"), {"_popup": "1", "_to_field": "id"})

    soup = BeautifulSoup(response.content, "html.parser")
    assert soup.select_one("#changelist-filters [name=_popup]")["value"] == "1"
    assert soup.select_one("#changelist-filters [name=_to_field]")["value"] == "id"
    sort_links = [link["href"] for link in soup.select("#changelist thead a[href]")]
    assert sort_links
    assert all("_popup=1" in href and "_to_field=id" in href for href in sort_links)
    add = soup.select_one(f'a[href^="{url(Category, "add")}"]')["href"]
    assert "_popup=1" in add
    assert "_to_field=id" in add


@pytest.mark.parametrize("popup", [True, False], ids=["dialog", "page"])
def test_only_the_dialog_list_picks_rows_and_it_edits_and_exports_nothing(admin_client, catalog, popup):
    params = {"_popup": "1", "_to_field": "id"} if popup else {}

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist"), params).content, "html.parser")

    assert bool(soup.select("[data-popup-pick]")) is popup
    assert bool(soup.select("[name=form-0-quantity]")) is not popup
    assert bool(soup.select(f'form[action="{url(Item, "export")}"]')) is not popup
    assert bool(soup.select(f'a[href^="{url(Item, "import")}"]')) is not popup


@pytest.mark.parametrize(
    ("codenames", "buttons"),
    [
        (("add_item", "view_category", "view_tag"), ["View selected category"]),
        (
            ("add_item", "add_category", "change_category", "view_tag"),
            ["Edit selected category", "Add another category"],
        ),
    ],
)
def test_relation_buttons_follow_the_related_admins_permissions(staff_client, catalog, codenames, buttons):
    soup = BeautifulSoup(staff_client(*codenames).get(url(Item, "add")).content, "html.parser")

    field = soup.select_one("#id_category_field")
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

    links = soup.select('#id_category_field [data-related-popup="change"]')
    assert [link.get("href") for link in links] == [url(Category, "change", catalog.kitchen.pk)]


@pytest.mark.parametrize(("widget", "buttons"), [(forms.CheckboxSelectMultiple, 1), (forms.MultipleHiddenInput, 0)])
def test_relation_buttons_show_next_to_any_visible_widget(admin_client, catalog, monkeypatch, widget, buttons):
    overrides = {models.ManyToManyField: {"widget": widget}}
    monkeypatch.setattr(site.get_model_admin(Item), "formfield_overrides", overrides)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    assert soup.select_one("[name=tags]") is not None
    assert len(soup.select('#id_tags_field [data-related-popup="add"]')) == buttons


def test_a_required_relation_shown_as_checkboxes_does_not_require_every_box(admin_client, catalog, monkeypatch):
    overrides = {models.ManyToManyField: {"widget": forms.CheckboxSelectMultiple, "required": True}}
    monkeypatch.setattr(site.get_model_admin(Item), "formfield_overrides", overrides)

    soup = BeautifulSoup(admin_client.get(url(Item, "change", catalog.alpha.pk)).content, "html.parser")

    boxes = soup.select("#id_tags_field input[type=checkbox]")
    assert boxes
    assert [box for box in boxes if box.has_attr("required")] == []


def test_change_button_is_dimmed_without_a_chosen_row(admin_client, catalog):
    soup = BeautifulSoup(admin_client.get(url(Item, "add")).content, "html.parser")

    link = soup.select_one('#id_category_field [data-related-popup="change"]')
    assert not link.has_attr("href")
    assert link["aria-disabled"] == "true"


def test_list_editable_relation_has_no_dialog_buttons(admin_client, catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable", ["category"])

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    assert soup.select_one("#changelist [name=form-0-category]") is not None
    assert soup.select("#changelist [data-related-popup]") == []


_STUB_COLUMNS = ["category", "status", "released", "available_from"]


@pytest.fixture
def stub_list(catalog, monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "list_display", ["name", *_STUB_COLUMNS])
    monkeypatch.setattr(model_admin, "list_editable", _STUB_COLUMNS)
    Item.objects.filter(pk=catalog.alpha.pk).update(available_from=datetime(2026, 3, 4, 9, 30, tzinfo=UTC))
    return catalog


def _cell(soup, obj, field):
    return soup.select_one(f"#changelist-table tr[data-pk='{obj.pk}'] td:has([name$=-{field}])")


def test_saving_a_list_of_stubs_posts_the_values_of_its_rows(admin_client, stub_list):
    stub_list.beta.delete()
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    form = soup.find(id="changelist-form")
    data = {el["name"]: el.get("value", "") for el in form.select("input[name^=form-]:not([disabled])")}
    before = list(Item.objects.order_by("pk").values(*_STUB_COLUMNS))

    response = admin_client.post(url(Item, "changelist"), {**data, "_save": "1"})

    assert len(form.select("[data-formwork-stub]")) == len(_STUB_COLUMNS)
    assert response.status_code == 302
    assert list(Item.objects.order_by("pk").values(*_STUB_COLUMNS)) == before


def test_a_failed_list_save_renders_stubs_for_the_fields_without_errors(admin_client, stub_list):
    stub_list.beta.delete()
    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
    form = soup.find(id="changelist-form")
    data = {el["name"]: el.get("value", "") for el in form.select("input[name^=form-]:not([disabled])")}
    data.update({"form-0-released": "not a date", "form-0-category": str(stub_list.office.pk)})

    soup = BeautifulSoup(admin_client.post(url(Item, "changelist"), {**data, "_save": "1"}).content, "html.parser")

    released = _cell(soup, stub_list.alpha, "released")
    category = _cell(soup, stub_list.alpha, "category")
    assert released.select("[data-formwork-stub]") == []
    assert released.select_one("[name$=-released]")["aria-invalid"] == "true"
    assert category.select_one("[data-formwork-stub] [name$=-category]")["value"] == str(stub_list.office.pk)


@pytest.mark.parametrize("stubs", [True, False])
def test_a_list_select_shows_its_rows_choice_and_its_column_lists_the_options_once_without_stubs(
    admin_client, stub_list, monkeypatch, stubs
):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable_stubs", stubs)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    cell = _cell(soup, stub_list.alpha, "category")
    column = [template.get_text(" ") for template in soup.find_all("template", id="form-category-options")]
    assert cell.select_one("[name$=-category]")["value"] == str(stub_list.kitchen.pk)
    assert "Kitchen" in cell.summary.get_text()
    assert cell.select("[role=option]") == []
    assert [("Kitchen" in text, "Office" in text) for text in column] == ([] if stubs else [(True, True)])


def test_a_list_select_longer_than_one_page_loads_its_rows_from_the_search(admin_client, stub_list, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable_stubs", False)
    Category.objects.bulk_create(Category(name=f"Shelf {n}", slug=f"shelf-{n}") for n in range(SEARCH_PAGE_SIZE))

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    cell = _cell(soup, stub_list.alpha, "category")
    assert cell.select_one("[data-has-search-url]")["data-has-search-url"] == "true"
    assert cell.select("[data-options]") == []
    assert soup.find_all("template", id="form-category-options") == []


class _OwnCategoryForm(FormworkModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(pk=self.instance.category_id)


class _OwnCategoryFormSet(FormworkBaseModelFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["category"].queryset = Category.objects.filter(pk=form.instance.category_id)


@pytest.mark.parametrize("form", [None, _OwnCategoryForm])
def test_a_list_of_stubs_and_its_relation_filter_run_the_queries_of_the_full_list(
    admin_client, stub_list, monkeypatch, form
):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "list_filter", ["category"])
    if form is not None:
        monkeypatch.setattr(model_admin, "form", form)

    def queries(*, stubs):
        monkeypatch.setattr(model_admin, "list_editable_stubs", stubs)
        with CaptureQueriesContext(connection) as captured:
            admin_client.get(url(Item, "changelist"))
        return len(captured)

    full = queries(stubs=False)

    assert queries(stubs=True) == full


def test_the_select_stubs_of_a_list_build_the_widget_of_a_value_once_for_all_rows_that_hold_it(
    admin_client, stub_list, monkeypatch
):
    built = []
    get_stub_context = Select.get_stub_context
    monkeypatch.setattr(
        Select, "get_stub_context", lambda select, *args: built.append(args) or get_stub_context(select, *args)
    )

    def render():
        built.clear()
        admin_client.get(url(Item, "changelist"))
        return len(built)

    two_rows = render()
    for name in ["Gamma kettle", "Delta kettle"]:
        Item.objects.create(name=name, category=stub_list.kitchen, status=Item.Status.ARCHIVED)

    assert render() == two_rows


class _RowNameForm(FormworkModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].widget.attrs["data-row"] = self.instance.name


def test_the_select_stubs_of_a_list_keep_the_widget_attrs_that_each_row_sets(admin_client, stub_list, monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "form", _RowNameForm)
    monkeypatch.setattr(model_admin, "share_choices", True)
    gamma = Item.objects.create(name="Gamma kettle", category=stub_list.kitchen, status=Item.Status.ARCHIVED)

    soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")

    rows = [_cell(soup, obj, "category").select_one("[data-row]")["data-row"] for obj in (stub_list.alpha, gamma)]
    assert rows == ["Alpha kettle", "Gamma kettle"]


@pytest.mark.parametrize("field", ["category", "status"])
def test_a_select_stub_sizes_its_trigger_with_the_labels_of_the_full_select(
    admin_client, stub_list, monkeypatch, field
):
    def label_copy():
        soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
        return str(_cell(soup, stub_list.alpha, field).select_one(".formwork-autowidth"))

    stubbed = label_copy()
    monkeypatch.setattr(site.get_model_admin(Item), "list_editable_stubs", False)

    assert label_copy() == stubbed


def test_the_stub_of_a_row_with_its_own_choices_sizes_its_trigger_with_the_rows_labels(
    admin_client, stub_list, monkeypatch
):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "form", _OwnCategoryForm)

    def cells():
        soup = BeautifulSoup(admin_client.get(url(Item, "changelist")).content, "html.parser")
        return [_cell(soup, obj, "category") for obj in (stub_list.alpha, stub_list.beta)]

    stubs = cells()
    monkeypatch.setattr(model_admin, "list_editable_stubs", False)
    full = cells()

    assert all(cell.select("[data-formwork-stub]") for cell in stubs)
    assert [str(cell.select_one(".formwork-autowidth")) for cell in stubs] == [
        str(cell.select_one(".formwork-autowidth")) for cell in full
    ]
    assert "Office" in full[1].select_one(".formwork-autowidth").get_text()
    assert "Office" not in full[0].select_one(".formwork-autowidth").get_text()


def test_a_cell_answers_with_the_full_widget_for_the_value_its_stub_holds(admin_client, stub_list):
    query = {"pk": stub_list.alpha.pk, "prefix": "form-0", "form-0-category": stub_list.office.pk}

    soup = BeautifulSoup(admin_client.get(url(Item, "cell", "category"), query).content, "html.parser")

    value = soup.select_one("[x-data=formworkSelect] input[type=hidden]")
    assert value["name"] == "form-0-category"
    assert value["value"] == str(stub_list.office.pk)


def test_a_cell_gives_its_row_the_choices_that_the_lists_formset_gives_it(admin_client, stub_list, monkeypatch):
    model_admin = site.get_model_admin(Item)
    get_formset = model_admin.get_changelist_formset
    monkeypatch.setattr(
        model_admin,
        "get_changelist_formset",
        lambda request, **kwargs: get_formset(request, formset=_OwnCategoryFormSet, **kwargs),
    )
    query = {"pk": stub_list.beta.pk, "prefix": "form-1"}

    soup = BeautifulSoup(admin_client.get(url(Item, "cell", "category"), query).content, "html.parser")

    assert [option.get_text(strip=True) for option in soup.select("[role=option]")] == ["Office"]
    assert soup.select_one("input[type=hidden]")["name"] == "form-1-category"


@pytest.mark.parametrize(("field", "pk"), [("name", None), ("category", "unknown")])
def test_a_cell_of_a_column_the_list_does_not_edit_or_of_a_missing_row_is_not_found(admin_client, stub_list, field, pk):
    query = {"pk": pk or stub_list.alpha.pk, "prefix": "form-0"}

    assert admin_client.get(url(Item, "cell", field), query).status_code == 404


def test_a_cell_is_refused_to_a_user_who_cannot_change_the_rows(staff_client, stub_list):
    client = staff_client("view_item")

    response = client.get(url(Item, "cell", "category"), {"pk": stub_list.alpha.pk, "prefix": "form-0"})

    assert response.status_code == 403


class _ItemRowsInline(admin.TabularInline):
    model = Item
    fields = ["name", "status", "tags", "released"]
    extra = 1


@pytest.fixture
def stub_inline(catalog, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Category), "inlines", [_ItemRowsInline])
    return catalog


@pytest.mark.parametrize(("attrs", "stubbed"), [({}, True), ({"stubs": False}, False), ({"layout": "stacked"}, False)])
def test_the_saved_rows_of_a_tabular_inline_render_their_selects_relations_and_date_pickers_as_stubs(
    admin_client, stub_inline, monkeypatch, attrs, stubbed
):
    for name, value in attrs.items():
        monkeypatch.setattr(_ItemRowsInline, name, value)
    kitchen = stub_inline.kitchen

    soup = BeautifulSoup(admin_client.get(url(Category, "change", kitchen.pk)).content, "html.parser")

    found = [
        (stub.select_one("[name]")["name"], urlsplit(stub["data-formwork-stub"]))
        for stub in soup.select("[data-formwork-stub]")
    ]
    assert [(name, link.path, parse_qs(link.query)) for name, link in found] == [
        (
            f"items-0-{field}",
            url(Category, "change_cell", kitchen.pk, field),
            {"pk": [str(stub_inline.alpha.pk)], "prefix": ["items-0"]},
        )
        for field in ("status", "tags", "released")
        if stubbed
    ]


def test_the_relation_stub_of_an_inline_row_keeps_the_links_of_the_relation_widget(admin_client, stub_inline):
    soup = BeautifulSoup(admin_client.get(url(Category, "change", stub_inline.kitchen.pk)).content, "html.parser")

    cell = soup.select_one("[data-formset-row=items-0] td:has([name=items-0-tags])")
    stub = cell.select_one("[x-data=formworkRelated] [data-formwork-stub]")
    assert [el["value"] for el in stub.select("[name=items-0-tags]") if el["value"]] == [str(stub_inline.sale.pk)]
    assert [link["data-related-popup"] for link in cell.select("[data-related-popup]")] == ["add"]


def test_an_inline_cell_answers_with_the_full_widget_for_the_value_its_stub_holds(admin_client, stub_inline):
    query = {"pk": stub_inline.alpha.pk, "prefix": "items-0", "items-0-status": Item.Status.ACTIVE}

    response = admin_client.get(url(Category, "change_cell", stub_inline.kitchen.pk, "status"), query)

    value = BeautifulSoup(response.content, "html.parser").select_one("[x-data=formworkSelect] input[type=hidden]")
    assert (value["name"], value["value"]) == ("items-0-status", Item.Status.ACTIVE)


def test_an_inline_cell_of_a_relation_answers_with_the_select_alone_for_the_values_its_stub_holds(
    admin_client, stub_inline
):
    new = Tag.objects.create(name="new")
    query = {"pk": stub_inline.alpha.pk, "prefix": "items-0", "items-0-tags": ["", new.pk]}

    response = admin_client.get(url(Category, "change_cell", stub_inline.kitchen.pk, "tags"), query)

    soup = BeautifulSoup(response.content, "html.parser")
    assert soup.find()["x-data"] == "formworkSelectMultiple"
    assert soup.select("[data-related], [data-related-popup]") == []
    assert [box["value"] for box in soup.select("input[name=items-0-tags][checked]")] == [str(new.pk)]


@pytest.mark.parametrize(
    ("field", "prefix", "row"),
    [("price", "items-0", "alpha"), ("status", "parts-0", "alpha"), ("status", "items-0", "beta")],
)
def test_an_inline_cell_of_a_field_the_inline_lacks_or_of_another_objects_row_is_not_found(
    admin_client, stub_inline, field, prefix, row
):
    query = {"pk": getattr(stub_inline, row).pk, "prefix": prefix}

    assert admin_client.get(url(Category, "change_cell", stub_inline.kitchen.pk, field), query).status_code == 404


@pytest.mark.parametrize("codenames", [("view_category", "change_item"), ("change_category", "view_item")])
def test_an_inline_cell_is_refused_to_a_user_who_cannot_change_the_object_or_its_rows(
    staff_client, stub_inline, codenames
):
    client = staff_client(*codenames)
    query = {"pk": stub_inline.alpha.pk, "prefix": "items-0"}

    assert client.get(url(Category, "change_cell", stub_inline.kitchen.pk, "status"), query).status_code == 403


def test_view_on_site_redirects_to_the_object(admin_client, catalog):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(Item)

    response = admin_client.get(reverse("admin:view_on_site", args=[content_type.pk, catalog.alpha.pk]))

    assert response.status_code == 302
    assert response["Location"].endswith(f"/items/{catalog.alpha.pk}/")


def test_registered_admins_pass_the_checks():
    assert checks.run_checks(tags=[checks.Tags.admin]) == []


@pytest.mark.parametrize(
    ("css", "warnings"),
    [
        (f':root{{--formwork-admin-css:"{__version__}"}}', []),
        (':root{--formwork-admin-css:"0.0.1"}', ["formwork_admin.W501"]),
        ("body{color:red}", ["formwork_admin.W501"]),
    ],
)
def test_check_warns_while_a_site_css_comes_from_another_version(tmp_path, settings, monkeypatch, css, warnings):
    (tmp_path / "site.css").write_text(css)
    settings.STATICFILES_DIRS = [str(tmp_path)]
    monkeypatch.setattr("django_formwork.admin.sites._sites", {})
    monkeypatch.setattr("django_formwork.admin.sites._all_sites", set())
    styled = admin.AdminSite(name="styled")
    styled.stylesheets = ("site.css", "https://cdn.example.com/extra.css")

    assert [message.id for message in checks.run_checks(tags=[checks.Tags.admin])] == warnings


def test_check_reports_two_sites_with_the_same_name(monkeypatch):
    monkeypatch.setattr("django_formwork.admin.sites._sites", {})
    monkeypatch.setattr("django_formwork.admin.sites._all_sites", set())
    for name in ("shared", "shared", "other"):
        admin.AdminSite(name=name)

    messages = checks.run_checks(tags=[checks.Tags.admin])

    assert [message.id for message in messages] == ["formwork_admin.E502"]
    assert "'shared'" in messages[0].msg


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
        ({"choice_description": ["nope"]}, "formwork_admin.E503"),
    ],
)
def test_checks_report_misconfigured_options(options, error_id):
    model_admin = type("BrokenAdmin", (admin.ModelAdmin,), options)(Item, site)

    assert [error.id for error in check_model_admin(model_admin)] == [error_id]


class _RowForm(FormworkModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class _RowFormSet(FormworkBaseInlineFormSet):
    def get_form_kwargs(self, index):
        return super().get_form_kwargs(index)


_EDITABLE_CATEGORY = {"list_display": ["name", "category"], "list_editable": ["category"]}


@pytest.mark.parametrize(
    ("model", "options", "errors"),
    [
        (Item, {**_EDITABLE_CATEGORY, "form": _RowForm}, ["formwork_admin.E504"]),
        (Item, {**_EDITABLE_CATEGORY, "form": _RowForm, "share_choices": True}, []),
        (Item, {**_EDITABLE_CATEGORY, "form": _RowForm, "share_choices": False}, []),
        (Item, _EDITABLE_CATEGORY, []),
        (Item, {"form": _RowForm}, []),
        (
            Category,
            {"inlines": [type("RowsInline", (admin.TabularInline,), {"model": Item, "formset": _RowFormSet})]},
            ["formwork_admin.E504"],
        ),
        (
            Category,
            {
                "inlines": [
                    type("NameInline", (admin.TabularInline,), {"model": Item, "fields": ["name"], "form": _RowForm})
                ]
            },
            [],
        ),
    ],
)
def test_check_asks_rows_that_can_get_their_own_choices_to_set_share_choices(model, options, errors):
    model_admin = type("RowsAdmin", (admin.ModelAdmin,), options)(model, site)

    assert [error.id for error in check_model_admin(model_admin)] == errors


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


@pytest.mark.parametrize(("view", "marks"), [("change", True), ("add", False)])
def test_change_form_marks_the_changed_fields_of_a_saved_object_only(admin_client, catalog, view, marks):
    args = (catalog.alpha.pk,) if view == "change" else ()
    soup = BeautifulSoup(admin_client.get(url(Item, view, *args)).content, "html.parser")

    assert soup.find("form", id="item_form").has_attr("data-formwork-dirty") is marks


def test_change_form_failed_save_keeps_every_change_marked(admin_client, catalog):
    alpha = catalog.alpha
    data = item_data(
        catalog.kitchen,
        name="Alpha kettle XL",
        quantity="-1",
        **management("parts", total=1, initial=1),
        **{
            "parts-0-id": catalog.lid.pk,
            "parts-0-item": alpha.pk,
            "parts-0-name": "Glass lid",
            "parts-0-quantity": "-1",
        },
    )

    soup = BeautifulSoup(admin_client.post(url(Item, "change", alpha.pk), data).content, "html.parser")

    marked = {el.find(["input", "select", "textarea"])["name"] for el in soup.select("[data-formwork-changed]")}
    assert {"name", "parts-0-name", "quantity", "parts-0-quantity"} <= marked
