"""Changelist exports: the file in the response and the background job."""

import csv
import io
import json
from datetime import date
from decimal import Decimal

import pytest
from admin_app.models import Category, Item, Tag
from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from openpyxl import load_workbook

from django_formwork.admin import site
from django_formwork.admin.exports import run_export_job
from django_formwork.admin.models import ExportJob

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def admin_urls(settings, tmp_path):
    settings.ROOT_URLCONF = "admin_app.urls"
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def items():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    sale = Tag.objects.create(name="sale")
    new = Tag.objects.create(name="new")
    kettle = Item.objects.create(
        name="Alpha kettle",
        category=kitchen,
        status=Item.Status.ARCHIVED,
        price=Decimal("19.90"),
        released=date(2026, 1, 10),
        data={"color": "red"},
    )
    kettle.tags.add(sale, new)
    lamp = Item.objects.create(name="Beta lamp", category=kitchen, status=Item.Status.DRAFT, is_featured=True)
    return kettle, lamp


EXPORT_URL = "admin:admin_app_item_export"


def export(client, export_format, query=""):
    return client.post(reverse(EXPORT_URL), {"format": export_format, "query": query})


def csv_rows(response):
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_csv_export_holds_the_filtered_rows(admin_client, items):
    kettle, _lamp = items

    response = export(admin_client, "csv", "status=archived")

    assert response["Content-Type"] == "text/csv"
    assert response["Content-Disposition"].startswith('attachment; filename="items-')
    rows = csv_rows(response)
    assert [row["name"] for row in rows] == ["Alpha kettle"]
    assert rows[0]["id"] == str(kettle.pk)
    assert rows[0]["category"] == str(kettle.category_id)
    assert rows[0]["price"] == "19.90"
    assert rows[0]["released"] == "2026-01-10"
    assert rows[0]["is_featured"] == "false"
    assert rows[0]["data"] == '{"color": "red"}'
    assert rows[0]["tags"] == ",".join(str(pk) for pk in sorted(kettle.tags.values_list("pk", flat=True)))


def test_json_export_keeps_lists_and_structures(admin_client, items):
    kettle, _lamp = items

    records = json.loads(export(admin_client, "json", "status=archived").content)

    assert records[0]["tags"] == sorted(kettle.tags.values_list("pk", flat=True))
    assert records[0]["data"] == {"color": "red"}
    assert records[0]["price"] == "19.90"


def test_excel_export_writes_typed_cells(admin_client, items):
    response = export(admin_client, "xlsx", "status=archived")

    sheet = load_workbook(io.BytesIO(response.content)).active
    header, row = sheet.iter_rows(values_only=True)
    assert header[:3] == ("id", "name", "slug")
    record = dict(zip(header, row, strict=True))
    assert record["name"] == "Alpha kettle"
    assert record["quantity"] == 0
    assert record["is_featured"] is False
    assert record["released"].date() == date(2026, 1, 10)


def test_export_fields_take_lookups_and_admin_methods(admin_client, items, monkeypatch):
    model_admin = site.get_model_admin(Item)
    monkeypatch.setattr(model_admin, "export_fields", ["name", "category__name", "tag_names"], raising=False)
    monkeypatch.setattr(
        type(model_admin),
        "tag_names",
        lambda self, obj: " / ".join(tag.name for tag in obj.tags.all()),
        raising=False,
    )

    rows = csv_rows(export(admin_client, "csv", "status=archived"))

    assert rows == [{"name": "Alpha kettle", "category__name": "Kitchen", "tag_names": "new / sale"}]


@pytest.mark.parametrize(
    ("data", "status"),
    [({"format": "pdf"}, 400), ({}, 400)],
)
def test_export_rejects_an_unknown_format(admin_client, items, data, status):
    assert admin_client.post(reverse(EXPORT_URL), data).status_code == status


