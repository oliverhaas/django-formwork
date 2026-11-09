"""DateRangeField and DateTimeRangeField, their range pickers, and a plain MultiWidget pair."""

from __future__ import annotations

import datetime as dt
import json
import re
import zoneinfo

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.utils import dateformat, timezone, translation
from django.utils.formats import date_format

from django_formwork.fields import DateRange, DateRangeField, DateTimeRange, DateTimeRangeField
from django_formwork.forms import FormworkForm
from django_formwork.widgets import DateInput, DateRangePicker

from .conftest import render_widget


class _Form(FormworkForm):
    period = DateRangeField(
        max_span=dt.timedelta(days=31),
        label="Period",
        error_messages={"max_span": "Too long."},
    )


class _PairForm(FormworkForm):
    period = DateRangeField(
        widget=forms.MultiWidget([DateInput(attrs={"aria-label": "From"}), DateInput(attrs={"aria-label": "To"})]),
        label="Period",
    )


class _StayForm(FormworkForm):
    stay = DateTimeRangeField(label="Stay")


def _bound(start, end, form_class=_Form):
    return form_class(data={"period_0": start, "period_1": end})


def _soup(html):
    return BeautifulSoup(str(html), "html.parser")


@pytest.mark.unit
def test_date_input_is_native_with_an_iso_value():
    """The native control accepts only ISO dates, whatever the locale format."""
    inp = render_widget(DateInput(), name="day", value=dt.date(2026, 3, 1)).select_one("input")
    assert inp["type"] == "date"
    assert inp["value"] == "2026-03-01"


@pytest.mark.unit
@pytest.mark.parametrize("end", ["2026-03-10", "2026-04-01"])
def test_both_dates_clean_into_one_named_value(end):
    """A valid pair cleans to one ``DateRange``, up to ``max_span`` apart."""
    form = _bound("2026-03-01", end)
    assert form.is_valid()
    assert form.cleaned_data["period"] == DateRange(dt.date(2026, 3, 1), dt.date.fromisoformat(end))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("2026-03-10", "2026-03-01", "Start date must be before end date"),
        ("2026-01-01", "2026-03-01", "Too long."),
        ("2026-03-01", "", "This field is required."),
        ("", "", "This field is required."),
    ],
)
def test_invalid_ranges_report_one_error_for_the_pair(start, end, message):
    """An invalid pair gives one error for the field, not one per input."""
    form = _bound(start, end)
    assert not form.is_valid()
    assert form.errors["period"] == [message]


@pytest.mark.unit
def test_an_optional_range_accepts_two_empty_inputs():
    """An optional range cleans two empty inputs to ``DateRange(None, None)``."""

    class _OptionalForm(FormworkForm):
        period = DateRangeField(required=False)

    form = _OptionalForm(data={"period_0": "", "period_1": ""})
    assert form.is_valid()
    assert form.cleaned_data["period"] == DateRange(None, None)


@pytest.mark.unit
def test_a_zero_max_span_rejects_a_two_day_range():
    class _OneDayForm(FormworkForm):
        period = DateRangeField(max_span=dt.timedelta(0))

    form = _OneDayForm(data={"period_0": "2026-03-01", "period_1": "2026-03-02"})
    assert form.has_error("period", code="max_span")


@pytest.mark.unit
def test_a_datetime_range_cleans_both_ends_to_aware_datetimes():
    """Each end keeps its day and its time, in the current time zone."""
    form = _StayForm(data={"stay_0": "2026-03-01T09:30", "stay_1": "2026-03-03T17:00"})
    assert form.is_valid()
    assert form.cleaned_data["stay"] == DateTimeRange(
        dt.datetime(2026, 3, 1, 9, 30, tzinfo=timezone.get_current_timezone()),
        dt.datetime(2026, 3, 3, 17, 0, tzinfo=timezone.get_current_timezone()),
    )


@pytest.mark.unit
def test_a_datetime_range_rejects_an_end_before_the_start_on_the_same_day():
    form = _StayForm(data={"stay_0": "2026-03-01T17:00", "stay_1": "2026-03-01T09:30"})
    assert form.has_error("stay", code="start_after_end")


