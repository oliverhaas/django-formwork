"""Changelist imports: the check, the preview and saving through the admin."""

import io
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from admin_app.models import Category, Item, Tag
from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import Workbook

from django_formwork.admin import site
from django_formwork.admin.models import HistoryEntry

pytestmark = pytest.mark.django_db

IMPORT_URL = "admin:admin_app_item_import"


@pytest.fixture(autouse=True)
def admin_urls(settings):
    settings.ROOT_URLCONF = "admin_app.urls"


@pytest.fixture
def kitchen():
    return Category.objects.create(name="Kitchen", slug="kitchen")


@pytest.fixture
def items(kitchen):
    sale = Tag.objects.create(name="sale")
    kettle = Item.objects.create(
        name="Alpha kettle",
        category=kitchen,
        status=Item.Status.ARCHIVED,
        price=Decimal("19.90"),
        released=date(2026, 1, 10),
        data={"color": "red"},
    )
    kettle.tags.add(sale)
    lamp = Item.objects.create(name="Beta lamp", category=kitchen, is_featured=True)
    return kettle, lamp


def upload(content, name="items.csv"):
    return SimpleUploadedFile(name, content.encode() if isinstance(content, str) else content)


def check(client, content, name="items.csv", url=IMPORT_URL):
    return client.post(reverse(url), {"file": upload(content, name), "_check": "1"})


def run_import(client, content, name="items.csv", url=IMPORT_URL):
    digest = preview(check(client, content, name, url))["digest"]
    return client.post(reverse(url), {"file": upload(content, name), "_import": "1", "digest": digest})


def preview(response):
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, "html.parser")
    section = soup.select_one("section[id^=import-preview]")
    if section is None:
        return {"errors": [p.get_text(" ", strip=True) for p in soup.select(".text-error, [role=alert]")]}
    counts = {}
    for tile in section.select("button[aria-pressed]"):
        label, count = tile.get_text(" ", strip=True).rsplit(" ", 1)
        counts[label] = int(count)
    rows = [
        tr.select_one("[data-status]").get_text(strip=True) for tr in section.select("tbody tr:not(:has(td[colspan]))")
    ]
    messages = [td.get_text(" ", strip=True) for td in section.select("td[colspan]")]
    invalid = [td.get_text(" ", strip=True) for td in section.select("td[data-invalid]")]
    button = section.select_one("button[name=_import]")
    return {
        "counts": counts,
        "rows": rows,
        "messages": messages,
        "invalid": invalid,
        "digest": section.select_one("input[name=digest]")["value"],
        "can_import": not button.has_attr("disabled"),
        "text": section.get_text(" ", strip=True),
    }


def staff(client, django_user_model, *codenames):
    user = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    client.force_login(user)
    return user


def test_import_button_shows_only_with_import_formats(admin_client, monkeypatch):
    soup = BeautifulSoup(admin_client.get(reverse("admin:admin_app_item_changelist")).content, "html.parser")
    assert soup.select_one(f'a[href="{reverse(IMPORT_URL)}"]') is not None

    monkeypatch.setattr(site.get_model_admin(Item), "import_formats", ())

    soup = BeautifulSoup(admin_client.get(reverse("admin:admin_app_item_changelist")).content, "html.parser")
    assert soup.select_one(f'a[href="{reverse(IMPORT_URL)}"]') is None
    assert admin_client.get(reverse(IMPORT_URL)).status_code == 404


def test_import_needs_add_or_change_permission(client, django_user_model):
    staff(client, django_user_model, "view_item")

    soup = BeautifulSoup(client.get(reverse("admin:admin_app_item_changelist")).content, "html.parser")

    assert soup.select_one(f'a[href="{reverse(IMPORT_URL)}"]') is None
    assert client.get(reverse(IMPORT_URL)).status_code == 403


def test_check_counts_new_changed_and_unchanged_rows(admin_client, items):
    kettle, lamp = items
    content = (
        "id,name,category__name,price\n"
        f"{kettle.pk},Alpha kettle,Kitchen,19.90\n{lamp.pk},Beta lamp XL,Kitchen,5\n,Gamma mug,Kitchen,3\n"
    )

    result = preview(check(admin_client, content))

    assert result["counts"] == {"New": 1, "Changed": 1, "Unchanged": 1, "Errors": 0}
    assert result["rows"] == ["Unchanged", "Changed", "New"]
    assert "Beta lamp XL" in result["text"]
    assert result["can_import"]
    assert Item.objects.count() == 2


def test_preview_badges_take_the_list_badges_colors(admin_client, items):
    _kettle, lamp = items

    response = check(admin_client, f"id,status\n{lamp.pk},archived\n")

    changed = BeautifulSoup(response.content, "html.parser").select_one("section[id^=import-preview] td:has(del)")
    assert "badge-ghost" in changed.select_one("del .badge")["class"]
    assert "badge-warning" in changed.select_one("ins .badge")["class"]


