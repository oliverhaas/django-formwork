from __future__ import annotations

import datetime as dt

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.utils import translation

from django_formwork.forms import FormworkForm
from django_formwork.widgets import DatePicker

from .conftest import render_form, render_widget


class DatePickerForm(FormworkForm):
    """Form fixture for DatePicker integration tests."""

    due_date = forms.DateField(widget=DatePicker, required=True)


class DayFirstForm(FormworkForm):
    """A day-first DatePicker next to a field that can fail on its own."""

    day = forms.DateField(widget=DatePicker(format="%d.%m.%Y"))
    note = forms.CharField()


@pytest.mark.unit
def test_date_picker_instantiation():
    """DatePicker has placeholder 'YYYY-MM-DD' by default."""
    widget = DatePicker()
    assert widget.attrs.get("placeholder") == "YYYY-MM-DD"


@pytest.mark.unit
def test_date_picker_custom_placeholder():
    """User-supplied placeholder overrides the default."""
    widget = DatePicker(attrs={"placeholder": "Pick a date"})
    assert widget.attrs.get("placeholder") == "Pick a date"


@pytest.mark.unit
def test_date_picker_custom_format_round_trips():
    """A custom format string formats the date value in both get_context and render."""
    widget = DatePicker(format="%d.%m.%Y")
    value = dt.date(2026, 7, 13)
    ctx = widget.get_context("due_date", value, {"id": "id_due_date"})
    assert ctx["widget"]["value"] == "13.07.2026"
    soup = render_widget(widget, name="due_date", value=value, attrs={"id": "id_due_date"})
    inp = soup.find("input", attrs={"name": "due_date"})
    assert inp["value"] == "13.07.2026"


@pytest.mark.unit
def test_date_picker_placeholder_follows_format():
    """A custom format derives a matching human placeholder."""
    widget = DatePicker(format="%d/%m/%Y")
    assert widget.attrs.get("placeholder") == "DD/MM/YYYY"


@pytest.mark.unit
def test_date_picker_explicit_placeholder_beats_derived_format():
    """An explicit placeholder still wins over the format-derived default."""
    widget = DatePicker(attrs={"placeholder": "Pick a date"}, format="%d/%m/%Y")
    assert widget.attrs.get("placeholder") == "Pick a date"


@pytest.mark.unit
def test_date_picker_renders_placeholder():
    """Rendered input contains the default placeholder 'YYYY-MM-DD'."""
    soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    inp = soup.find("input")
    assert inp is not None
    assert inp.get("placeholder") == "YYYY-MM-DD"


@pytest.mark.unit
def test_date_picker_renders_with_value():
    """A date value is reflected in the rendered input's value attribute."""
    widget = DatePicker()
    soup = render_widget(widget, value=dt.date(2024, 6, 15), attrs={"id": "id_due_date"})
    inp = soup.find("input")
    assert inp is not None
    assert inp.get("value") == "2024-06-15"


@pytest.mark.unit
def test_date_picker_alpine_x_data():
    """The wrapper div binds to the formworkDatePicker Alpine.data component."""
    widget = DatePicker()
    soup = render_widget(widget, value=dt.date(2024, 6, 15), attrs={"id": "id_due_date"})
    wrapper = soup.find("div", attrs={"x-data": "formworkDatePicker"})
    assert wrapper is not None
    assert wrapper["data-value"] == "2024-06-15"


@pytest.mark.unit
def test_date_picker_closes_through_click_outside():
    """The calendar closes through Alpine 3's @click.outside, not Alpine 2's @click.away."""
    soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    wrapper = soup.find("div", attrs={"x-data": "formworkDatePicker"})
    assert wrapper["@click.outside"] == "close()"
    assert "@click.away" not in str(soup)


@pytest.mark.unit
@pytest.mark.parametrize(("language", "first_days"), [("en", ["Sun", "Mon"]), ("de", ["Mo", "Di"])])
def test_date_picker_weekdays_follow_the_language(language, first_days):
    """The weekday header has the language's names and starts on its FIRST_DAY_OF_WEEK."""
    with translation.override(language):
        soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    header = [cell.get_text() for cell in soup.select("[role=columnheader]")]
    assert header[:2] == first_days
    assert len(header) == 7


@pytest.mark.unit
def test_date_picker_month_nav_buttons_have_aria_labels():
    """Prev/next month buttons carry aria-labels for assistive tech."""
    soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    labels = [b.get("aria-label") for b in soup.find_all("button")]
    assert "Previous month" in labels
    assert "Next month" in labels


@pytest.mark.integration
def test_date_picker_renders_via_form(renderer):
    """Field renders as a text input named after the form field."""
    form = DatePickerForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "due_date"})
    assert inp is not None
    assert inp.get("type") == "text"


