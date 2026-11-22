"""Browser tests for the rows of ``formset.as_rows``, with full widgets or with stubs."""

import datetime as dt

import pytest
from admin_app.models import Category, Item, Tag
from django.utils.datastructures import MultiValueDict
from playwright.sync_api import expect

from django_formwork import (
    DateRange,
    DateRangeField,
    DisplayField,
    FormworkCellMixin,
    FormworkModelForm,
    formwork_modelformset_factory,
)
from django_formwork.widgets import ChoiceLabel, ComboBox, ComboBoxMultiple, DatePicker, Select, SelectMultiple

pytestmark = pytest.mark.django_db(transaction=True)

_NAMES = [ChoiceLabel("Lamp", icon="\U0001f4a1"), "Kettle", "Toaster"]


class RowForm(FormworkModelForm):
    period = DateRangeField(required=False)

    class Meta:
        model = Item
        fields = ["name", "category", "tags", "released", "notes"]
        widgets = {
            "name": ComboBox(suggestions=_NAMES),
            "category": Select(),
            "tags": SelectMultiple(),
            "released": DatePicker(),
            "notes": ComboBoxMultiple(suggestions=_NAMES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        released = self.instance.released
        self.initial["period"] = DateRange(released, released and released + dt.timedelta(days=6))


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
    for name, count, released, notes in [
        ("Kettle", 0, None, ""),
        ("Lamp", 2, dt.date(2026, 3, 4), "Lamp, Kettle"),
        ("Toaster", 4, None, "Toaster"),
    ]:
        Item.objects.create(name=name, category=kitchen, released=released, notes=notes).tags.set(tags[:count])


def test_the_stubs_of_a_table_look_like_its_full_widgets_before_and_after_they_load(rows_page, items):
    rows_page.open(rows)
    full = rows_page.screenshot()
    rows_page.open(rows, RowCell)
    stubs = rows_page.page.locator("[data-formwork-stub]")
    expect(stubs).to_have_count(18)
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


def test_dates_typed_into_both_parts_of_a_range_stub_carry_over_to_the_full_picker(rows_page, items):
    rows_page.open(rows, RowCell)
    held = []
    rows_page.page.route("**/rows/cell/**", lambda route: held.append(route))  # noqa: PLW0108 (Playwright reads the handler's signature, which a builtin lacks)
    kettle = rows_page.page.locator("tbody", has=rows_page.page.locator("[name$=-name][value=Kettle]"))

    kettle.get_by_label("Start date").press_sequentially("2026-02-03")
    kettle.get_by_label("End date").press_sequentially("2026-02-09")
    held[0].fallback()
    expect(kettle.locator("[x-data=formworkDateRangePicker]")).to_be_attached()
    kettle.get_by_label("End date").blur()

    expect(kettle.locator("[name$=-period_0]")).to_have_value("2026-02-03")
    expect(kettle.locator("[name$=-period_1]")).to_have_value("2026-02-09")
    assert rows_page.errors == []


def test_a_press_on_the_icon_of_a_range_stub_opens_the_calendar_of_the_full_picker(rows_page, items):
    rows_page.open(rows, RowCell)
    kettle = rows_page.page.locator("tbody", has=rows_page.page.locator("[name$=-name][value=Kettle]"))

    kettle.locator(".icon-calendar-range").click()

    expect(kettle.get_by_role("dialog", name="Calendar")).to_be_visible()
    assert rows_page.errors == []


def test_a_press_on_the_icon_of_a_combo_box_stub_opens_the_suggestions_of_the_full_combo_box(rows_page, items):
    rows_page.open(rows, RowCell)
    lamp = rows_page.page.locator("tbody", has=rows_page.page.locator("[name$=-name][value=Lamp]"))
    name = lamp.locator(".formwork-combobox:has([name$=-name])")

    name.locator(".combobox-display").click()

    expect(name).to_have_attribute("x-data", "formworkComboBox")
    expect(name.locator("[name$=-name]")).to_be_focused()
    expect(name.get_by_role("listbox")).to_be_visible()


def _row(rows_page, name):
    return rows_page.page.locator("tbody", has=rows_page.page.locator(f"[name$=-name][value={name}]"))


def test_a_select_of_a_full_row_lists_the_options_of_its_column_and_marks_its_own(rows_page, items):
    rows_page.open(rows)
    category = _row(rows_page, "Lamp").locator("details:has([name$=-category])")

    category.locator("summary").click()
    expect(category.get_by_role("option", name="Kitchen")).to_have_attribute("aria-selected", "true")
    category.get_by_role("option", name="Garden").click()
    category.locator("summary").click()

    expect(category.get_by_role("option", name="Garden")).to_have_attribute("aria-selected", "true")
    expect(category.get_by_role("option", name="Kitchen")).to_have_attribute("aria-selected", "false")
    expect(category.locator("input[type=hidden][name$=-category]")).to_have_value(
        str(Category.objects.get(slug="garden").pk)
    )
    assert rows_page.errors == []


def test_a_select_multiple_of_a_full_row_posts_the_tags_picked_from_the_options_of_its_column(rows_page, items):
    rows_page.open(rows)
    tags = _row(rows_page, "Lamp").locator("details:has([name$=-tags])")

    tags.locator("summary").click()
    expect(tags.locator("input[type=checkbox]:checked")).to_have_count(2)
    tags.get_by_role("option", name="used").click()
    posted = rows_page.page.evaluate(
        """() => [...document.querySelectorAll("input[name]")]
          .filter((input) => !input.disabled && !(input.type === "checkbox" && !input.checked))
          .map((input) => [input.name, input.value])"""
    )
    data = MultiValueDict()
    for name, value in posted:
        data.appendlist(name, value)
    formset = RowFormSet(data, queryset=Item.objects.order_by("pk"))
    assert formset.is_valid(), formset.errors
    formset.save()

    tagged = {item.name: sorted(tag.name for tag in item.tags.all()) for item in Item.objects.all()}
    assert tagged == {"Kettle": [], "Lamp": ["eco", "new", "used"], "Toaster": ["eco", "new", "sale", "used"]}
    assert rows_page.errors == []


class BlurbForm(FormworkModelForm):
    blurb = DisplayField(max_lines=2, source=lambda item: " ".join([item.name] * (120 if item.name == "Lamp" else 1)))

    class Meta:
        model = Item
        fields = ["name"]


def blurbs():
    return formwork_modelformset_factory(Item, form=BlurbForm, extra=0)(queryset=Item.objects.order_by("pk"))


def test_a_value_cut_to_a_few_lines_opens_whole_on_more_and_a_short_one_offers_no_toggle(rows_page, items):
    rows_page.open(blurbs)
    lamp = _row(rows_page, "Lamp").locator(".formwork-clamp")
    toggle = lamp.locator("summary")
    cut = lamp.locator(".formwork-clamp-body").bounding_box()["height"]

    expect(_row(rows_page, "Kettle").locator(".formwork-clamp summary")).to_be_hidden()
    expect(toggle).to_be_visible()
    toggle.click()

    expect(lamp.locator("details")).to_have_attribute("open", "")
    assert lamp.locator(".formwork-clamp-body").bounding_box()["height"] > 2 * cut
    assert rows_page.errors == []


def test_a_line_separates_the_rows_of_a_table(rows_page, items):
    rows_page.open(blurbs)

    lines = rows_page.page.locator("tbody > tr:first-child > td:first-child").evaluate_all(
        "cells => cells.map(cell => getComputedStyle(cell).borderTopWidth)"
    )

    assert lines == ["0px", "1px", "1px"]