def test_import_saves_new_and_changed_rows_and_logs_them(admin_client, admin_user, items):
    kettle, lamp = items
    content = (
        "id,name,category__name,tags__name,status,price\n"
        f"{kettle.pk},Alpha kettle,Kitchen,sale,Archived,19.90\n"
        f"{lamp.pk},Beta lamp,Kitchen,sale,active,7.5\n"
        ",Gamma mug,Kitchen,,draft,3\n"
    )

    response = run_import(admin_client, content)

    assert response.status_code == 302
    assert response["Location"] == reverse("admin:admin_app_item_changelist")
    lamp.refresh_from_db()
    assert lamp.status == Item.Status.ACTIVE
    assert lamp.price == Decimal("7.50")
    assert list(lamp.tags.values_list("name", flat=True)) == ["sale"]
    assert lamp.is_featured
    mug = Item.objects.get(name="Gamma mug")
    assert mug.category.name == "Kitchen"
    assert mug.quantity == 0
    entries = HistoryEntry.objects.filter(user=admin_user).order_by("action")
    assert [(entry.object_id, entry.action) for entry in entries] == [(str(mug.pk), "add"), (str(lamp.pk), "change")]
    assert "Status" in entries[1].changes[0]["changed"]["fields"]
    messages = [str(message) for message in response.wsgi_request._messages]
    assert messages == ["Imported 2 items: 1 added, 1 changed."]


def test_import_runs_the_admins_save_hooks(admin_client, kitchen, monkeypatch):
    model_admin = site.get_model_admin(Item)

    def save_model(request, obj, form, change):
        obj.notes = f"by {request.user.username}"
        obj.save()

    monkeypatch.setattr(model_admin, "save_model", save_model)

    run_import(admin_client, f"name,category\nMug,{kitchen.pk}\n")

    assert Item.objects.get(name="Mug").notes == "by admin"


def test_errors_block_the_import(admin_client, items):
    _kettle, lamp = items
    content = (
        f"id,name,category__name,price\n{lamp.pk},Beta lamp,Nowhere,5\n,Gamma mug,Kitchen,abc\n,Delta cup,Kitchen,2\n"
    )

    result = preview(check(admin_client, content))

    assert result["counts"]["Errors"] == 2
    assert not result["can_import"]
    assert any("No category matches “Nowhere”." in cell for cell in result["invalid"])
    assert any("Enter a number." in cell for cell in result["invalid"])
    response = admin_client.post(
        reverse(IMPORT_URL), {"file": upload(content), "_import": "1", "digest": result["digest"]}
    )
    assert response.status_code == 200
    assert not Item.objects.filter(name__in=["Gamma mug", "Delta cup"]).exists()


def test_new_rows_need_add_permission(client, django_user_model, items):
    kettle, _lamp = items
    staff(client, django_user_model, "view_item", "change_item")

    result = preview(check(client, f"id,name\n{kettle.pk},Alpha kettle 2\n,Gamma mug\n"))

    assert result["rows"] == ["Changed", "Error"]
    assert result["messages"] == ["You can’t add items."]


def test_changed_rows_need_change_permission(client, django_user_model, items, monkeypatch):
    kettle, lamp = items
    staff(client, django_user_model, "view_item", "change_item", "add_item")
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(
        model_admin, "has_change_permission", lambda request, obj=None: obj is None or obj.pk != kettle.pk
    )

    result = preview(check(client, f"id,name\n{kettle.pk},Alpha kettle 2\n{lamp.pk},Beta lamp\n"))

    assert result["rows"] == ["Error", "Unchanged"]
    assert result["messages"] == ["You can’t change this item."]


def test_rows_cannot_change_read_only_fields(admin_client, items, monkeypatch):
    kettle, _lamp = items
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(
        model_admin, "get_readonly_fields", lambda request, obj=None: ["created", "price"] if obj else ["created"]
    )

    result = preview(check(admin_client, f"id,price\n{kettle.pk},25\n"))

    assert result["rows"] == ["Error"]
    assert any("This field can’t be changed." in cell for cell in result["invalid"])


@pytest.mark.parametrize("export_format", ["csv", "xlsx", "json"])
def test_an_exported_file_imports_unchanged(admin_client, items, export_format):
    content = admin_client.post(reverse("admin:admin_app_item_export"), {"format": export_format}).content

    result = preview(check(admin_client, content, f"items.{export_format}"))

    assert result["counts"] == {"New": 0, "Changed": 0, "Unchanged": 2, "Errors": 0}
    assert not result["can_import"]
    assert "created" in result["text"]


@pytest.mark.parametrize("export_format", ["csv", "xlsx", "json"])
def test_exported_times_import_unchanged_despite_lost_microseconds(admin_client, items, export_format, monkeypatch):
    kettle, _lamp = items
    Item.objects.filter(pk=kettle.pk).update(available_from=datetime(2026, 3, 1, 9, 30, 15, 946450, tzinfo=UTC))
    monkeypatch.setattr(site.get_model_admin(Item), "import_fields", ["name", "available_from"])
    content = admin_client.post(reverse("admin:admin_app_item_export"), {"format": export_format}).content

    result = preview(check(admin_client, content, f"items.{export_format}"))

    assert result["counts"] == {"New": 0, "Changed": 0, "Unchanged": 2, "Errors": 0}


