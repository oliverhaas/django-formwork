"""Browser tests for the rows of ``formset.as_rows``, with full widgets or with stubs."""

from datetime import date

import pytest
from admin_app.models import Category, Item, Tag
from playwright.sync_api import expect

from django_formwork import FormworkCellMixin, FormworkModelForm, formwork_modelformset_factory
from django_formwork.widgets import DatePicker, Select, SelectMultiple

pytestmark = pytest.mark.django_db(transaction=True)


class RowForm(FormworkModelForm):
    class Meta:
        model = Item
        fields = ["name", "category", "tags", "released"]
        widgets = {"category": Select(), "tags": SelectMultiple(), "released": DatePicker()}


RowFormSet = formwork_modelformset_factory(Item, form=RowForm, extra=0)


class RowCell(FormworkCellMixin):
    formset_class = RowFormSet
    queryset = Item.objects.all()


def rows():
    return RowFormSet(queryset=Item.objects.order_by("pk").prefetch_related("tags"))


@pytest.fixture
def items():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    Category.objects.create(name="Garden", slug="garden")
    tags = [Tag.objects.create(name=name) for name in ("eco", "new", "sale", "used")]
    for name, count, released in [("Kettle", 0, None), ("Lamp", 2, date(2026, 3, 4)), ("Toaster", 4, None)]:
        Item.objects.create(name=name, category=kitchen, released=released).tags.set(tags[:count])


def test_the_stubs_of_a_table_look_like_its_full_widgets_before_and_after_they_load(rows_page, items):
    rows_page.open(rows)
    full = rows_page.screenshot()
    rows_page.open(rows, RowCell)
    stubs = rows_page.page.locator("[data-formwork-stub]")
    expect(stubs).to_have_count(9)
    with_stubs = rows_page.screenshot()
    for count in range(stubs.count(), 0, -1):
        stubs.first.hover()
        expect(stubs).to_have_count(count - 1)
    rows_page.page.locator(".overflow-x-auto").evaluate("table => table.scrollTo(0, 0)")
    loaded = rows_page.screenshot()

    rows_page.assert_same_screens(full, with_stubs, "full", "stubs")
    rows_page.assert_same_screens(full, loaded, "full", "loaded")
    assert rows_page.errors == []


def test_a_select_multiple_stub_opens_as_the_full_select_on_the_first_press(rows_page, items):
    rows_page.open(rows, RowCell)
    lamp = rows_page.page.locator("tbody", has=rows_page.page.locator("[name$=-name][value=Lamp]"))
    tags = lamp.locator("details:has([name$=-tags])")

    tags.locator("summary").click()
    tags.get_by_role("option", name="used").click()

    expect(tags).to_have_attribute("x-data", "formworkSelectMultiple")
    expect(tags.locator("input[type=checkbox][name$=-tags]:checked")).to_have_count(3)
    assert rows_page.errors == []
