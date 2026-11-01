from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ToggleInput

from .conftest import render_form, render_widget, submit


class ToggleForm(FormworkForm):
    """Form fixture for ToggleInput integration tests."""

    enabled = forms.BooleanField(widget=ToggleInput, required=True, help_text="Send me updates.")


@pytest.mark.unit
def test_toggle_input_merges_the_toggle_class_with_user_classes():
    """The ``toggle`` class leads the caller's classes on the rendered checkbox."""
    soup = render_widget(ToggleInput(attrs={"class": "my-toggle"}))
    inp = soup.find("input")
    assert inp["type"] == "checkbox"
    assert inp["class"] == ["toggle", "my-toggle"]


@pytest.mark.unit
@pytest.mark.parametrize(("query", "expected"), [("enabled=on", True), ("", False)])
def test_toggle_input_value_from_datadict(query, expected):
    """A checked switch submits True; an absent one reads as False."""
    assert ToggleInput().value_from_datadict(QueryDict(query), {}, "enabled") is expected


@pytest.mark.unit
@pytest.mark.parametrize(("value", "checked"), [(True, True), (False, False), (None, False)])
def test_toggle_input_renders_checked_state(value, checked):
    """The value decides the checked attribute."""
    assert render_widget(ToggleInput(), value=value).find("input").has_attr("checked") is checked


@pytest.mark.integration
def test_toggle_input_label_sits_beside_the_switch(renderer):
    """The field label wraps the switch and targets it, without a legend above."""
    soup = render_form(ToggleForm(), renderer=renderer)
    fieldset = soup.find("fieldset", id="id_enabled_field")
    label = fieldset.find("label", id="id_enabled_label")
    assert label["for"] == "id_enabled"
    assert label.find("input", attrs={"name": "enabled"}) is not None
    assert "Enabled" in label.get_text()
    assert fieldset.find("legend") is None


@pytest.mark.integration
def test_toggle_input_has_no_optional_badge(renderer):
    """An optional switch carries no "optional" badge, like a single checkbox."""

    class OptionalToggleForm(FormworkForm):
        enabled = forms.BooleanField(widget=ToggleInput, required=False)

    soup = render_form(OptionalToggleForm(), renderer=renderer)
    assert soup.find(class_="badge") is None


@pytest.mark.integration
def test_toggle_input_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = ToggleForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", attrs={"name": "enabled"})["aria-invalid"] == "true"


@pytest.mark.integration
def test_toggle_input_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = ToggleForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_enabled_error", class_="tooltip-content")
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
@pytest.mark.parametrize("error_display", ["auto", "inline"])
def test_toggle_input_error_state_shows_inline_error_with_help(renderer, error_display):
    """With help text, the error and the help share the disclosure row under the switch."""
    form = ToggleForm(data={}, error_display=error_display)
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    disclosure = soup.find(id="id_enabled_disclosure")
    assert "required" in disclosure.find(id="id_enabled_error").text.lower()
    assert disclosure.find(id="id_enabled_helptext").get_text(strip=True) == "Send me updates."


@pytest.mark.integration
def test_toggle_input_describedby_targets_exist(renderer):
    """Every id in the switch's aria-describedby is rendered."""
    form = ToggleForm(data={}, error_display="inline")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    ids = soup.find("input", attrs={"name": "enabled"})["aria-describedby"].split()
    assert ids
    assert all(soup.find(id=i) is not None for i in ids)


@pytest.mark.integration
def test_toggle_input_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(ToggleForm(prefix="cfg"), renderer=renderer)
    assert soup.find("input", attrs={"name": "cfg-enabled"})["id"] == "id_cfg-enabled"


@pytest.mark.e2e
def test_toggle_input_label_click_flips_the_switch(toggle_page):
    """Clicking the label text toggles the switch on and off."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    label = toggle_page.locator("#id_toggle_label span")
    expect(toggle).not_to_be_checked()
    label.click()
    expect(toggle).to_be_checked()
    toggle.click()
    expect(toggle).not_to_be_checked()


@pytest.mark.e2e
def test_toggle_input_morph_preserves_checked(toggle_page):
    """Checked state survives an htmx form morph."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    toggle.check()
    submit(toggle_page)
    expect(toggle_page.locator('input[name="toggle"]')).to_be_checked()


@pytest.mark.e2e
def test_toggle_input_morph_preserves_unchecked(toggle_page):
    """Unchecked state survives an htmx form morph."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    expect(toggle).not_to_be_checked()
    submit(toggle_page)
    expect(toggle_page.locator('input[name="toggle"]')).not_to_be_checked()


@pytest.mark.screenshot
def test_toggle_input_screenshot_default(toggle_page, assert_screenshot):
    """Visual snapshot: ToggleInput in default (unchecked) state."""
    assert_screenshot(toggle_page.locator("#id_toggle_field"), "toggle-default.png")


@pytest.mark.screenshot
def test_toggle_input_screenshot_checked(toggle_page, assert_screenshot):
    """Visual snapshot: ToggleInput in checked state."""
    toggle_page.locator('input[name="toggle"]').check()
    assert_screenshot(toggle_page.locator("#id_toggle_field"), "toggle-checked.png")