def test_semicolon_csv_with_decimal_comma(admin_client, kitchen):
    content = f"Name;Category;Price;Is featured\r\nMug;{kitchen.pk};1.234,50;Yes\r\n"

    run_import(admin_client, content.encode("cp1252"))

    mug = Item.objects.get(name="Mug")
    assert mug.price == Decimal("1234.50")
    assert mug.is_featured


def test_json_rows_leave_out_fields_they_lack(admin_client, items):
    kettle, _lamp = items
    content = json.dumps([{"id": kettle.pk, "price": "21.00", "data": {}}])

    run_import(admin_client, content, "items.json")

    kettle.refresh_from_db()
    assert kettle.price == Decimal("21.00")
    assert kettle.data == {}
    assert kettle.status == Item.Status.ARCHIVED
    assert list(kettle.tags.values_list("name", flat=True)) == ["sale"]


def test_excel_import_reads_the_first_sheet(admin_client, kitchen):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["name", "category", "released", "quantity"])
    sheet.append(["Mug", kitchen.pk, date(2026, 3, 31), 4.0])
    buffer = io.BytesIO()
    workbook.save(buffer)

    run_import(admin_client, buffer.getvalue(), "items.xlsx")

    mug = Item.objects.get(name="Mug")
    assert mug.released == date(2026, 3, 31)
    assert mug.quantity == 4


def test_lookup_column_that_matches_several_records_is_an_error(admin_client, kitchen):
    Category.objects.create(name="Kitchen", slug="kitchen-2")

    result = preview(check(admin_client, "name,category__name\nMug,Kitchen\n"))

    assert any("2 categories match “Kitchen”." in cell for cell in result["invalid"])


def test_rows_repeating_unique_values_get_the_error(admin_client, monkeypatch):
    model_admin = site.get_model_admin(Category)
    monkeypatch.setattr(model_admin, "import_formats", ("csv",))
    Category.objects.create(name="Garden", slug="garden")
    content = "name,slug\nKitchen,kitchen\nKitchen too,kitchen\nYard,garden\n"

    result = preview(check(admin_client, content, url="admin:admin_app_category_import"))

    assert result["rows"] == ["New", "Error", "Error"]
    assert any("Row 2 has the same slug." in cell for cell in result["invalid"])
    assert any("Category with this Slug already exists." in cell for cell in result["invalid"])


def test_import_id_fields_find_records_by_another_field(admin_client, kitchen, monkeypatch):
    model_admin = site.get_model_admin(Category)
    monkeypatch.setattr(model_admin, "import_formats", ("csv",))
    monkeypatch.setattr(model_admin, "import_id_fields", ("slug",))

    run_import(admin_client, "slug,name\nkitchen,Cooking\ngarden,Garden\n", url="admin:admin_app_category_import")

    assert dict(Category.objects.values_list("slug", "name")) == {"kitchen": "Cooking", "garden": "Garden"}


def test_two_rows_for_the_same_record_are_an_error(admin_client, items):
    kettle, _lamp = items

    result = preview(check(admin_client, f"id,name\n{kettle.pk},One\n{kettle.pk},Two\n"))

    assert result["rows"] == ["Changed", "Error"]
    assert result["messages"] == ["Row 2 has the same ID."]


def test_a_file_changed_since_the_check_shows_the_new_preview(admin_client, items):
    _kettle, lamp = items
    content = f"id,name\n{lamp.pk},Beta lamp XL\n"
    digest = preview(check(admin_client, content))["digest"]
    Item.objects.filter(pk=lamp.pk).update(name="Beta lamp L")

    response = admin_client.post(reverse(IMPORT_URL), {"file": upload(content), "_import": "1", "digest": digest})

    result = preview(response)
    assert "changed since the last check" in result["text"]
    lamp.refresh_from_db()
    assert lamp.name == "Beta lamp L"


@pytest.mark.parametrize(
    ("content", "name", "error"),
    [
        ("name\nMug\n", "items.txt", "Pick a CSV, Excel or JSON file."),
        ("colour,size\nred,2\n", "items.csv", "None of the columns is a field of items"),
        ("name\n", "items.csv", "The file has no rows under its header row."),
        ('{"name": "Mug"}', "items.json", "The file isn’t a JSON list of objects."),
    ],
)
def test_a_file_the_import_cant_read_gets_an_error(admin_client, content, name, error):
    result = preview(check(admin_client, content, name))

    assert any(error in text for text in result["errors"])


def test_check_queries_stay_flat_as_the_file_grows(admin_client, kitchen):
    Tag.objects.create(name="sale")

    def queries(rows):
        content = "name,category__name,tags__name\n" + "".join(f"Item {n},Kitchen,sale\n" for n in range(rows))
        with CaptureQueriesContext(connection) as captured:
            assert preview(check(admin_client, content))["counts"]["New"] == rows
        return len(captured)

    assert queries(40) == queries(4)