@pytest.mark.unit
def test_the_picker_posts_iso_and_shows_each_date_in_the_locale_format():
    """The hidden inputs hold ISO dates; the text inputs show them as DATE_FORMAT."""
    start, end = dt.date(2026, 3, 1), dt.date(2026, 3, 10)
    soup = _soup(_Form(initial={"period": DateRange(start, end)})["period"].as_widget())
    assert [i["value"] for i in soup.select("input[type=hidden]")] == ["2026-03-01", "2026-03-10"]
    texts = [i["value"] for i in soup.select("input.date-range-input")]
    assert texts == [date_format(start, "DATE_FORMAT"), date_format(end, "DATE_FORMAT")]


@pytest.mark.unit
def test_the_datetime_picker_shows_a_stored_range_in_the_current_time_zone():
    """An aware UTC value renders as the local wall time the user picked."""
    utc = dt.UTC
    initial = DateTimeRange(dt.datetime(2026, 3, 1, 12, 0, tzinfo=utc), dt.datetime(2026, 3, 2, 8, 0, tzinfo=utc))
    with timezone.override(zoneinfo.ZoneInfo("Europe/Berlin")):
        soup = _soup(_StayForm(initial={"stay": initial})["stay"].as_widget())
    assert [i["value"] for i in soup.select("input[type=hidden]")] == ["2026-03-01T13:00", "2026-03-02T09:00"]


@pytest.mark.unit
@pytest.mark.parametrize(("form_class", "end"), [(_Form, "2026-13-45"), (_StayForm, "2026-02-30T10:00")])
def test_posted_text_that_names_no_date_renders_as_typed_with_an_error(form_class, end):
    """Text the field rejects stays in its input, so the user can fix it."""
    name = next(iter(form_class.base_fields))
    form = form_class(data={f"{name}_0": "junk", f"{name}_1": end})
    assert not form.is_valid()
    soup = _soup(form[name].as_widget())
    assert [i["value"] for i in soup.select("input[type=hidden]")] == ["junk", end]
    assert [i["value"] for i in soup.select("input.date-range-input")] == ["junk", end]


@pytest.mark.unit
def test_the_inputs_are_grouped_under_the_field_label_and_both_carry_the_error_state():
    """The field label names the group of the two inputs, and an error marks both invalid."""
    form = _bound("2026-03-10", "2026-03-01")
    form.is_valid()
    soup = _soup(form["period"].as_field_group())
    assert soup.select_one("[role=group]")["aria-labelledby"] == "id_period_label"
    assert soup.select_one("#id_period_label").get_text(strip=True) == "Period*"
    inputs = soup.select("input.date-range-input")
    assert [i["id"] for i in inputs] == ["id_period", "id_period_end"]
    assert [i["aria-label"] for i in inputs] == ["Start date", "End date"]
    assert all(i["aria-invalid"] == "true" for i in inputs)


@pytest.mark.unit
def test_htmx_and_data_attrs_go_on_the_end_input_and_the_rest_on_the_start_input():
    """The end's hidden input fires ``change`` for the range, so request attrs ride on it."""
    widget = DateRangePicker(attrs={"hx-post": "/save/", "data-role": "range", "title": "Stay"})
    soup = render_widget(widget, name="period", attrs={"id": "id_period"})
    start, end = soup.select("input[type=hidden]")
    assert (end["hx-post"], end["data-role"]) == ("/save/", "range")
    assert "hx-post" not in start.attrs
    typed = soup.select_one("input#id_period")
    assert typed["title"] == "Stay"
    assert "hx-post" not in typed.attrs


