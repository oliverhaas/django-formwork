from __future__ import annotations

import datetime as dt
import re

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.utils import timezone, translation

from django_formwork.forms import FormworkForm
from django_formwork.widgets import DateTimePicker

from .conftest import render_widget, submit


class StartsForm(FormworkForm):
    """A DateTimePicker next to a field that can fail on its own."""

    starts_at = forms.DateTimeField(widget=DateTimePicker(format="d.m.Y H:i"))
    note = forms.CharField()


def inputs(html):
    soup = BeautifulSoup(str(html), "html.parser")
    return soup.select_one("input[type=text]"), soup.select_one("input[type=hidden]")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "text", "posted"),
    [
        (dt.datetime(2026, 7, 13, 9, 30, tzinfo=dt.UTC), "13.07.2026 11:30", "2026-07-13T11:30"),
        (dt.datetime(2026, 7, 13, 9, 30, 15, tzinfo=dt.UTC), "13.07.2026 11:30", "2026-07-13T11:30:15"),
        ("2026-07-13T11:30", "13.07.2026 11:30", "2026-07-13T11:30"),
        (dt.date(2026, 7, 13), "13.07.2026 00:00", "2026-07-13T00:00"),
    ],
    ids=["aware", "seconds", "iso", "date"],
)
def test_date_time_picker_shows_its_format_and_posts_local_iso(value, text, posted):
    """The input shows the value in the widget's format; the hidden input posts it as local ISO."""
    with timezone.override("Europe/Berlin"):
        shown, hidden = inputs(render_widget(DateTimePicker(format="d.m.Y H:i"), value=value))
    assert (shown["value"], hidden["value"]) == (text, posted)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("date_format", "placeholder"),
    [("d.m.Y H:i", "DD.MM.YYYY hh:mm"), ("SHORT_DATETIME_FORMAT", "MM/DD/YYYY hh:mm a.m.")],
)
def test_date_time_picker_placeholder_spells_its_format(date_format, placeholder):
    """The placeholder spells out the format the input shows."""
    with translation.override("en"):
        shown, _ = inputs(render_widget(DateTimePicker(format=date_format)))
    assert shown["placeholder"] == placeholder


@pytest.mark.unit
def test_date_time_picker_puts_data_and_htmx_attrs_on_the_posted_input():
    """The hidden input carries data- and hx- attrs, which fire with its change; the rest stay on the text input."""
    attrs = {"id": "id_when", "class": "input-sm", "hx-post": "/save/", "data-autosave": "1"}
    shown, hidden = inputs(render_widget(DateTimePicker(), name="when", attrs=attrs))
    assert (hidden["name"], hidden["hx-post"], hidden["data-autosave"]) == ("when", "/save/", "1")
    assert (shown["id"], "input-sm" in shown["class"]) == ("id_when", True)
    assert not {"id", "class"} & set(hidden.attrs)
    assert not {"name", "hx-post", "data-autosave"} & set(shown.attrs)


@pytest.mark.integration
def test_date_time_picker_posts_a_value_the_field_cleans():
    """The posted ISO value cleans to an aware datetime in the current time zone."""
    with timezone.override("Europe/Berlin"):
        form = StartsForm(data={"starts_at": "2026-07-13T09:30", "note": "x"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["starts_at"] == dt.datetime(2026, 7, 13, 7, 30, tzinfo=dt.UTC)


@pytest.mark.integration
@pytest.mark.parametrize(("data", "text"), [("2026-07-13T09:30:15", "13.07.2026 09:30"), ("noon", "noon")])
def test_date_time_picker_shows_a_submitted_value_after_an_error(data, text):
    """A form with errors shows the posted day and time in the widget's format, and text that names none as typed."""
    form = StartsForm(data={"starts_at": data, "note": ""})
    assert not form.is_valid()
    shown, hidden = inputs(form["starts_at"])
    assert (shown["value"], hidden["value"]) == (text, data)


@pytest.mark.e2e
def test_date_time_picker_picks_a_day_and_a_time(new_widgets_page):
    """A picked day keeps the calendar open for the time, Done posts both, and the server shows them back."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_starts_at_datetimepicker")
    panel = picker.locator("div.dropdown-content")
    hidden = picker.locator("input[name='starts_at']")
    picker.locator("button.date-picker-toggle").click()
    panel.locator("button[data-date$='-15']").click()
    expect(panel).to_be_visible()
    panel.locator("input[type=time]").fill("21:45")
    panel.get_by_role("button", name="Done").click()
    expect(panel).to_be_hidden()
    expect(hidden).to_have_value(re.compile(r"^\d{4}-\d{2}-15T21:45$"))
    submit(new_widgets_page)
    expect(hidden).to_have_attribute("value", re.compile(r"^\d{4}-\d{2}-15T21:45$"))
    expect(picker.locator("#id_starts_at")).to_have_value(re.compile(r"^\d{2}/15/\d{4} 9:45 p\.m\.$"))


@pytest.mark.e2e
def test_date_time_picker_reads_typed_text(new_widgets_page):
    """Text typed in the shown format posts as ISO and reads back as the widget writes it."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("#id_starts_at")
    inp.fill("7/13/2026 9:30 pm")
    inp.press("Enter")
    expect(new_widgets_page.locator("input[name='starts_at']")).to_have_value("2026-07-13T21:30")
    expect(inp).to_have_value("07/13/2026 9:30 p.m.")


@pytest.mark.e2e
def test_date_time_picker_now_and_clear(new_widgets_page):
    """Now posts the current day and minute; Clear empties the field."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_starts_at_datetimepicker")
    panel = picker.locator("div.dropdown-content")
    hidden = picker.locator("input[name='starts_at']")
    today = new_widgets_page.evaluate("new Date().toLocaleDateString('sv')")
    picker.locator("button.date-picker-toggle").click()
    panel.get_by_role("button", name="Now").click()
    expect(hidden).to_have_value(re.compile(rf"^{today}T\d{{2}}:\d{{2}}$"))
    picker.locator("button.date-picker-toggle").click()
    panel.get_by_role("button", name="Clear").click()
    expect(hidden).to_have_value("")
    expect(picker.locator("#id_starts_at")).to_have_value("")


@pytest.mark.e2e
def test_date_time_picker_leaves_a_stored_time_with_seconds_alone(new_widgets_page):
    """Leaving the input keeps the seconds of a stored time whose minute did not change, and fires no change."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_starts_at_datetimepicker")
    hidden = picker.locator("input[name='starts_at']")
    picker.evaluate(
        "el => { el.dispatchEvent(new Event('formwork:start')); el.dataset.value = '2026-07-13T09:30:15'; }"
    )
    hidden.evaluate(
        "el => { el.value = '2026-07-13T09:30:15'; el.addEventListener('change', () => { el.dataset.changed = '1'; }); }"
    )
    picker.locator("#id_starts_at").focus()
    new_widgets_page.locator("#id_quantity").focus()
    expect(hidden).to_have_value("2026-07-13T09:30:15")
    expect(hidden).not_to_have_attribute("data-changed", "1")