def test_export_needs_view_permission(client, django_user_model, items):
    user = django_user_model.objects.create_user("staff", password="pw-12345", is_staff=True)
    client.force_login(user)

    assert export(client, "csv").status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_item"))
    assert export(client, "csv").status_code == 200


def test_export_menu_offers_the_formats_and_keeps_the_filters(admin_client, items):
    soup = BeautifulSoup(
        admin_client.get(reverse("admin:admin_app_item_changelist") + "?status__exact=draft&p=1").content, "html.parser"
    )

    menu = soup.select_one("form:has(> input[name=query])")
    assert [button["value"] for button in menu.select("button[name=format]")] == ["csv", "xlsx", "json"]
    assert menu.select_one("input[name=query]")["value"] == "status__exact=draft"


def test_export_menu_follows_the_filters_in_a_content_morph(admin_client, items):
    response = admin_client.get(
        reverse("admin:admin_app_item_changelist") + "?status__exact=archived",
        headers={"HX-Request": "true", "HX-Target": "main#content"},
    )

    soup = BeautifulSoup(response.content, "html.parser")
    assert soup.select_one("form:has(> input[name=query]) input[name=query]")["value"] == "status__exact=archived"


def test_export_menu_hides_without_formats(admin_client, items, monkeypatch):
    monkeypatch.setattr(site.get_model_admin(Item), "export_formats", ())

    soup = BeautifulSoup(admin_client.get(reverse("admin:admin_app_item_changelist")).content, "html.parser")

    assert soup.select_one("form:has(> input[name=query])") is None


def test_large_export_runs_as_a_job_and_downloads(
    admin_client, admin_user, items, monkeypatch, django_capture_on_commit_callbacks
):
    monkeypatch.setattr(site.get_model_admin(Item), "export_background_threshold", 1)

    with django_capture_on_commit_callbacks(execute=True):
        response = export(admin_client, "csv", "q=a")

    assert response.status_code == 302
    assert response["Location"] == reverse("admin:admin_app_item_changelist") + "?q=a"
    job = ExportJob.objects.get()
    assert (job.user, job.status, job.row_count) == (admin_user, ExportJob.Status.DONE, 2)

    page = BeautifulSoup(admin_client.get(reverse("admin:exports")).content, "html.parser")
    download = page.select_one(f'a[href="{reverse("admin:export_download", args=[job.pk])}"]')
    assert download is not None

    response = admin_client.get(download["href"])
    assert response["Content-Disposition"].startswith('attachment; filename="items-')
    content = b"".join(response.streaming_content).decode("utf-8-sig")
    assert sorted(row["name"] for row in csv.DictReader(io.StringIO(content))) == ["Alpha kettle", "Beta lamp"]


def make_job(user, **fields):
    fields = {"site_name": site.name, "format": "csv", **fields}
    return ExportJob.objects.create(user=user, content_type=ContentType.objects.get_for_model(Item), **fields)


def test_exports_page_polls_while_a_job_runs(admin_client, admin_user):
    job = make_job(admin_user)

    def polling():
        soup = BeautifulSoup(admin_client.get(reverse("admin:exports")).content, "html.parser")
        return soup.select_one("#exports").has_attr("hx-trigger")

    assert polling()
    job.status = ExportJob.Status.FAILED
    job.save()
    assert not polling()


def test_download_is_for_the_job_owner_only(client, django_user_model, admin_user):
    job = make_job(admin_user, status=ExportJob.Status.DONE)
    other = django_user_model.objects.create_superuser("other", password="pw-12345")
    client.force_login(other)

    assert client.get(reverse("admin:export_download", args=[job.pk])).status_code == 404


def test_job_without_its_admin_fails_with_the_reason(admin_user):
    job = make_job(admin_user, query="", site_name="gone")

    with pytest.raises(LookupError):
        run_export_job(job.pk)

    job.refresh_from_db()
    assert job.status == ExportJob.Status.FAILED
    assert "gone" in job.error
