from __future__ import annotations

import datetime as dt
import re

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.utils import translation

from django_formwork.forms import FormworkForm
from django_formwork.widgets import TimePicker

from .conftest import render_widget, submit


class OpensForm(FormworkForm):
    """A TimePicker next to a field that can fail on its own."""

    opens_at = forms.TimeField(widget=TimePicker(format="H:i"))
    note = forms.CharField()


def inputs(html):
    soup = BeautifulSoup(str(html), "html.parser")
    return soup.select_one("input[type=text]"), soup.select_one("input[type=hidden]")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "time_format", "text", "posted"),
    [
        (dt.time(14, 30), "TIME_FORMAT", "2:30 p.m.", "14:30"),
        (dt.time(9, 30, 15), "H:i", "09:30", "09:30:15"),
        ("21:05", "g:i A", "9:05 PM", "21:05"),
    ],
    ids=["time", "seconds", "iso"],
)
def test_time_picker_shows_its_format_and_posts_iso(value, time_format, text, posted):
    """The input shows the time in the widget's format; the hidden input posts it as HH:MM."""
    with translation.override("en"):
        shown, hidden = inputs(render_widget(TimePicker(format=time_format), value=value))
    assert (shown["value"], hidden["value"]) == (text, posted)


@pytest.mark.unit
def test_time_picker_input_fits_the_times_written_as_words():
    """The input is sized for midnight and noon, which a 12-hour format writes as words."""
    with translation.override("en"):
        soup = render_widget(TimePicker())
    assert {"midnight", "noon"} <= {span.get_text() for span in soup.select(".date-picker-sizer span")}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("time_format", "lists"),
    [("TIME_FORMAT", ["Hour", "Minute", "AM/PM"]), ("g:i A", ["Hour", "Minute", "AM/PM"]), ("H:i", ["Hour", "Minute"])],
)
def test_time_picker_offers_am_and_pm_for_a_12_hour_format(time_format, lists):
    """A 12-hour format gets a list of a.m. and p.m. next to the hours and minutes; a 24-hour one does not."""
    with translation.override("en"):
        soup = render_widget(TimePicker(format=time_format))
    assert [listbox["aria-label"] for listbox in soup.find_all(attrs={"role": "listbox"})] == lists


@pytest.mark.unit
def test_time_picker_puts_data_and_htmx_attrs_on_the_posted_input():
    """The hidden input carries data- and hx- attrs, which fire with its change; the rest stay on the text input."""
    attrs = {"id": "id_at", "class": "input-sm", "hx-post": "/save/", "data-autosave": "1"}
    shown, hidden = inputs(render_widget(TimePicker(), name="at", attrs=attrs))
    assert (hidden["name"], hidden["hx-post"], hidden["data-autosave"]) == ("at", "/save/", "1")
    assert (shown["id"], "input-sm" in shown["class"]) == ("id_at", True)
    assert not {"id", "class"} & set(hidden.attrs)
    assert not {"name", "hx-post", "data-autosave"} & set(shown.attrs)


@pytest.mark.unit
def test_time_picker_rejects_a_minute_step_below_one():
    """A step of zero minutes would list no minutes."""
    with pytest.raises(ValueError, match="minute_step"):
        TimePicker(minute_step=0)


@pytest.mark.integration
@pytest.mark.parametrize(("data", "text"), [("14:35:15", "14:35"), ("lunch", "lunch")])
def test_time_picker_shows_a_submitted_value_after_an_error(data, text):
    """A form with errors shows the posted time in the widget's format, and text that names none as typed."""
    form = OpensForm(data={"opens_at": data, "note": ""})
    assert not form.is_valid()
    shown, hidden = inputs(form["opens_at"])
    assert (shown["value"], hidden["value"]) == (text, data)