def _presets(widget):
    return [
        (button.get_text(strip=True), button["data-start"], button["data-end"])
        for button in render_widget(widget, name="period").select(".calendar-presets button")
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        (
            dt.datetime(2026, 11, 9, 12, tzinfo=dt.UTC),
            "UTC",
            [
                ("Today", "2026-11-09", "2026-11-09"),
                ("Past 7 days", "2026-11-03", "2026-11-09"),
                ("This month", "2026-11-01", "2026-11-30"),
                ("This year", "2026-01-01", "2026-12-31"),
            ],
        ),
        (
            dt.datetime(2026, 12, 31, 23, 30, tzinfo=dt.UTC),
            "Europe/Berlin",
            [
                ("Today", "2027-01-01", "2027-01-01"),
                ("Past 7 days", "2026-12-26", "2027-01-01"),
                ("This month", "2027-01-01", "2027-01-31"),
                ("This year", "2027-01-01", "2027-12-31"),
            ],
        ),
    ],
    ids=["mid_month", "new_year_in_the_current_time_zone"],
)
def test_presets_cover_today_the_past_week_this_month_and_this_year(monkeypatch, now, zone, expected):
    """The days count in the current time zone, as Django's admin date filter counts them."""
    monkeypatch.setattr(timezone, "now", lambda: now)
    with timezone.override(zoneinfo.ZoneInfo(zone)), translation.override("en"):
        assert _presets(DateRangePicker(presets=True)) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("presets", "expected"),
    [
        (False, []),
        (
            lambda today: [("Next week", today + dt.timedelta(days=1), today + dt.timedelta(days=7))],
            [("Next week", "2026-11-10", "2026-11-16")],
        ),
    ],
    ids=["off_by_default", "function_of_today"],
)
def test_presets_come_from_a_function_of_today(monkeypatch, presets, expected):
    monkeypatch.setattr(timezone, "now", lambda: dt.datetime(2026, 11, 9, 12, tzinfo=dt.UTC))
    with timezone.override(zoneinfo.ZoneInfo("UTC")):
        assert _presets(DateRangePicker(presets=presets)) == expected


@pytest.mark.unit
@pytest.mark.parametrize(("language", "longest"), [("en", "Sept. 28, 2026"), ("de", "28. September 2026")])
def test_each_input_is_as_wide_as_the_longest_date_the_format_writes(language, longest):
    """The end input keeps its place whatever the start holds."""
    with translation.override(language):
        field = render_widget(DateRangePicker(), name="period").select_one(".date-range-field")
    assert field["style"] == f"--date-range-width: {len(longest) + 1}ch"


@pytest.mark.unit
def test_the_input_pair_renders_both_native_inputs_from_one_value():
    """One value renders both native inputs, each named for screen readers."""
    html = _PairForm(initial={"period": DateRange(dt.date(2026, 3, 1), dt.date(2026, 3, 10))})["period"].as_widget()
    inputs = _soup(html).select("input")
    assert [i["type"] for i in inputs] == ["date", "date"]
    assert [i["name"] for i in inputs] == ["period_0", "period_1"]
    assert [i["value"] for i in inputs] == ["2026-03-01", "2026-03-10"]
    assert [i["aria-label"] for i in inputs] == ["From", "To"]


@pytest.mark.unit
def test_the_input_pair_renders_as_one_labelled_group():
    """The field label is the group's one legend; neither input gets a <label>."""
    soup = _soup(_PairForm()["period"].as_field_group())
    assert [legend.get_text(strip=True) for legend in soup.select("legend")] == ["Period*"]
    assert soup.select("label") == []
    assert [i.get("value") for i in soup.select("input")] == [None, None]


@pytest.mark.unit
@pytest.mark.parametrize(("end", "changed"), [("2026-03-10", False), ("2026-03-11", True)])
def test_the_input_pair_compares_posted_dates_with_the_initial_range(end, changed):
    form = _PairForm(
        data={"period_0": "2026-03-01", "period_1": end},
        initial={"period": DateRange(dt.date(2026, 3, 1), dt.date(2026, 3, 10))},
    )
    assert form.has_changed() is changed


