"""DateInput, and DateRangeField cleaning two inputs into one value."""

from __future__ import annotations

import datetime as dt

import pytest
from bs4 import BeautifulSoup

from django_formwork.fields import DateRange, DateRangeField
from django_formwork.forms import FormworkForm
from django_formwork.widgets import DateInput

from .conftest import render_widget


class _Form(FormworkForm):
    period = DateRangeField(
        max_span=dt.timedelta(days=31),
        label="Period",
        error_messages={"max_span": "Too long."},
    )


def _bound(start, end):
    return _Form(data={"period_0": start, "period_1": end})


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
def test_both_inputs_render_from_one_value():
    """One value renders both native inputs, each named for screen readers."""
    html = _Form(initial={"period": [dt.date(2026, 3, 1), dt.date(2026, 3, 10)]})["period"].as_widget()
    inputs = BeautifulSoup(html, "html.parser").select("input")
    assert [i["type"] for i in inputs] == ["date", "date"]
    assert [i["name"] for i in inputs] == ["period_0", "period_1"]
    assert [i["value"] for i in inputs] == ["2026-03-01", "2026-03-10"]
    assert [i["aria-label"] for i in inputs] == ["From", "To"]


@pytest.mark.unit
def test_the_pair_renders_as_one_labelled_group():
    """The field label is the group's one legend; neither input gets a <label>."""
    soup = BeautifulSoup(str(_Form()["period"].as_field_group()), "html.parser")
    assert [legend.get_text(strip=True) for legend in soup.select("legend")] == ["Period*"]
    assert soup.select("label") == []


@pytest.mark.unit
def test_the_pair_inputs_keep_their_ids_and_error_state():
    """Each input keeps its own id, and an error marks both invalid."""
    form = _bound("2026-03-10", "2026-03-01")
    form.is_valid()
    inputs = BeautifulSoup(str(form["period"].as_field_group()), "html.parser").select("input")
    assert [i["id"] for i in inputs] == ["id_period_0", "id_period_1"]
    assert all(i["aria-invalid"] == "true" for i in inputs)
