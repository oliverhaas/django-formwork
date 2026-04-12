"""Tests for the PasswordReveal widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_password_reveal.py                 # everything
    uv run pytest tests/widgets/ -m unit                                # all widgets, unit only
    uv run pytest tests/widgets/test_password_reveal.py -m "not e2e"   # skip browser tests

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, classes, attributes
    3. integration — form integration: field template, error state, morph IDs
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: toggle password visibility
    6. e2e         — error flow: SKIPPED (see comment)
    7. e2e         — morph resilience: show/hide state preserved across morphs
    8. screenshot  — visual states: default (hidden), revealed
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import PasswordReveal

from .conftest import assert_html_equivalent, render_form, render_widget


class PasswordRevealForm(FormworkForm):
    """Form fixture for PasswordReveal integration tests."""

    password = forms.CharField(widget=PasswordReveal, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_password_reveal_instantiation():
    """PasswordReveal widget can be instantiated without arguments."""
    widget = PasswordReveal()
    assert widget is not None


@pytest.mark.unit
def test_password_reveal_is_password_input():
    """PasswordReveal extends forms.PasswordInput."""
    widget = PasswordReveal()
    assert isinstance(widget, forms.PasswordInput)


@pytest.mark.unit
def test_password_reveal_render_value_false():
    """PasswordReveal does not render the value (security: render_value=False)."""
    widget = PasswordReveal()
    assert widget.render_value is False


@pytest.mark.unit
def test_password_reveal_get_context_name():
    """get_context() produces a context dict with the correct widget name."""
    widget = PasswordReveal()
    ctx = widget.get_context("password", None, {"id": "id_password"})
    assert ctx["widget"]["name"] == "password"


@pytest.mark.unit
def test_password_reveal_get_context_id():
    """get_context() passes the id attribute through."""
    widget = PasswordReveal()
    ctx = widget.get_context("password", None, {"id": "id_password"})
    assert ctx["widget"]["attrs"]["id"] == "id_password"


@pytest.mark.unit
def test_password_reveal_get_context_value_not_rendered():
    """get_context() does not expose the value (render_value=False)."""
    widget = PasswordReveal()
    ctx = widget.get_context("password", "secret", {"id": "id_password"})
    # PasswordInput with render_value=False sets value to empty string or None
    assert not ctx["widget"]["value"]


@pytest.mark.unit
def test_password_reveal_value_from_datadict_returns_string():
    """value_from_datadict() returns a string for a submitted password."""
    widget = PasswordReveal()
    data = QueryDict("password=secret123")
    result = widget.value_from_datadict(data, {}, "password")
    assert result == "secret123"
    assert isinstance(result, str)


@pytest.mark.unit
def test_password_reveal_value_from_datadict_empty():
    """value_from_datadict() returns None when field is absent from QueryDict."""
    widget = PasswordReveal()
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "password")
    assert result is None


@pytest.mark.unit
def test_password_reveal_preserves_user_attrs():
    """User-supplied attrs are stored on the widget."""
    widget = PasswordReveal(attrs={"placeholder": "Enter password"})
    assert widget.attrs.get("placeholder") == "Enter password"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_password_reveal_renders_input():
    """widget.render() produces an <input> element."""
    soup = render_widget(PasswordReveal())
    assert soup.find("input") is not None


@pytest.mark.unit
def test_password_reveal_renders_toggle_button():
    """Rendered HTML contains a toggle button with x-on:click handler."""
    soup = render_widget(PasswordReveal())
    btn = soup.find("button")
    assert btn is not None
    assert btn.get("x-on:click") == "show = !show"


@pytest.mark.unit
def test_password_reveal_alpine_x_data():
    """The wrapper label has Alpine x-data initialising show to false."""
    soup = render_widget(PasswordReveal())
    label = soup.find("label")
    assert label.get("x-data") == "{ show: false }"


@pytest.mark.unit
def test_password_reveal_alpine_x_bind_type():
    """The input has x-bind:type to toggle between password and text."""
    soup = render_widget(PasswordReveal())
    inp = soup.find("input")
    assert inp.get("x-bind:type") == "show ? 'text' : 'password'"


@pytest.mark.unit
def test_password_reveal_wrapped_in_label():
    """The widget is wrapped in a <label class='password-reveal'>."""
    soup = render_widget(PasswordReveal())
    label = soup.find("label", class_="password-reveal")
    assert label is not None
    assert label.find("input") is not None


@pytest.mark.unit
def test_password_reveal_input_has_grow_class():
    """The input element has the 'grow' class for flex layout."""
    soup = render_widget(PasswordReveal())
    inp = soup.find("input")
    assert "grow" in inp.get("class", [])


@pytest.mark.unit
def test_password_reveal_wrapper_id_when_id_present():
    """When an id is provided, the wrapper label gets id='<id>_wrapper'."""
    soup = render_widget(PasswordReveal(), attrs={"id": "id_pw"})
    label = soup.find("label", class_="password-reveal")
    assert label["id"] == "id_pw_wrapper"


@pytest.mark.unit
def test_password_reveal_no_wrapper_id_without_id():
    """Without an id attr, the wrapper label has no id attribute."""
    soup = render_widget(PasswordReveal())
    label = soup.find("label", class_="password-reveal")
    assert not label.has_attr("id")


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_password_reveal_renders_via_form(renderer):
    """PasswordReveal renders correctly when used inside a FormworkForm."""
    form = PasswordRevealForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "password"})
    assert inp is not None


@pytest.mark.integration
def test_password_reveal_form_wraps_in_fieldset(renderer):
    """Field template wraps the PasswordReveal in a fieldset with a stable id."""
    form = PasswordRevealForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_password_field")
    assert fieldset is not None


@pytest.mark.integration
def test_password_reveal_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = PasswordRevealForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "password"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_password_reveal_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = PasswordRevealForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_password_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_password_reveal_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = PasswordRevealForm(prefix="auth")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "auth-password"})
    assert inp is not None
    assert inp["id"] == "id_auth-password"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_password_reveal_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """PasswordReveal produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(PasswordRevealForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(PasswordRevealForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_password_reveal_renders_on_page(simple_page):
    """PasswordReveal input is visible on the /simple/ page."""
    from playwright.sync_api import expect

    inp = simple_page.locator('input[name="password"]')
    expect(inp).to_be_visible()


@pytest.mark.e2e
def test_password_reveal_default_type_is_password(simple_page):
    """Password input starts as type='password' (hidden)."""
    inp = simple_page.locator('input[name="password"]')
    assert inp.get_attribute("type") == "password"


@pytest.mark.e2e
def test_password_reveal_toggle_shows_password(simple_page):
    """Clicking the toggle button changes the input type to 'text'."""
    inp = simple_page.locator('input[name="password"]')
    assert inp.get_attribute("type") == "password"
    simple_page.locator("label.password-reveal button").click()
    simple_page.wait_for_timeout(100)
    assert inp.get_attribute("type") == "text"


@pytest.mark.e2e
def test_password_reveal_toggle_hides_password(simple_page):
    """Clicking the toggle button twice restores type='password'."""
    inp = simple_page.locator('input[name="password"]')
    simple_page.locator("label.password-reveal button").click()
    simple_page.wait_for_timeout(100)
    assert inp.get_attribute("type") == "text"
    simple_page.locator("label.password-reveal button").click()
    simple_page.wait_for_timeout(100)
    assert inp.get_attribute("type") == "password"


@pytest.mark.e2e
def test_password_reveal_wrapper_has_id_attr(simple_page):
    """The wrapper label has an id attribute ending in '_wrapper'."""
    wrapper = simple_page.locator("label.password-reveal")
    wrapper_id = wrapper.get_attribute("id")
    assert wrapper_id is not None
    assert "_wrapper" in wrapper_id


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# PasswordReveal on the /simple/ page is required, but testing error display
# requires a form without other required fields that would also fail.
# Dedicated error-flow tests would need a standalone page for PasswordReveal
# only.  Skipped until that page exists.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_password_reveal_morph_clears_value(simple_page):
    """Django's PasswordInput doesn't render values — morph clears the field."""
    from tests.e2e.conftest import submit

    inp = simple_page.locator('input[name="password"]')
    inp.fill("secret123")
    submit(simple_page)
    assert inp.input_value() == ""


@pytest.mark.e2e
def test_password_reveal_morph_preserves_reveal_state(simple_page):
    """Show/hide toggle state persists through an htmx form morph."""
    from tests.e2e.conftest import submit

    inp = simple_page.locator('input[name="password"]')
    inp.fill("secret")
    simple_page.locator("label.password-reveal button").click()
    simple_page.wait_for_timeout(200)
    assert (
        simple_page.evaluate(
            "document.querySelector('input[name=\"password\"]').type",
        )
        == "text"
    )
    submit(simple_page)
    assert (
        simple_page.evaluate(
            "document.querySelector('input[name=\"password\"]').type",
        )
        == "text"
    )


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.  See issue #26 for the plan.


@pytest.mark.screenshot
def test_password_reveal_screenshot_default(simple_page):
    """Visual snapshot: PasswordReveal in default (hidden/password) state."""
    wrapper = simple_page.locator("#id_password_field")
    wrapper.screenshot(path="test-results/password-reveal-default-actual.png")


@pytest.mark.screenshot
def test_password_reveal_screenshot_revealed(simple_page):
    """Visual snapshot: PasswordReveal in revealed (text) state."""
    simple_page.locator("label.password-reveal button").click()
    simple_page.wait_for_timeout(100)
    wrapper = simple_page.locator("#id_password_field")
    wrapper.screenshot(path="test-results/password-reveal-revealed-actual.png")
