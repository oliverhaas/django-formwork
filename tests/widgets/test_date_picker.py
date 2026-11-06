from __future__ import annotations

import datetime as dt

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import DatePicker

from .conftest import render_form, render_widget


class DatePickerForm(FormworkForm):
    """Form fixture for DatePicker integration tests."""

    due_date = forms.DateField(widget=DatePicker, required=True)


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
def test_date_picker_template_calls_the_component_only():
    """Every Alpine attribute holds one call or a property, never a JS statement (D4)."""
    soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    wrapper = soup.find("div", attrs={"x-data": "formworkDatePicker"})
    assert wrapper["@click.outside"] == "close()"
    assert "@click.away" not in str(soup)
    handlers = [v for tag in soup.find_all() for k, v in tag.attrs.items() if k.startswith(("@", "x-on:"))]
    assert all(";" not in v and "=" not in v.replace("==", "") for v in handlers)


@pytest.mark.unit
def test_date_picker_weekday_names_come_from_django():
    """The weekday header is rendered by the server, so it follows the active language (D8)."""
    from django.utils import translation

    with translation.override("de"):
        soup = render_widget(DatePicker(), attrs={"id": "id_due_date"})
    header = [span.get_text() for span in soup.select("div.grid-cols-7 > span")]
    assert header[:2] == ["So", "Mo"]


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
    assert wrapper["data-value"] == payload


@pytest.mark.e2e
def test_date_picker_opens_and_picks_day(new_widgets_page):
    """Smoke: the calendar toggle opens the panel; picking a day fills the input."""
    import re

    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_due_date_datepicker")
    picker.locator("button.date-picker-toggle").click()
    panel = picker.locator("div.dropdown-content")
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="15", exact=True).click()
    inp = new_widgets_page.locator("input[name='due_date']")
    expect(inp).to_have_value(re.compile(r"^\d{4}-\d{2}-15$"))
    expect(panel).not_to_be_visible()
