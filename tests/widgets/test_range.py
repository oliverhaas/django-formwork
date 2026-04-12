"""Tests for the Range widget (range slider).

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_range.py                 # everything
    uv run pytest tests/widgets/ -m unit                       # all widgets, unit only
    uv run pytest tests/widgets/test_range.py -m "not e2e"    # skip browser tests

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, type="range", min/max/step attrs
    3. integration — form integration: field template, error state, morph IDs
    5. e2e         — user interaction: set value
    6. e2e         — error flow: SKIPPED (no required Range field on /simple/)
    7. e2e         — morph resilience: value preserved across htmx morphs
    8. screenshot  — visual states: default, set-value
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Range

from .conftest import assert_html_equivalent, render_form, render_widget


class RangeForm(FormworkForm):
    """Form fixture for Range integration tests."""

    level = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "10", "step": "1"}),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_range_instantiation_default():
    """Range widget can be instantiated with no arguments."""
    widget = Range()
    assert widget.input_type == "range"


@pytest.mark.unit
def test_range_instantiation_with_min_max_attrs():
    """Range widget stores min/max attrs when provided."""
    widget = Range(attrs={"min": "0", "max": "100"})
    assert widget.attrs["min"] == "0"
    assert widget.attrs["max"] == "100"


@pytest.mark.unit
def test_range_instantiation_with_step_attr():
    """Range widget stores step attr when provided."""
    widget = Range(attrs={"step": "10"})
    assert widget.attrs["step"] == "10"


@pytest.mark.unit
def test_range_get_context_returns_range_type():
    """get_context() produces a context dict where the widget renders as a range input."""
    widget = Range()
    ctx = widget.get_context("level", 5, {"id": "id_level"})
    assert ctx["widget"]["type"] == "range"
    assert ctx["widget"]["name"] == "level"
    assert ctx["widget"]["attrs"]["id"] == "id_level"


@pytest.mark.unit
def test_range_value_from_datadict_returns_string():
    """Submitted range input returns a string value."""
    widget = Range()
    data = QueryDict("level=70")
    result = widget.value_from_datadict(data, {}, "level")
    assert result == "70"


@pytest.mark.unit
def test_range_value_from_datadict_missing_key():
    """Missing range input returns None."""
    widget = Range()
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "level")
    assert result is None


@pytest.mark.unit
def test_range_get_context_with_value_none():
    """Passing value=None is tolerated — widget renders without a value attr."""
    widget = Range()
    ctx = widget.get_context("level", None, {"id": "id_level"})
    assert ctx["widget"]["value"] is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_range_renders_non_empty_html():
    """widget.render() produces non-empty output."""
    soup = render_widget(Range())
    assert soup.find("input") is not None


@pytest.mark.unit
def test_range_renders_range_input_type():
    """Rendered HTML contains an <input type='range'>."""
    soup = render_widget(Range())
    inp = soup.find("input")
    assert inp["type"] == "range"


@pytest.mark.unit
def test_range_renders_min_max_attrs():
    """Provided min/max attrs appear on the rendered input element."""
    widget = Range(attrs={"min": "0", "max": "100"})
    soup = render_widget(widget)
    inp = soup.find("input")
    assert inp["min"] == "0"
    assert inp["max"] == "100"


@pytest.mark.unit
def test_range_renders_step_attr():
    """Provided step attr appears on the rendered input element."""
    widget = Range(attrs={"step": "10"})
    soup = render_widget(widget)
    inp = soup.find("input")
    assert inp["step"] == "10"


@pytest.mark.unit
def test_range_renders_with_value():
    """Passing a value produces an input with that value attribute."""
    soup = render_widget(Range(), value=50)
    inp = soup.find("input")
    assert inp.get("value") == "50"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_range_renders_via_form(renderer):
    """Range renders correctly when used inside a FormworkForm."""
    form = RangeForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "level"})
    assert inp is not None
    assert inp["type"] == "range"


@pytest.mark.integration
def test_range_form_wraps_in_fieldset(renderer):
    """Field template wraps the Range in a fieldset with a stable id."""
    form = RangeForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_level_field")
    assert fieldset is not None


@pytest.mark.integration
def test_range_form_attrs_propagate(renderer):
    """min/max/step attrs on the widget appear in the rendered form output."""
    form = RangeForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "level"})
    assert inp["min"] == "0"
    assert inp["max"] == "10"
    assert inp["step"] == "1"


@pytest.mark.integration
def test_range_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = RangeForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "level"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_range_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = RangeForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_level_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_range_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = RangeForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-level"})
    assert inp is not None
    assert inp["id"] == "id_cfg-level"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_range_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Range produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(RangeForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(RangeForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_range_renders_on_page(simple_page):
    """Range input is visible on the /simple/ page."""
    from playwright.sync_api import expect

    rng = simple_page.locator('input[name="volume"]')
    expect(rng).to_be_visible()


@pytest.mark.e2e
def test_range_has_correct_attrs(simple_page):
    """Range input has expected type and min/max/step attributes."""
    rng = simple_page.locator('input[name="volume"]')
    assert rng.get_attribute("type") == "range"
    assert rng.get_attribute("min") == "0"
    assert rng.get_attribute("max") == "100"
    assert rng.get_attribute("step") == "10"


@pytest.mark.e2e
def test_range_user_can_set_value(simple_page):
    """User can set the range value via JavaScript dispatch."""
    simple_page.evaluate("""
        const r = document.querySelector('input[name="volume"]');
        r.value = '70';
        r.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    assert simple_page.locator('input[name="volume"]').input_value() == "70"


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# The /simple/ page does not have a required Range field — volume is
# always valid (any integer passes).  Dedicated error-flow tests would
# need a separate test page with a required Range with restricted values.
# Deferred until that dedicated test page exists.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_range_morph_preserves_value(simple_page):
    """Set range value survives an htmx form morph."""
    from tests.e2e.conftest import submit

    simple_page.evaluate("""
        const r = document.querySelector('input[name="volume"]');
        r.value = '70';
        r.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    submit(simple_page)
    assert simple_page.locator('input[name="volume"]').input_value() == "70"


@pytest.mark.e2e
def test_range_morph_preserves_default_value(simple_page):
    """Default range value survives an htmx form morph without any change."""
    from tests.e2e.conftest import submit

    initial = simple_page.locator('input[name="volume"]').input_value()
    submit(simple_page)
    assert simple_page.locator('input[name="volume"]').input_value() == initial


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.  See issue #26 for the plan.


@pytest.mark.screenshot
def test_range_screenshot_default(simple_page, assert_screenshot):
    """Visual snapshot: Range in default state."""
    wrapper = simple_page.locator("#id_volume_field")
    assert_screenshot(wrapper, "range-default.png")


@pytest.mark.screenshot
def test_range_screenshot_set_value(simple_page, assert_screenshot):
    """Visual snapshot: Range with value set to 70."""
    simple_page.evaluate("""
        const r = document.querySelector('input[name="volume"]');
        r.value = '70';
        r.dispatchEvent(new Event('input', {bubbles: true}));
    """)
    wrapper = simple_page.locator("#id_volume_field")
    assert_screenshot(wrapper, "range-set-value.png")