@pytest.mark.unit
def test_the_input_pair_keeps_its_ids_and_marks_both_invalid():
    """Each input keeps its own id, and an error marks both invalid."""
    form = _bound("2026-03-10", "2026-03-01", form_class=_PairForm)
    form.is_valid()
    inputs = _soup(form["period"].as_field_group()).select("input")
    assert [i["id"] for i in inputs] == ["id_period_0", "id_period_1"]
    assert all(i["aria-invalid"] == "true" for i in inputs)


def _first_month_day(panel, day):
    button = panel.locator(f".calendar-days > .calendar-month:first-child button[data-date$='-{day}']")
    return button, button.get_attribute("data-date")


@pytest.mark.e2e
def test_a_range_picked_in_the_calendar_saves_and_renders_after_a_reload(new_widgets_page):
    """A pick before the start begins the range again; the second pick ends it and closes the panel."""
    from playwright.sync_api import expect

    page = new_widgets_page
    trigger = page.locator("#id_period")
    panel = page.locator("#id_period_calendar")
    trigger.click()
    expect(panel).to_be_visible()
    later, _ = _first_month_day(panel, "20")
    earlier, start = _first_month_day(panel, "10")
    last, end = _first_month_day(panel, "14")
    later.click()
    earlier.click()
    last.click()
    expect(panel).to_be_hidden()
    expect(page.locator("input[name='period_0']")).to_have_value(start)
    expect(page.locator("input[name='period_1']")).to_have_value(end)
    page.get_by_role("button", name="Submit").click()
    expect(page.get_by_role("button", name="Delete")).to_be_visible()
    page.reload()
    expect(page.locator("input[name='period_0']")).to_have_value(start)
    expect(page.locator("input[name='period_1']")).to_have_value(end)
    expect(trigger).to_have_value(date_format(dt.date.fromisoformat(start), "DATE_FORMAT"))


@pytest.mark.e2e
def test_a_datetime_range_posts_the_times_picked_under_the_calendar(new_widgets_page):
    from playwright.sync_api import expect

    page = new_widgets_page
    panel = page.locator("#id_stay_calendar")
    page.locator("#id_stay").click()
    first, start = _first_month_day(panel, "10")
    last, end = _first_month_day(panel, "14")
    first.click()
    last.click()
    expect(panel).to_be_visible()
    panel.get_by_label("Start time").fill("09:30")
    panel.get_by_label("End time").fill("17:00")
    panel.get_by_role("button", name="Done").click()
    expect(panel).to_be_hidden()
    expect(page.locator("input[name='stay_0']")).to_have_value(f"{start}T09:30")
    expect(page.locator("input[name='stay_1']")).to_have_value(f"{end}T17:00")


@pytest.mark.e2e
def test_a_range_whose_start_alone_changes_marks_the_field_dirty(new_widgets_page):
    """The picker fires ``change`` on the end input, yet a new start with the same end is a change too."""
    from playwright.sync_api import expect

    page = new_widgets_page
    trigger = page.locator("#id_period")
    panel = page.locator("#id_period_calendar")
    trigger.click()
    _first_month_day(panel, "10")[0].click()
    _first_month_day(panel, "14")[0].click()
    page.evaluate("""() => {
        document.querySelector('form[hx-post]').setAttribute('data-formwork-dirty', '');
        document.dispatchEvent(new Event('htmx:after:swap'));
    }""")
    fieldset = page.locator("#id_period_field")
    trigger.click()
    _first_month_day(panel, "12")[0].click()
    _first_month_day(panel, "14")[0].click()
    expect(fieldset).to_have_class(re.compile(r"\bformwork-dirty\b"))


@pytest.mark.e2e
def test_a_click_on_the_end_date_changes_the_end_alone(new_widgets_page):
    from playwright.sync_api import expect

    page = new_widgets_page
    trigger = page.locator("#id_period")
    panel = page.locator("#id_period_calendar")
    trigger.click()
    first, start = _first_month_day(panel, "10")
    last, _ = _first_month_day(panel, "14")
    later, end = _first_month_day(panel, "20")
    first.click()
    last.click()
    page.locator("#id_period_end").click()
    later.click()
    expect(panel).to_be_hidden()
    expect(page.locator("input[name='period_0']")).to_have_value(start)
    expect(page.locator("input[name='period_1']")).to_have_value(end)


