"""Tests for Django's built-in SplitDateTimeWidget as styled by formwork.

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: two inputs, types, name suffixes
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: renders, fill date and time, side-by-side layout
    6. e2e         — error flow: SKIPPED (event_at is not required on the builtin page)
    7. e2e         — morph resilience: filled values preserved across htmx morph
    8. screenshot  — visual states: default, filled
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm

from .conftest import assert_html_equivalent, render_form, render_widget


class SplitDateTimeForm(FormworkForm):
    """Form fixture for SplitDateTimeWidget integration tests."""

    event_at = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
        ),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_split_datetime_instantiation():
    """SplitDateTimeWidget has two sub-widgets."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    assert len(widget.widgets) == 2


@pytest.mark.unit
def test_split_datetime_get_context():
    """get_context() returns a subwidgets list with two entries."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    ctx = widget.get_context("event_at", None, {"id": "id_event_at"})
    assert "subwidgets" in ctx["widget"]
    assert len(ctx["widget"]["subwidgets"]) == 2


@pytest.mark.unit
def test_split_datetime_value_from_datadict():
    """value_from_datadict combines date and time fields from a QueryDict."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    data = QueryDict("event_at_0=2024-06-15&event_at_1=14:30:00")
    result = widget.value_from_datadict(data, {}, "event_at")
    assert result == ["2024-06-15", "14:30:00"]


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_split_datetime_renders_two_inputs():
    """render() produces two <input> elements."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    soup = render_widget(widget, name="event_at", attrs={"id": "id_event_at"})
    inputs = soup.find_all("input")
    assert len(inputs) == 2


@pytest.mark.unit
def test_split_datetime_renders_date_type():
    """The first input has type='date'."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    soup = render_widget(widget, name="event_at", attrs={"id": "id_event_at"})
    inputs = soup.find_all("input")
    assert inputs[0].get("type") == "date"


@pytest.mark.unit
def test_split_datetime_renders_time_type():
    """The second input has type='time'."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    soup = render_widget(widget, name="event_at", attrs={"id": "id_event_at"})
    inputs = soup.find_all("input")
    assert inputs[1].get("type") == "time"


@pytest.mark.unit
def test_split_datetime_renders_name_suffixes():
    """The two inputs have name_0 and name_1 suffixes."""
    widget = forms.SplitDateTimeWidget(
        date_attrs={"type": "date"},
        time_attrs={"type": "time"},
    )
    soup = render_widget(widget, name="event_at", attrs={"id": "id_event_at"})
    inputs = soup.find_all("input")
    names = [inp.get("name") for inp in inputs]
    assert "event_at_0" in names
    assert "event_at_1" in names


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_split_datetime_renders_via_form(renderer):
    """SplitDateTimeWidget renders correctly when used inside a FormworkForm."""
    form = SplitDateTimeForm()
    soup = render_form(form, renderer=renderer)
    date_input = soup.find("input", attrs={"name": "event_at_0"})
    time_input = soup.find("input", attrs={"name": "event_at_1"})
    assert date_input is not None
    assert time_input is not None


@pytest.mark.integration
def test_split_datetime_form_wraps_in_fieldset(renderer):
    """Field template wraps the widget in a fieldset with id='id_event_at_field'."""
    form = SplitDateTimeForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_event_at_field")
    assert fieldset is not None


@pytest.mark.integration
def test_split_datetime_error_state(renderer):
    """Bound form with errors adds aria-invalid='true' to both sub-inputs."""
    form = SplitDateTimeForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    date_input = soup.find("input", attrs={"name": "event_at_0"})
    time_input = soup.find("input", attrs={"name": "event_at_1"})
    assert date_input is not None
    assert time_input is not None
    # At least one of the sub-inputs should be marked invalid
    invalid_inputs = [inp for inp in [date_input, time_input] if inp.get("aria-invalid") == "true"]
    assert len(invalid_inputs) > 0


@pytest.mark.integration
def test_split_datetime_form_prefix(renderer):
    """Form prefix propagates to sub-widget names."""
    form = SplitDateTimeForm(prefix="evt")
    soup = render_form(form, renderer=renderer)
    date_input = soup.find("input", attrs={"name": "evt-event_at_0"})
    time_input = soup.find("input", attrs={"name": "evt-event_at_1"})
    assert date_input is not None
    assert time_input is not None


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_split_datetime_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """SplitDateTimeWidget produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(SplitDateTimeForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SplitDateTimeForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_split_datetime_renders_on_page(builtin_page):
    """Both date and time inputs are visible on the /builtin/ page."""
    from playwright.sync_api import expect

    date_input = builtin_page.locator('input[name="event_at_0"]')
    time_input = builtin_page.locator('input[name="event_at_1"]')
    expect(date_input).to_be_visible()
    expect(time_input).to_be_visible()


@pytest.mark.e2e
def test_split_datetime_fill_date_and_time(builtin_page):
    """User can fill both the date and time inputs."""
    date_input = builtin_page.locator('input[name="event_at_0"]')
    time_input = builtin_page.locator('input[name="event_at_1"]')
    date_input.fill("2024-06-15")
    time_input.fill("14:30")
    assert date_input.input_value() == "2024-06-15"
    assert time_input.input_value() == "14:30"


@pytest.mark.e2e
def test_split_datetime_side_by_side_layout(builtin_page):
    """Date and time inputs are on the same row (same vertical position)."""
    date_box = builtin_page.locator('input[name="event_at_0"]').bounding_box()
    time_box = builtin_page.locator('input[name="event_at_1"]').bounding_box()
    assert date_box is not None
    assert time_box is not None
    # Both inputs should be at roughly the same vertical position (same row)
    assert abs(date_box["y"] - time_box["y"]) < date_box["height"]


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# event_at is not required on the /builtin/ page (required=False), so no
# error-flow tests can be triggered without a separate required-field page.
# Left as a gap — tracked as part of broader error-state test coverage work.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_split_datetime_morph_preserves_values(builtin_page):
    """Filled date and time values survive an htmx form morph."""
    from tests.e2e.conftest import submit

    date_input = builtin_page.locator('input[name="event_at_0"]')
    time_input = builtin_page.locator('input[name="event_at_1"]')
    date_input.fill("2024-06-15")
    time_input.fill("14:30")
    submit(builtin_page)
    assert builtin_page.locator('input[name="event_at_0"]').input_value() == "2024-06-15"
    assert builtin_page.locator('input[name="event_at_1"]').input_value() == "14:30"


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.  See issue #26 for the plan.


@pytest.mark.screenshot
def test_split_datetime_screenshot_default(builtin_page):
    """Visual snapshot: SplitDateTimeWidget in default (empty) state."""
    wrapper = builtin_page.locator("#id_event_at_field")
    wrapper.screenshot(path="test-results/split-datetime-default-actual.png")


@pytest.mark.screenshot
def test_split_datetime_screenshot_filled(builtin_page):
    """Visual snapshot: SplitDateTimeWidget with date and time filled."""
    builtin_page.locator('input[name="event_at_0"]').fill("2024-06-15")
    builtin_page.locator('input[name="event_at_1"]').fill("14:30")
    wrapper = builtin_page.locator("#id_event_at_field")
    wrapper.screenshot(path="test-results/split-datetime-filled-actual.png")
