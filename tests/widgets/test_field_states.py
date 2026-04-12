"""Tests for cross-cutting field states: disabled, readonly, required indicator, color input.

These test formwork's handling of standard Django field attributes that
apply across all widget types, not specific to any single widget.

Levels:
    1. unit        — widget rendering: disabled/readonly attrs in HTML
    2. integration — form integration: fieldset structure, required indicator
    3. e2e         — user interaction: disabled/readonly behavior, asterisk visibility
    4. screenshot  — visual states: disabled, readonly
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm

from .conftest import render_form, render_widget


class DisabledFieldForm(FormworkForm):
    """Form fixture with a disabled text input."""

    name = forms.CharField(
        widget=forms.TextInput(attrs={"disabled": True}),
        required=False,
        initial="Cannot edit this",
    )


class ReadonlyFieldForm(FormworkForm):
    """Form fixture with a readonly text input."""

    name = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": True}),
        required=False,
        initial="Read-only value",
    )


class RequiredFieldForm(FormworkForm):
    """Form fixture with required and optional fields."""

    required_name = forms.CharField(required=True)
    optional_name = forms.CharField(required=False)


class ColorInputForm(FormworkForm):
    """Form fixture with a color input."""

    color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        required=False,
    )


# ─── Level 1: Widget rendering (disabled / readonly) ────────────────────


@pytest.mark.unit
def test_disabled_field_renders_disabled_attr():
    """TextInput with disabled=True renders a disabled input."""
    widget = forms.TextInput(attrs={"disabled": True})
    soup = render_widget(widget, name="field", value="test")
    inp = soup.find("input")
    assert inp.has_attr("disabled")


@pytest.mark.unit
def test_disabled_field_renders_value():
    """Disabled input still renders its value."""
    widget = forms.TextInput(attrs={"disabled": True})
    soup = render_widget(widget, name="field", value="Cannot edit this")
    inp = soup.find("input")
    assert inp["value"] == "Cannot edit this"


@pytest.mark.unit
def test_readonly_field_renders_readonly_attr():
    """TextInput with readonly=True renders a readonly input."""
    widget = forms.TextInput(attrs={"readonly": True})
    soup = render_widget(widget, name="field", value="test")
    inp = soup.find("input")
    assert inp.has_attr("readonly")


@pytest.mark.unit
def test_readonly_field_renders_value():
    """Readonly input renders its value."""
    widget = forms.TextInput(attrs={"readonly": True})
    soup = render_widget(widget, name="field", value="Read-only value")
    inp = soup.find("input")
    assert inp["value"] == "Read-only value"


@pytest.mark.unit
def test_color_input_renders_type():
    """TextInput with type='color' renders an input[type=color]."""
    widget = forms.TextInput(attrs={"type": "color"})
    soup = render_widget(widget, name="color")
    inp = soup.find("input")
    assert inp["type"] == "color"


# ─── Level 2: Form integration (required indicator) ─────────────────────


@pytest.mark.integration
def test_required_field_has_asterisk(renderer):
    """Required field renders a red asterisk in its fieldset legend/label."""
    form = RequiredFieldForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_required_name_field")
    assert fieldset is not None
    asterisk = fieldset.find("span", class_="text-error")
    assert asterisk is not None
    assert asterisk.text == "*"


@pytest.mark.integration
def test_optional_field_no_asterisk(renderer):
    """Optional field does not render an asterisk."""
    form = RequiredFieldForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_optional_name_field")
    assert fieldset is not None
    asterisk = fieldset.find("span", class_="text-error")
    assert asterisk is None


@pytest.mark.integration
def test_disabled_field_renders_via_form(renderer):
    """Disabled field renders correctly inside a FormworkForm."""
    form = DisabledFieldForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "name"})
    assert inp is not None
    assert inp.has_attr("disabled")


@pytest.mark.integration
def test_disabled_field_wraps_in_fieldset(renderer):
    """Disabled field is wrapped in a fieldset with id."""
    form = DisabledFieldForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_name_field")
    assert fieldset is not None


@pytest.mark.integration
def test_readonly_field_renders_via_form(renderer):
    """Readonly field renders correctly inside a FormworkForm."""
    form = ReadonlyFieldForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "name"})
    assert inp is not None
    assert inp.has_attr("readonly")


@pytest.mark.integration
def test_color_input_renders_via_form(renderer):
    """Color input renders correctly inside a FormworkForm."""
    form = ColorInputForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "color"})
    assert inp is not None
    assert inp["type"] == "color"


@pytest.mark.integration
def test_color_input_wraps_in_fieldset(renderer):
    """Color input is wrapped in a fieldset with id."""
    form = ColorInputForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_color_field")
    assert fieldset is not None


# ─── Level 3: E2e interaction ───────────────────────────────────────────


@pytest.mark.e2e
def test_disabled_field_renders_on_page(builtin_page):
    """Disabled input is present and disabled on the /builtin/ page."""
    from playwright.sync_api import expect

    inp = builtin_page.locator('input[name="disabled_text"]')
    expect(inp).to_have_count(1)
    expect(inp).to_be_disabled()


@pytest.mark.e2e
def test_disabled_field_has_initial_value(builtin_page):
    """Disabled input shows its initial value."""
    from playwright.sync_api import expect

    inp = builtin_page.locator('input[name="disabled_text"]')
    expect(inp).to_have_value("Cannot edit this")


@pytest.mark.e2e
def test_disabled_field_wrapped_in_fieldset(builtin_page):
    """Disabled field is wrapped in a fieldset."""
    from playwright.sync_api import expect

    fieldset = builtin_page.locator("#id_disabled_text_field")
    expect(fieldset).to_be_visible()


@pytest.mark.e2e
def test_readonly_field_renders_on_page(builtin_page):
    """Readonly input is present with readonly attribute on the /builtin/ page."""
    inp = builtin_page.locator('input[name="readonly_text"]')
    assert inp.count() == 1
    assert inp.get_attribute("readonly") is not None


@pytest.mark.e2e
def test_readonly_field_has_initial_value(builtin_page):
    """Readonly input shows its initial value."""
    from playwright.sync_api import expect

    inp = builtin_page.locator('input[name="readonly_text"]')
    expect(inp).to_have_value("Read-only value")


@pytest.mark.e2e
def test_readonly_field_morph_preserves_value(builtin_page):
    """Readonly field value survives an htmx form morph."""
    from playwright.sync_api import expect

    from tests.e2e.conftest import submit

    inp = builtin_page.locator('input[name="readonly_text"]')
    submit(builtin_page)
    expect(inp).to_have_value("Read-only value")


@pytest.mark.e2e
def test_required_field_has_asterisk_on_page(basic_page):
    """Required field (name) shows an asterisk in its fieldset on the /basic/ page."""
    from playwright.sync_api import expect

    fieldset = basic_page.locator("#id_name_field")
    asterisk = fieldset.locator("span.text-error")
    expect(asterisk).to_have_count(1)
    assert asterisk.inner_text() == "*"


@pytest.mark.e2e
def test_optional_field_no_asterisk_on_page(builtin_page):
    """Optional field (event_at) has no asterisk on the /builtin/ page."""
    from playwright.sync_api import expect

    fieldset = builtin_page.locator("#id_event_at_field")
    asterisk = fieldset.locator("span.text-error")
    expect(asterisk).to_have_count(0)


@pytest.mark.e2e
def test_color_input_renders_on_page(builtin_page):
    """Color input is visible on the /builtin/ page."""
    from playwright.sync_api import expect

    inp = builtin_page.locator('input[name="color"]')
    expect(inp).to_be_visible()
    assert inp.get_attribute("type") == "color"


@pytest.mark.e2e
def test_color_input_morph_preserves_value(builtin_page):
    """Color input value survives an htmx form morph."""
    from playwright.sync_api import expect

    from tests.e2e.conftest import submit

    builtin_page.evaluate("""
        const inp = document.querySelector('input[name="color"]');
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        setter.call(inp, '#ff5500');
        inp.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    submit(builtin_page)
    expect(builtin_page.locator('input[name="color"]')).to_have_value("#ff5500")


# ─── Level 4: Screenshot (visual regression) ────────────────────────────


@pytest.mark.screenshot
def test_disabled_field_screenshot(builtin_page, assert_screenshot):
    """Visual snapshot: disabled text input."""
    wrapper = builtin_page.locator("#id_disabled_text_field")
    assert_screenshot(wrapper, "disabled-field.png")


@pytest.mark.screenshot
def test_readonly_field_screenshot(builtin_page, assert_screenshot):
    """Visual snapshot: readonly text input."""
    wrapper = builtin_page.locator("#id_readonly_text_field")
    assert_screenshot(wrapper, "readonly-field.png")