@pytest.mark.e2e
def test_time_picker_picks_an_hour_a_minute_and_pm(new_widgets_page):
    """Picks in the three lists make one time, Done posts it, and the server shows it back."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_opens_at_timepicker")
    panel = picker.locator("[role=dialog]")
    hidden = picker.locator("input[name='opens_at']")
    picker.locator("button.date-picker-toggle").click()
    panel.get_by_role("listbox", name="Hour").get_by_role("option", name="9", exact=True).click()
    panel.get_by_role("listbox", name="Minute").get_by_role("option", name="45", exact=True).click()
    panel.get_by_role("option", name="p.m.").click()
    expect(picker.locator("#id_opens_at")).to_have_value("9:45 p.m.")
    panel.get_by_role("button", name="Done").click()
    expect(panel).to_be_hidden()
    expect(hidden).to_have_value("21:45")
    submit(new_widgets_page)
    expect(hidden).to_have_attribute("value", "21:45")
    expect(picker.locator("#id_opens_at")).to_have_value("9:45 p.m.")


@pytest.mark.e2e
@pytest.mark.parametrize(("typed", "posted", "text"), [("2:35 pm", "14:35", "2:35 p.m."), ("noon", "12:00", "noon")])
def test_time_picker_reads_typed_text(new_widgets_page, typed, posted, text):
    """Text typed in the shown format, or as ISO, posts as HH:MM and reads back as the widget writes it."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("#id_opens_at")
    inp.fill(typed)
    inp.press("Enter")
    expect(new_widgets_page.locator("input[name='opens_at']")).to_have_value(posted)
    expect(inp).to_have_value(text)


@pytest.mark.e2e
def test_time_picker_moves_through_the_lists_by_keyboard(new_widgets_page):
    """Down goes from the input into the hours, Up and Down move in a list, Right goes to the next list."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("#id_opens_at")
    inp.focus()
    inp.press("ArrowDown")
    focused = new_widgets_page.locator("#id_opens_at_clock :focus")
    expect(focused).to_have_text("12")
    for key in ("ArrowDown", "ArrowDown", "Space", "ArrowRight", "End", "Space", "ArrowRight", "ArrowDown", "Space"):
        focused.press(key)
    expect(inp).to_have_value("2:55 p.m.")
    new_widgets_page.locator("#id_quantity").focus()
    expect(new_widgets_page.locator("input[name='opens_at']")).to_have_value("14:55")


@pytest.mark.e2e
def test_time_picker_lists_the_minutes_of_its_step_and_a_typed_one(new_widgets_page):
    """A 24-hour picker lists 0 to 23, minutes in its step, and a typed minute off the step."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_closes_at_timepicker")
    inp = picker.locator("#id_closes_at")
    inp.fill("21:40")
    inp.press("Enter")
    picker.locator("button.date-picker-toggle").click()
    hours = picker.get_by_role("listbox", name="Hour").get_by_role("option")
    expect(hours).to_have_count(24)
    expect(hours.first).to_have_text("00")
    minutes = picker.get_by_role("listbox", name="Minute").get_by_role("option")
    expect(minutes).to_have_text(["00", "15", "30", "40", "45"])
    expect(picker.get_by_role("option", name="40")).to_have_attribute("aria-selected", "true")
    expect(picker.get_by_role("listbox", name="AM/PM")).to_have_count(0)


@pytest.mark.e2e
def test_time_picker_now_and_clear(new_widgets_page):
    """Now posts the current minute; Clear empties the field."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_opens_at_timepicker")
    panel = picker.locator("[role=dialog]")
    hidden = picker.locator("input[name='opens_at']")
    picker.locator("button.date-picker-toggle").click()
    panel.get_by_role("button", name="Now").click()
    expect(hidden).to_have_value(re.compile(r"^\d{2}:\d{2}$"))
    picker.locator("button.date-picker-toggle").click()
    panel.get_by_role("button", name="Clear").click()
    expect(hidden).to_have_value("")
    expect(picker.locator("#id_opens_at")).to_have_value("")


@pytest.mark.e2e
def test_time_picker_leaves_a_stored_time_with_seconds_alone(new_widgets_page):
    """Leaving the input keeps the seconds of a stored time whose minute did not change, and fires no change."""
    from playwright.sync_api import expect

    picker = new_widgets_page.locator("#id_opens_at_timepicker")
    hidden = picker.locator("input[name='opens_at']")
    picker.evaluate("el => { el.dispatchEvent(new Event('formwork:start')); el.dataset.value = '09:30:15'; }")
    hidden.evaluate(
        "el => { el.value = '09:30:15'; el.addEventListener('change', () => { el.dataset.changed = '1'; }); }"
    )
    picker.locator("#id_opens_at").focus()
    new_widgets_page.locator("#id_quantity").focus()
    expect(hidden).to_have_value("09:30:15")
    expect(hidden).not_to_have_attribute("data-changed", "1")