@pytest.mark.e2e
def test_typed_dates_post_as_iso_and_read_back_in_the_locale_format(new_widgets_page):
    """A typed start moves the calendar to its month; Tab goes on to the end, and leaving commits."""
    from playwright.sync_api import expect

    page = new_widgets_page
    start = page.locator("#id_period")
    end = page.locator("#id_period_end")
    start.fill("3/1/2030")
    expect(page.locator("#id_period_calendar [data-date='2030-03-01']")).to_have_class(re.compile("calendar-selected"))
    start.press("Tab")
    expect(end).to_be_focused()
    end.press_sequentially("mar 10 2030")
    end.press("Tab")
    expect(page.locator("#id_period_calendar")).to_be_hidden()
    expect(page.locator("input[name='period_0']")).to_have_value("2030-03-01")
    expect(page.locator("input[name='period_1']")).to_have_value("2030-03-10")
    expect(start).to_have_value(date_format(dt.date(2030, 3, 1), "DATE_FORMAT"))
    expect(end).to_have_value(date_format(dt.date(2030, 3, 10), "DATE_FORMAT"))


@pytest.mark.e2e
def test_a_preset_picks_its_range_and_closes_the_calendar(new_widgets_page):
    from playwright.sync_api import expect

    page = new_widgets_page
    today = timezone.localdate()
    page.locator("#id_period").click()
    page.get_by_role("button", name="Past 7 days").click()
    expect(page.locator("#id_period_calendar")).to_be_hidden()
    expect(page.locator("input[name='period_0']")).to_have_value((today - dt.timedelta(days=6)).isoformat())
    expect(page.locator("input[name='period_1']")).to_have_value(today.isoformat())
    page.locator("#id_period").click()
    expect(page.get_by_role("button", name="Past 7 days")).to_have_attribute("aria-current", "true")
    expect(page.get_by_role("button", name="Today")).not_to_have_attribute("aria-current", "true")


@pytest.mark.e2e
def test_an_end_typed_before_the_start_posts_as_typed_and_gets_the_field_error(new_widgets_page):
    """The picker never swaps the ends: the field reports the order."""
    from playwright.sync_api import expect

    page = new_widgets_page
    page.locator("#id_period").fill("3/10/2030")
    page.locator("#id_period_end").fill("3/1/2030")
    page.locator("#id_period_end").press("Enter")
    expect(page.locator("input[name='period_0']")).to_have_value("2030-03-10")
    expect(page.locator("input[name='period_1']")).to_have_value("2030-03-01")
    page.get_by_role("button", name="Submit").click()
    expect(page.locator("#id_period_field")).to_contain_text("Start date must be before end date")
    expect(page.locator("#id_period")).to_have_attribute("aria-invalid", "true")


@pytest.mark.e2e
def test_a_datetime_range_reads_typed_times(new_widgets_page):
    from playwright.sync_api import expect

    page = new_widgets_page
    page.locator("#id_stay").fill("3/1/2030 14:30")
    page.locator("#id_stay_end").fill("Mar. 3, 2030, 9 a.m.")
    page.locator("#id_stay_end").press("Enter")
    expect(page.locator("input[name='stay_0']")).to_have_value("2030-03-01T14:30")
    expect(page.locator("input[name='stay_1']")).to_have_value("2030-03-03T09:00")


_READ_CASES = {
    "en": [
        ("Nov. 8, 2026", "2026-11-08"),
        ("nov 8 2026", "2026-11-08"),
        ("November 8, 2026", "2026-11-08"),
        ("Sept 30 2026", "2026-09-30"),
        ("11/8/2026", "2026-11-08"),
        ("11/08/26", "2026-11-08"),
        ("2026-11-08", "2026-11-08"),
        ("8 November 2026", "2026-11-08"),
        ("Nov. 31, 2026", None),
        ("Nov. 8", None),
        ("2026-11-08x", None),
        ("soon", None),
    ],
    "de": [
        ("8.11.2026", "2026-11-08"),
        ("08.11.26", "2026-11-08"),
        ("3. märz 2026", "2026-03-03"),
        ("3 März 2026", "2026-03-03"),
        ("2026-03-03", "2026-03-03"),
        ("30.2.2026", None),
    ],
}


