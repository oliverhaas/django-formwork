"""Tests for the InputNumber widget.

Levels:
    1. unit (widget object): instantiation, get_context, value_from_datadict
    2. unit (widget rendering): HTML structure, attributes
    3. integration (form integration): field template, error state, prefix
    4. integration (Jinja2/DTL parity): identical HTML across engines
    5. e2e (smoke): +/- buttons step the value, incl. float-step rounding
    6 to 8. e2e / screenshot: SKIPPED (gaps; smoke coverage only)
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import InputNumber

from .conftest import assert_html_equivalent, render_form, render_widget


class InputNumberForm(FormworkForm):
    """Form fixture for InputNumber integration tests."""

    quantity = forms.IntegerField(
        widget=InputNumber(attrs={"min": "1", "max": "99", "step": "1"}),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_input_number_instantiation():
    """InputNumber can be instantiated and exposes the expected template_name."""
    widget = InputNumber()
    assert widget.template_name == "formwork/widgets/input_number.html"


@pytest.mark.unit
def test_input_number_inherits_number_input():
    """InputNumber is a subclass of Django's NumberInput."""
    widget = InputNumber()
    assert isinstance(widget, forms.NumberInput)


@pytest.mark.unit
def test_input_number_get_context():
    """get_context() returns the standard widget context with name and attrs."""
    widget = InputNumber(attrs={"min": "0", "max": "10"})
    ctx = widget.get_context("quantity", 5, {"id": "id_quantity"})
    assert ctx["widget"]["name"] == "quantity"
    assert ctx["widget"]["value"] == "5"
    assert ctx["widget"]["attrs"]["id"] == "id_quantity"


@pytest.mark.unit
def test_input_number_value_from_datadict():
    """Submitted number value is returned from a QueryDict."""
    widget = InputNumber()
    data = QueryDict("quantity=42")
    result = widget.value_from_datadict(data, {}, "quantity")
    assert result == "42"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_input_number_renders_input():
    """InputNumber renders an <input type='number'>."""
    soup = render_widget(InputNumber(), name="quantity", attrs={"id": "id_quantity"})
    inp = soup.find("input", attrs={"type": "number"})
    assert inp is not None


@pytest.mark.unit
def test_input_number_renders_with_value():
    """Rendered input reflects the provided value via the data-value config attribute."""
    # The template uses :value="val" (Alpine binding); the formworkInputNumber
    # component reads its initial state from data-* attributes at init.
    widget = InputNumber(attrs={"min": "1", "max": "99"})
    soup = render_widget(widget, name="quantity", value=7, attrs={"id": "id_quantity"})
    container = soup.find(attrs={"class": lambda c: c and "input-number" in c})
    assert container is not None
    assert container["x-data"] == "formworkInputNumber"
    assert container["data-value"] == "7"
    assert container["data-min"] == "1"
    assert container["data-max"] == "99"


@pytest.mark.unit
def test_input_number_unbound_renders_empty_value():
    """An unbound/None value renders as an empty string, not '0'."""
    soup = render_widget(InputNumber(), name="quantity", attrs={"id": "id_quantity"})
    container = soup.find(attrs={"class": lambda c: c and "input-number" in c})
    assert container["data-value"] == ""


@pytest.mark.unit
def test_input_number_zero_value_not_blanked():
    """An actual 0 value is kept; only None/empty renders empty."""
    soup = render_widget(InputNumber(), name="quantity", value=0, attrs={"id": "id_quantity"})
    container = soup.find(attrs={"class": lambda c: c and "input-number" in c})
    assert container["data-value"] == "0"


@pytest.mark.unit
def test_input_number_steps_round_to_step_precision():
    """A float step is passed through data-step so _round() knows its precision."""
    # Regression: 0.2 + 0.1 stepped to 0.30000000000000004 in the stepper.
    # The rounding itself lives in formworkInputNumber (input_number.js) and
    # is asserted end-to-end in test_input_number_float_step_rounds below.
    widget = InputNumber(attrs={"step": "0.1"})
    soup = render_widget(widget, name="quantity", attrs={"id": "id_quantity"})
    container = soup.find(attrs={"class": lambda c: c and "input-number" in c})
    assert container["data-step"] == "0.1"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_input_number_renders_via_form(renderer):
    """InputNumber renders correctly when used inside a FormworkForm."""
    form = InputNumberForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "quantity"})
    assert inp is not None
    assert inp.get("type") == "number"


@pytest.mark.integration
def test_input_number_form_wraps_in_fieldset(renderer):
    """Field template wraps InputNumber in a fieldset with a stable id."""
    form = InputNumberForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_quantity_field")
    assert fieldset is not None


@pytest.mark.integration
def test_input_number_error_state(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = InputNumberForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_quantity_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_input_number_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    form = InputNumberForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-quantity"})
    assert inp is not None
    assert inp["id"] == "id_cfg-quantity"


@pytest.mark.integration
def test_input_number_escapes_value_in_x_data(renderer):
    """SECURITY: the redisplayed raw value never lands in an executable context."""
    # Regression: val: interpolated the raw submitted string into the inline
    # Alpine object literal, so a non-numeric payload executed on
    # validation-error redisplay.  The value now rides in an autoescaped
    # data-value attribute read via dataset (never evaluated as JS), and
    # x-data holds only the fixed component name.
    payload = "1'); alert(1); ('"
    form = InputNumberForm(data={"quantity": payload})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", class_="input-number")
    assert wrapper["x-data"] == "formworkInputNumber"
    # BeautifulSoup entity-decodes: an exact round-trip proves lossless escaping.
    assert wrapper["data-value"] == payload


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_input_number_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """InputNumber produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(InputNumberForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(InputNumberForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_input_number_increments_and_clamps(new_widgets_page):
    """Smoke: + steps the value up; - clamps at the configured minimum."""
    from playwright.sync_api import expect

    stepper = new_widgets_page.locator("#id_quantity_stepper")
    inp = new_widgets_page.locator("input[name='quantity']")
    expect(inp).to_have_value("1")
    stepper.locator("button[aria-label='Increase']").click()
    expect(inp).to_have_value("2")
    stepper.locator("button[aria-label='Decrease']").click()
    expect(inp).to_have_value("1")
    stepper.locator("button[aria-label='Decrease']").click()
    expect(inp).to_have_value("1")


@pytest.mark.e2e
def test_input_number_float_step_rounds(new_widgets_page):
    """Smoke: a 0.1 step rounds to step precision instead of accumulating artifacts."""
    # Regression: 0.2 + 0.1 stepped to 0.30000000000000004 in the stepper.
    from playwright.sync_api import expect

    stepper = new_widgets_page.locator("#id_price_stepper")
    inp = new_widgets_page.locator("input[name='price']")
    expect(inp).to_have_value("0.2")
    stepper.locator("button[aria-label='Increase']").click()
    expect(inp).to_have_value("0.3")


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Requires a dedicated error-flow page.  Left as a gap.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# Key case to cover: stepper value preserved across htmx morph.
# Left as a gap.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Planned screenshots: input-number-default.png,
# input-number-incremented.png.  Left as a gap.
