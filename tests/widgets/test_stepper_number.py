from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import StepperNumberInput

from .conftest import render_form, render_widget


class StepperNumberForm(FormworkForm):
    """Form fixture for StepperNumberInput integration tests."""

    quantity = forms.IntegerField(
        widget=StepperNumberInput(attrs={"min": "1", "max": "99", "step": "1"}),
        required=True,
    )


@pytest.mark.unit
def test_caller_class_is_appended_once_to_the_component_class():
    """The caller's class follows the component class on the one input."""
    soup = render_widget(StepperNumberInput(attrs={"class": "w-24"}), name="qty", value=3)
    inputs = soup.select("input")
    assert len(inputs) == 1
    assert inputs[0]["class"] == ["input-stepper", "w-24"]


@pytest.mark.unit
def test_step_config_reaches_alpine_as_data_attributes():
    """``min`` and ``integer`` reach the component as data attributes."""
    soup = render_widget(StepperNumberInput(integer=True, min=1), name="qty", value=3)
    root = soup.select_one('[x-data="formworkStepperNumber"]')
    assert root is not None
    assert root["data-min"] == "1"
    assert root["data-integer"] == "true"


@pytest.mark.unit
def test_no_inline_script():
    """The template renders no <script> (R3)."""
    assert render_widget(StepperNumberInput(), name="qty", value=3).select_one("script") is None


@pytest.mark.unit
def test_stepper_number_buttons_have_aria_labels():
    """Both buttons name their direction and stay out of the tab order."""
    soup = render_widget(StepperNumberInput(), name="qty")
    buttons = soup.select("button")
    assert [b["aria-label"] for b in buttons] == ["Decrease", "Increase"]
    assert all(b["tabindex"] == "-1" for b in buttons)
    assert all(b["type"] == "button" for b in buttons)


@pytest.mark.unit
def test_stepper_number_native_bounds_stay_on_the_input():
    """``max`` and ``step`` stay native attributes; the component reads them from the input."""
    soup = render_widget(StepperNumberInput(attrs={"max": "99", "step": "0.1"}), name="qty")
    inp = soup.select_one("input")
    assert inp["max"] == "99"
    assert inp["step"] == "0.1"
    assert inp["x-ref"] == "input"


@pytest.mark.unit
def test_stepper_number_min_kwarg_has_no_native_attribute():
    """``min=`` bounds the buttons only, so the browser accepts a lower typed value."""
    soup = render_widget(StepperNumberInput(min=1), name="qty")
    assert not soup.select_one("input").has_attr("min")


@pytest.mark.unit
def test_stepper_number_unbound_renders_no_value():
    """An unbound value renders no value attribute, not '0'."""
    soup = render_widget(StepperNumberInput(), name="qty")
    assert not soup.select_one("input").has_attr("value")


@pytest.mark.unit
def test_stepper_number_zero_value_not_blanked():
    """An actual 0 value is kept."""
    soup = render_widget(StepperNumberInput(), name="qty", value=0)
    assert soup.select_one("input")["value"] == "0"


@pytest.mark.unit
def test_stepper_number_trailing_buttons():
    """``trailing_buttons`` puts both buttons after the input as DaisyUI buttons."""
    soup = render_widget(StepperNumberInput(trailing_buttons=True), name="qty")
    row = soup.select_one("div.flex.gap-2")
    assert [child.name for child in row.find_all(recursive=False)] == ["input", "button", "button"]
    assert all("btn" in b["class"] for b in row.select("button"))


@pytest.mark.unit
def test_stepper_number_disabled_hides_the_buttons():
    """A disabled input hides the overlay buttons."""
    soup = render_widget(StepperNumberInput(attrs={"disabled": True}), name="qty")
    assert all("invisible" in b["class"] for b in soup.select("button"))


@pytest.mark.unit
def test_stepper_number_disabled_trailing_buttons_are_disabled():
    """With trailing buttons, a disabled input disables both buttons."""
    soup = render_widget(StepperNumberInput(attrs={"disabled": True}, trailing_buttons=True), name="qty")
    assert all(b.has_attr("disabled") for b in soup.select("button"))


@pytest.mark.integration
def test_stepper_number_renders_via_form(renderer):
    """Field renders as a number input named after the form field."""
    soup = render_form(StepperNumberForm(), renderer=renderer)
    inp = soup.find("input", attrs={"name": "quantity"})
    assert inp is not None
    assert inp.get("type") == "number"


@pytest.mark.integration
def test_stepper_number_label_targets_the_input(renderer):
    """The field label points at the number input (R9)."""
    soup = render_form(StepperNumberForm(), renderer=renderer)
    label = soup.find("label", id="id_quantity_label")
    assert label["for"] == "id_quantity"
    assert soup.find(id="id_quantity").name == "input"


@pytest.mark.integration
def test_stepper_number_error_state(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = StepperNumberForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_quantity_error", class_="tooltip-content")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_stepper_number_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(StepperNumberForm(prefix="cfg"), renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-quantity"})
    assert inp["id"] == "id_cfg-quantity"


@pytest.mark.integration
def test_stepper_number_escapes_the_redisplayed_value(renderer):
    """SECURITY: a hostile redisplayed value stays an escaped attribute."""
    payload = "1'); alert(1); ('"
    form = StepperNumberForm(data={"quantity": payload})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    root = soup.select_one('[x-data="formworkStepperNumber"]')
    assert root["x-data"] == "formworkStepperNumber"
    assert soup.find("input", attrs={"name": "quantity"})["value"] == payload


@pytest.mark.e2e
def test_stepper_number_increments_and_clamps(new_widgets_page):
    """Smoke: + steps the value up; - clamps at the configured minimum."""
    from playwright.sync_api import expect

    field = new_widgets_page.locator("#id_quantity_field")
    inp = new_widgets_page.locator("input[name='quantity']")
    expect(inp).to_have_value("1")
    field.locator("button[aria-label='Increase']").click()
    expect(inp).to_have_value("2")
    field.locator("button[aria-label='Decrease']").click()
    expect(inp).to_have_value("1")
    field.locator("button[aria-label='Decrease']").click()
    expect(inp).to_have_value("1")


@pytest.mark.e2e
def test_stepper_number_float_step_rounds(new_widgets_page):
    """Smoke: a 0.1 step rounds to step precision instead of accumulating artifacts."""
    from playwright.sync_api import expect

    field = new_widgets_page.locator("#id_price_field")
    inp = new_widgets_page.locator("input[name='price']")
    expect(inp).to_have_value("0.2")
    field.locator("button[aria-label='Increase']").click()
    expect(inp).to_have_value("0.3")


@pytest.mark.e2e
def test_stepper_number_clamps_a_typed_value_to_max(new_widgets_page):
    """A typed value past ``max`` snaps to ``max`` on change."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("input[name='quantity']")
    inp.fill("500")
    inp.dispatch_event("change")
    expect(inp).to_have_value("99")