def _read_dates(page, widget, texts):
    """What the calendar script reads from each text, with the formats and names the widget renders."""
    data = render_widget(widget, name="period").select_one("[data-names]")
    return page.evaluate(
        """async ([texts, formats, inputFormats, names]) => {
            const { readDate } = await import("/static/formwork/widgets/_calendar.js");
            return texts.map((text) => readDate(text, [formats.value, formats.label], inputFormats, names));
        }""",
        [texts, *(json.loads(data[key]) for key in ("data-formats", "data-input-formats", "data-names"))],
    )


@pytest.mark.e2e
@pytest.mark.parametrize("language", ["en", "de"])
def test_the_calendar_script_reads_dates_typed_in_the_locale_formats(new_widgets_page, language):
    """Typed text in the display format or an input format reads as its day; case and dots do not matter."""
    with translation.override(language):
        read = _read_dates(new_widgets_page, DateRangePicker(), [text for text, _ in _READ_CASES[language]])
    assert [day and day["iso"] for day in read] == [iso for _, iso in _READ_CASES[language]]


@pytest.mark.e2e
def test_the_calendar_script_reads_the_times_of_typed_datetimes(new_widgets_page):
    from django_formwork.widgets import DateTimeRangePicker

    texts = [
        "Nov. 8, 2026, 3:30 p.m.",
        "Nov. 8, 2026, midnight",
        "Nov. 8, 2026, noon",
        "2026-11-08 14:30",
        "Nov. 8, 2026",
    ]
    with translation.override("en"):
        read = _read_dates(new_widgets_page, DateTimeRangePicker(), texts)
    assert read == [
        {"iso": "2026-11-08", "time": "15:30"},
        {"iso": "2026-11-08", "time": "00:00"},
        {"iso": "2026-11-08", "time": "12:00"},
        {"iso": "2026-11-08", "time": "14:30"},
        {"iso": "2026-11-08", "time": ""},
    ]


_EVERY_CODE = "a A b d D E f F g G h H i j l L m M n N o P s S t w W y Y z c"
_ESCAPED = r"\Y\-m \\d j\."
_MOMENTS = [
    (2026, 1, 1, 0, 0),
    (2026, 3, 9, 12, 0),
    (2026, 7, 4, 12, 30),
    (2026, 9, 21, 9, 5),
    (2026, 12, 31, 23, 59),
    (2024, 12, 30, 0, 1),
    (2021, 1, 3, 18, 45),
    (2020, 2, 29, 11, 59),
]


@pytest.mark.e2e
@pytest.mark.parametrize("language", ["en", "de"])
def test_the_calendar_script_writes_each_format_code_as_django_does(new_widgets_page, language):
    """The script writes dates in the browser as django.utils.dateformat writes them, names included."""
    with translation.override(language):
        names = json.loads(render_widget(DateRangePicker(format=_EVERY_CODE)).select_one("[data-names]")["data-names"])
        moments = [dt.datetime(*moment, tzinfo=dt.UTC).replace(tzinfo=None) for moment in _MOMENTS]
        expected = [[dateformat.format(moment, code) for code in (_EVERY_CODE, _ESCAPED)] for moment in moments]
    written = new_widgets_page.evaluate(
        """async ([moments, formats, names]) => {
            const { formatDjango } = await import("/static/formwork/widgets/_calendar.js");
            return moments.map(([y, mo, d, h, mi]) => formats.map((f) => formatDjango(new Date(y, mo - 1, d, h, mi), f, names)));
        }""",
        [_MOMENTS, [_EVERY_CODE, _ESCAPED], names],
    )
    assert written == expected
