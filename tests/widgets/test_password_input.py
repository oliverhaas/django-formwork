from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import PasswordInput

from .conftest import render_form, render_widget, submit


class PasswordInputForm(FormworkForm):
    """Form fixture for PasswordInput integration tests."""

    password = forms.CharField(widget=PasswordInput, required=True)


@pytest.mark.unit
@pytest.mark.parametrize(("reveal", "buttons"), [(True, 1), (False, 0)])
def test_reveal_flag_decides_whether_the_toggle_renders(reveal, buttons):
    """``reveal=False`` drops the toggle, for confirm-password fields."""
    soup = render_widget(PasswordInput(reveal=reveal), name="password", value="")
    assert len(soup.select("button")) == buttons
    assert soup.select_one('input[type="password"]') is not None


@pytest.mark.unit
def test_password_input_does_not_render_the_value():
    """The submitted password is not sent back by default."""
    soup = render_widget(PasswordInput(), name="password", value="secret")
    assert not soup.select_one("input").has_attr("value")


@pytest.mark.unit
def test_password_input_render_value_renders_the_value():
    """``render_value=True`` sends the value back, as with Django's widget."""
    soup = render_widget(PasswordInput(render_value=True), name="password", value="secret")
    assert soup.select_one("input")["value"] == "secret"


@pytest.mark.unit
def test_password_input_toggle_binds_the_input_type():
    """The component owns the input type; the button flips it and reports its state."""
    soup = render_widget(PasswordInput(), name="password")
    root = soup.select_one('[x-data="formworkPasswordInput"]')
    assert root.select_one("input")[":type"] == "inputType"
    button = root.select_one("button")
    assert button["type"] == "button"
    assert button["@click"] == "toggle()"
    assert button[":aria-pressed"] == "show"
    assert button["aria-label"] == "Show password"


@pytest.mark.unit
def test_password_input_icons_are_hidden_from_screen_readers():
    """The eye icons are decoration; the button's aria-label names it."""
    soup = render_widget(PasswordInput(), name="password")
    icons = soup.select("button i")
    assert [i["class"][1] for i in icons] == ["icon-eye", "icon-eye-off"]
    assert all(i["aria-hidden"] == "true" for i in icons)


@pytest.mark.unit
def test_password_input_floating_wraps_the_toggle_in_the_label():
    """``floating`` puts the reveal control inside the floating label, with the placeholder as text."""
    widget = PasswordInput(attrs={"placeholder": "Password"}, floating=True)
    soup = render_widget(widget, name="password")
    label = soup.select_one("label.floating-label")
    assert label.select_one('[x-data="formworkPasswordInput"] input[type="password"]') is not None
    assert label.select_one("span").get_text() == "Password"


@pytest.mark.integration
def test_password_input_renders_via_form(renderer):
    """Field renders an input named after the form field, targeted by the label."""
    soup = render_form(PasswordInputForm(), renderer=renderer)
    inp = soup.find("input", attrs={"name": "password"})
    assert inp["id"] == "id_password"
    assert soup.find("label", id="id_password_label")["for"] == "id_password"


@pytest.mark.integration
def test_password_input_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = PasswordInputForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", attrs={"name": "password"})["aria-invalid"] == "true"


@pytest.mark.integration
def test_password_input_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = PasswordInputForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_password_error", class_="tooltip-content")
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_password_input_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(PasswordInputForm(prefix="auth"), renderer=renderer)
    inp = soup.find("input", attrs={"name": "auth-password"})
    assert inp["id"] == "id_auth-password"


@pytest.mark.e2e
def test_password_input_toggle_shows_and_hides_password(simple_page):
    """The toggle flips the input between password and text."""
    from playwright.sync_api import expect

    inp = simple_page.locator('input[name="password"]')
    button = simple_page.locator('[x-data="formworkPasswordInput"] button')
    expect(inp).to_have_attribute("type", "password")
    button.click()
    expect(inp).to_have_attribute("type", "text")
    expect(button).to_have_attribute("aria-pressed", "true")
    button.click()
    expect(inp).to_have_attribute("type", "password")


@pytest.mark.e2e
def test_password_input_morph_clears_value(simple_page):
    """The server does not send the password back; morph clears the field."""
    inp = simple_page.locator('input[name="password"]')
    inp.fill("secret123")
    submit(simple_page)
    assert inp.input_value() == ""


@pytest.mark.e2e
def test_password_input_morph_preserves_reveal_state(simple_page):
    """Show/hide toggle state persists through an htmx form morph."""
    from playwright.sync_api import expect

    inp = simple_page.locator('input[name="password"]')
    inp.fill("secret")
    simple_page.locator('[x-data="formworkPasswordInput"] button').click()
    expect(inp).to_have_attribute("type", "text")
    submit(simple_page)
    expect(inp).to_have_attribute("type", "text")


@pytest.mark.screenshot
def test_password_input_screenshot_default(simple_page, assert_screenshot):
    """Visual snapshot: PasswordInput in default (hidden/password) state."""
    assert_screenshot(simple_page.locator("#id_password_field"), "password-reveal-default.png")


@pytest.mark.screenshot
def test_password_input_screenshot_revealed(simple_page, assert_screenshot):
    """Visual snapshot: PasswordInput in revealed (text) state."""
    simple_page.locator('[x-data="formworkPasswordInput"] button').click()
    simple_page.wait_for_timeout(100)
    assert_screenshot(simple_page.locator("#id_password_field"), "password-reveal-revealed.png")