@pytest.mark.integration
def test_date_picker_form_wraps_in_fieldset(renderer):
    """Field template wraps DatePicker in a fieldset with a stable id."""
    form = DatePickerForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_due_date_field")
    assert fieldset is not None


@pytest.mark.integration
def test_date_picker_error_state(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = DatePickerForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "due_date"})
    assert inp is not None
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_date_picker_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    form = DatePickerForm(prefix="sched")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "sched-due_date"})
    assert inp is not None
    assert inp["id"] == "id_sched-due_date"


@pytest.mark.integration
def test_date_picker_escapes_value_in_x_data(renderer):
    """SECURITY: the redisplayed raw value never lands in an executable context."""
    payload = "'}); alert(1); ({'"
    form = DatePickerForm(data={"due_date": payload})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", class_="date-picker")
    assert wrapper["x-data"] == "formworkDatePicker"
    assert wrapper["data-value"] == ""
    assert soup.find("input", attrs={"name": "due_date"})["value"] == payload


@pytest.mark.unit
@pytest.mark.parametrize("value", [dt.date(2026, 11, 6), "06/11/2026", "2026-11-06"])
def test_date_picker_calendar_value_is_iso_under_any_format(value):
    """The calendar gets ``YYYY-MM-DD`` while the input shows the configured format."""
    soup = render_widget(DatePicker(format="%d/%m/%Y"), value=value)
    assert soup.select_one("[x-data=formworkDatePicker]")["data-value"] == "2026-11-06"


@pytest.mark.integration
@pytest.mark.parametrize("text", ["13.07.2026", "2026-07-13"])
def test_date_picker_reads_its_format_where_the_language_lacks_it(text):
    """A date in the widget's format validates on an English page, as ISO does."""
    with translation.override("en"):
        form = DayFirstForm(data={"day": text, "note": "x"})
        assert form.is_valid(), form.errors
    assert form.cleaned_data["day"] == dt.date(2026, 7, 13)


@pytest.mark.integration
@pytest.mark.parametrize("text", ["13.07.2026", "2026-07-13"])
def test_date_picker_shows_a_submitted_date_in_its_format(text):
    """After a failed submit the input shows the date in the widget's format, however it was sent."""
    form = DayFirstForm(data={"day": text, "note": ""})
    assert not form.is_valid()
    inp = BeautifulSoup(str(form["day"]), "html.parser").find("input", attrs={"name": "day"})
    assert inp["value"] == "13.07.2026"


@pytest.mark.e2e
def test_date_picker_input_is_named_by_its_label_alone(new_widgets_page):
    """The calendar toggle's name stays out of the input's name; a click on the box still focuses the input."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("input[name='due_date']")
    expect(inp).to_have_accessible_name("Due date")
    new_widgets_page.locator("#id_due_date_datepicker .date-picker-label").click(position={"x": 4, "y": 4})
    expect(inp).to_be_focused()


@pytest.mark.e2e
def test_date_picker_opens_and_picks_day(new_widgets_page):
    """Smoke: the calendar toggle opens the panel; picking a day fills the input."""
    import re

    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_due_date_datepicker")
    picker.locator("button.date-picker-toggle").click()
    panel = picker.locator("div.dropdown-content")
    expect(panel).to_be_visible()
    panel.locator("button[data-date$='-15']").click()
    inp = new_widgets_page.locator("input[name='due_date']")
    expect(inp).to_have_value(re.compile(r"^\d{4}-\d{2}-15$"))
    expect(panel).not_to_be_visible()


@pytest.mark.e2e
def test_date_picker_writes_and_reads_its_format(new_widgets_page):
    """A picked day lands in the widget's format, and a day typed in that format is the one the calendar marks."""
    import re

    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_delivery_date_datepicker")
    inp = picker.locator("input[name='delivery_date']")
    panel = picker.locator("div.dropdown-content")
    picker.locator("button.date-picker-toggle").click()
    panel.locator("button[data-date$='-15']").click()
    expect(inp).to_have_value(re.compile(r"^15\.\d{2}\.\d{4}$"))
    inp.fill("14" + inp.input_value()[2:])
    expect(panel.locator("button[data-date$='-14']")).to_have_class(re.compile(r"\bcalendar-selected\b"))


@pytest.mark.e2e
def test_date_picker_escape_and_focus_leaving_close_the_calendar(new_widgets_page):
    """Escape closes the open calendar, and so does tabbing to another control."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("#id_due_date")
    panel = new_widgets_page.locator("#id_due_date_datepicker div.dropdown-content")
    inp.click()
    expect(panel).to_be_visible()
    inp.press("Escape")
    expect(panel).to_be_hidden()
    new_widgets_page.locator("#id_due_date_datepicker button.date-picker-toggle").click()
    expect(panel).to_be_visible()
    new_widgets_page.locator("#id_quantity").focus()
    expect(panel).to_be_hidden()
