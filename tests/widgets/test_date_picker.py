"""Tests for the DatePicker widget.

Levels:
    1. unit        — widget object: instantiation, input_type, default format
    2. unit        — widget rendering: HTML structure, placeholder, value
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5–8. e2e / screenshot — SKIPPED (no e2e page for DatePicker yet)
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import DatePicker

from .conftest import assert_html_equivalent, render_form, render_widget


class DatePickerForm(FormworkForm):
    """Form fixture for DatePicker integration tests."""

    due_date = forms.DateField(widget=DatePicker, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


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
def test_date_picker_default_format():
    """DatePicker defaults to '%Y-%m-%d' format."""
    widget = DatePicker()
    assert widget.format == "%Y-%m-%d"


@pytest.mark.unit
def test_date_picker_input_type():
    """DatePicker uses input_type='text', not 'date'."""
    widget = DatePicker()
    assert widget.input_type == "text"


@pytest.mark.unit
def test_date_picker_get_context():
    """get_context() returns a dict with widget sub-dict."""
    widget = DatePicker()
    ctx = widget.get_context("due_date", None, {"id": "id_due_date"})
    assert "widget" in ctx
    assert ctx["widget"]["name"] == "due_date"
    assert ctx["widget"]["attrs"]["id"] == "id_due_date"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_date_picker_renders_input():
    """DatePicker renders an <input> element."""
    soup = render_widget(DatePicker())
    assert soup.find("input") is not None


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
    import datetime

    widget = DatePicker()
    soup = render_widget(widget, value=datetime.date(2024, 6, 15), attrs={"id": "id_due_date"})
    inp = soup.find("input")
    assert inp is not None
    assert inp.get("value") == "2024-06-15"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_date_picker_renders_via_form(renderer):
    """DatePicker renders correctly when used inside a FormworkForm."""
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
    """SECURITY: the redisplayed raw value inside the Alpine x-data string is JS-escaped."""
    # Regression: an unescaped quote broke out of the value: '...' string
    # literal and executed on validation-error redisplay (Alpine evaluates the
    # entity-decoded attribute, so HTML autoescaping alone does not defend).
    payload = "'}); alert(1); ({'"
    form = DatePickerForm(data={"due_date": payload})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", class_="date-picker")
    x_data = wrapper["x-data"]
    assert payload not in x_data
    assert "\\u0027" in x_data


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_date_picker_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """DatePicker produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(DatePickerForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(DatePickerForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────
#
# No e2e page for DatePicker yet — tests would live here once a page
# fixture is added.  Tracked as a gap in e2e coverage.


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.
