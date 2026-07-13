"""Canonical test patterns for a formwork widget (Toggle as exemplar).

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_toggle.py                 # everything
    uv run pytest tests/widgets/ -m unit                       # all widgets, unit only
    uv run pytest tests/widgets/test_toggle.py -m "not e2e"    # skip browser tests

Levels:
    1. unit (widget object: instantiation, get_context, value_from_datadict)
    2. unit (widget rendering: HTML structure, classes, attributes)
    3. integration (form integration: field template, error state, morph IDs)
    5. e2e (user interaction: fill, click, submit)
    6. e2e (error flow: validation errors appear and clear)
    7. e2e (morph resilience: state preserved across htmx morphs)
    8. screenshot (visual states: default, checked, error)
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Toggle

from .conftest import render_form, render_widget, submit


class ToggleForm(FormworkForm):
    """Form fixture for Toggle integration tests."""

    enabled = forms.BooleanField(widget=Toggle, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_toggle_instantiation_has_default_class():
    """Toggle widget adds 'toggle' to its default attrs."""
    widget = Toggle()
    assert "toggle" in widget.attrs.get("class", "")


@pytest.mark.unit
def test_toggle_preserves_user_attrs():
    """User-supplied attrs (including class) are merged with defaults."""
    widget = Toggle(attrs={"class": "my-toggle"})
    cls = widget.attrs.get("class", "")
    assert "toggle" in cls
    assert "my-toggle" in cls


@pytest.mark.unit
def test_toggle_get_context_returns_checkbox_type():
    """get_context() produces a context dict where the widget renders as a checkbox."""
    widget = Toggle()
    ctx = widget.get_context("enabled", True, {"id": "id_enabled"})  # noqa: FBT003
    assert ctx["widget"]["type"] == "checkbox"
    assert ctx["widget"]["name"] == "enabled"
    assert ctx["widget"]["attrs"]["id"] == "id_enabled"


@pytest.mark.unit
def test_toggle_value_from_datadict_checked():
    """Submitted checked checkbox returns True."""
    widget = Toggle()
    data = QueryDict("enabled=on")
    assert widget.value_from_datadict(data, {}, "enabled") is True


@pytest.mark.unit
def test_toggle_value_from_datadict_unchecked():
    """Unchecked checkbox returns False (name missing from QueryDict)."""
    widget = Toggle()
    data = QueryDict("")
    assert widget.value_from_datadict(data, {}, "enabled") is False


@pytest.mark.unit
def test_toggle_get_context_with_value_none():
    """Passing value=None is tolerated; widget renders unchecked."""
    widget = Toggle()
    ctx = widget.get_context("enabled", None, {"id": "id_enabled"})
    assert ctx["widget"]["value"] is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_toggle_renders_non_empty_html():
    """widget.render() produces non-empty output."""
    soup = render_widget(Toggle())
    assert soup.find("input") is not None


@pytest.mark.unit
def test_toggle_renders_checkbox_input():
    """Rendered HTML contains an <input type='checkbox'>."""
    soup = render_widget(Toggle())
    inp = soup.find("input")
    assert inp["type"] == "checkbox"


@pytest.mark.unit
def test_toggle_renders_toggle_class_in_output():
    """The 'toggle' class appears on the rendered input element."""
    soup = render_widget(Toggle())
    inp = soup.find("input")
    assert "toggle" in inp.get("class", [])


@pytest.mark.unit
def test_toggle_renders_checked_state():
    """Passing value=True produces a checked input."""
    soup = render_widget(Toggle(), value=True)
    inp = soup.find("input")
    assert inp.has_attr("checked")


@pytest.mark.unit
def test_toggle_renders_unchecked_state():
    """Passing value=False produces an input without the checked attribute."""
    soup = render_widget(Toggle(), value=False)
    inp = soup.find("input")
    assert not inp.has_attr("checked")


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_toggle_renders_via_form(renderer):
    """Field renders as a checkbox input named after the form field."""
    form = ToggleForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "enabled"})
    assert inp is not None
    assert inp["type"] == "checkbox"


@pytest.mark.integration
def test_toggle_form_wraps_in_fieldset(renderer):
    """Field template wraps the Toggle in a fieldset with a stable id."""
    form = ToggleForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_enabled_field")
    assert fieldset is not None


@pytest.mark.integration
def test_toggle_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = ToggleForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "enabled"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_toggle_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = ToggleForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_enabled_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_toggle_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = ToggleForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-enabled"})
    assert inp is not None
    assert inp["id"] == "id_cfg-enabled"


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_toggle_renders_on_page(toggle_page):
    """Toggle input is visible on the /simple/ page."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    expect(toggle).to_be_visible()


@pytest.mark.e2e
def test_toggle_user_can_click_on_off(toggle_page):
    """User can toggle the switch on and off."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    expect(toggle).not_to_be_checked()
    toggle.click()
    expect(toggle).to_be_checked()
    toggle.click()
    expect(toggle).not_to_be_checked()


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Needs a page with a required=True Toggle; /simple/ has none.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_toggle_morph_preserves_checked(toggle_page):
    """Checked state survives an htmx form morph."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    toggle.check()
    expect(toggle).to_be_checked()
    submit(toggle_page)
    expect(toggle_page.locator('input[name="toggle"]')).to_be_checked()


@pytest.mark.e2e
def test_toggle_morph_preserves_unchecked(toggle_page):
    """Unchecked state survives an htmx form morph."""
    from playwright.sync_api import expect

    toggle = toggle_page.locator('input[name="toggle"]')
    expect(toggle).not_to_be_checked()
    submit(toggle_page)
    expect(toggle_page.locator('input[name="toggle"]')).not_to_be_checked()


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_toggle_screenshot_default(toggle_page, assert_screenshot):
    """Visual snapshot: Toggle in default (unchecked) state."""
    wrapper = toggle_page.locator("#id_toggle_field")
    assert_screenshot(wrapper, "toggle-default.png")


@pytest.mark.screenshot
def test_toggle_screenshot_checked(toggle_page, assert_screenshot):
    """Visual snapshot: Toggle in checked state."""
    toggle_page.locator('input[name="toggle"]').check()
    wrapper = toggle_page.locator("#id_toggle_field")
    assert_screenshot(wrapper, "toggle-checked.png")
