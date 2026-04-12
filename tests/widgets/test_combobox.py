"""Canonical test patterns for the ComboBox widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_combobox.py                 # everything
    uv run pytest tests/widgets/ -m unit                         # all widgets, unit only
    uv run pytest tests/widgets/test_combobox.py -m "not e2e"   # skip browser tests

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, classes, attributes
    3. integration — form integration: field template, error state, morph IDs
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: typing, picking suggestion, clear
    6. e2e         — error flow: skipped (no required ComboBox on the /combobox/ page)
    7. e2e         — morph resilience: typed value and selected suggestions preserved
    8. screenshot  — visual states: default, open dropdown, suggestion selected
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ComboBox

from .conftest import assert_html_equivalent, render_form, render_widget


class ComboBoxForm(FormworkForm):
    """Form fixture for ComboBox integration tests."""

    tag = forms.CharField(
        widget=ComboBox(suggestions=["Alpha", "Beta", "Gamma"]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_combobox_instantiation_default():
    """ComboBox can be instantiated with no arguments."""
    widget = ComboBox()
    assert widget.suggestions == []
    assert widget.multiple is False
    assert widget.search_url is None


@pytest.mark.unit
def test_combobox_instantiation_with_suggestions():
    """ComboBox stores provided suggestions."""
    widget = ComboBox(suggestions=["A", "B", "C"])
    assert widget.suggestions == ["A", "B", "C"]


@pytest.mark.unit
def test_combobox_instantiation_multiple():
    """ComboBox stores multiple flag."""
    widget = ComboBox(suggestions=["A"], multiple=True)
    assert widget.multiple is True


@pytest.mark.unit
def test_combobox_instantiation_search_url():
    """ComboBox stores search_url."""
    widget = ComboBox(search_url="/search/")
    assert widget.search_url == "/search/"


@pytest.mark.unit
def test_combobox_instantiation_icons():
    """ComboBox stores icons dict."""
    widget = ComboBox(suggestions=["A"], icons={"A": "<svg/>"})
    assert widget.icons == {"A": "<svg/>"}


@pytest.mark.unit
def test_combobox_get_context_suggestions_as_dicts():
    """get_context() converts suggestion strings to dicts with text/icon/description."""
    widget = ComboBox(suggestions=["A", "B"], icons={"A": mark_safe("<svg/>")})
    ctx = widget.get_context("test", "", {})
    sugs = ctx["widget"]["suggestions"]
    assert sugs[0] == {"text": "A", "icon": mark_safe("<svg/>"), "description": ""}
    assert sugs[1] == {"text": "B", "icon": "", "description": ""}


@pytest.mark.unit
def test_combobox_get_context_multiple_mode():
    """get_context() exposes multiple flag correctly."""
    widget = ComboBox(suggestions=["A", "B"], multiple=True)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is True


@pytest.mark.unit
def test_combobox_get_context_single_mode():
    """get_context() defaults to multiple=False."""
    widget = ComboBox(suggestions=["A", "B"])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is False


@pytest.mark.unit
def test_combobox_get_context_search_url():
    """get_context() exposes search_url."""
    widget = ComboBox(search_url="/search/")
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] == "/search/"


@pytest.mark.unit
def test_combobox_get_context_search_url_none_by_default():
    """get_context() has search_url=None when not provided."""
    widget = ComboBox(suggestions=["A"])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_combobox_value_from_datadict_returns_string():
    """value_from_datadict returns the typed string value."""
    widget = ComboBox(suggestions=["Alpha"])
    data = QueryDict("test=Rust")
    val = widget.value_from_datadict(data, {}, "test")
    assert val == "Rust"


@pytest.mark.unit
def test_combobox_value_from_datadict_empty():
    """value_from_datadict returns empty string when nothing submitted."""
    widget = ComboBox(suggestions=["Alpha"])
    data = QueryDict("")
    val = widget.value_from_datadict(data, {}, "test")
    assert val is None


@pytest.mark.unit
def test_combobox_empty_suggestions_get_context():
    """ComboBox with no suggestions produces an empty suggestions list in context."""
    widget = ComboBox()
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["suggestions"] == []


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_combobox_renders_dropdown_wrapper():
    """render() produces a div with class 'dropdown'."""
    widget = ComboBox(suggestions=["Alpha", "Beta"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="dropdown")
    assert wrapper is not None


@pytest.mark.unit
def test_combobox_class_on_wrapper():
    """render() produces a div with class 'combobox'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="combobox")
    assert wrapper is not None


@pytest.mark.unit
def test_combobox_text_input_is_form_field():
    """The text input submits directly — no hidden input."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input is not None
    assert text_input["name"] == "test"
    assert text_input["type"] == "text"
    # No hidden input
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden is None


@pytest.mark.unit
def test_combobox_role():
    """The combobox input has role='combobox' and aria-autocomplete='list'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["role"] == "combobox"
    assert trigger["aria-autocomplete"] == "list"


@pytest.mark.unit
def test_combobox_suggestions_as_buttons():
    """Each suggestion renders as a button[type=button]."""
    widget = ComboBox(suggestions=["Alpha", "Beta", "Gamma"])
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 3


@pytest.mark.unit
def test_combobox_suggestion_labels():
    """Suggestion text appears in span elements."""
    widget = ComboBox(suggestions=["Alpha", "Beta"])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_combobox_preserves_value():
    """render() sets the input value to the current field value."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", value="hello")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input["value"] == "hello"


@pytest.mark.unit
def test_combobox_default_placeholder():
    """Default placeholder contains 'search'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert "search" in text_input.get("placeholder", "").lower()


@pytest.mark.unit
def test_combobox_custom_placeholder():
    """Custom placeholder is rendered."""
    widget = ComboBox(suggestions=["Alpha"], attrs={"placeholder": "Type here"})
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input["placeholder"] == "Type here"


@pytest.mark.unit
def test_combobox_alpine_x_data():
    """Wrapper div has x-data Alpine directive."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper is not None


@pytest.mark.unit
def test_combobox_no_results_element():
    """A 'No results' paragraph is rendered for client-side mode."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    no_results = soup.find("p", string="No results")
    assert no_results is not None


@pytest.mark.unit
def test_combobox_listbox_role():
    """The suggestions list has role='listbox'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert listbox is not None


@pytest.mark.unit
def test_combobox_aria_invalid():
    """aria-invalid='true' on wrapper propagates to the input."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["aria-invalid"] == "true"


@pytest.mark.unit
def test_combobox_htmx_attrs_when_search_url():
    """When search_url is set, htmx attributes are added to the input."""
    widget = ComboBox(search_url="/search/")
    soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["hx-get"] == "/search/"
    assert "input changed delay:300ms" in trigger["hx-trigger"]
    assert trigger["hx-target"] == "#id_tags_listbox"
    assert trigger["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_combobox_no_htmx_attrs_without_search_url():
    """Without search_url, no htmx attributes are added."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    trigger = soup.find("input", class_="combobox-input")
    assert not trigger.has_attr("hx-get")


@pytest.mark.unit
def test_combobox_no_client_suggestions_when_search_url():
    """When search_url is set, client-side suggestion buttons are not rendered."""
    widget = ComboBox(suggestions=["Alpha"], search_url="/search/")
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 0


@pytest.mark.unit
def test_combobox_no_alpine_no_results_when_search_url():
    """When search_url is set, 'No results' element is not rendered."""
    widget = ComboBox(search_url="/search/")
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_combobox_icon_rendering():
    """Icons are rendered inline in suggestion buttons."""
    widget = ComboBox(
        suggestions=["Python", "Go"],
        icons={"Python": mark_safe('<img src="py.svg">')},
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "py.svg"})
    assert icon is not None


@pytest.mark.unit
def test_combobox_no_icon_when_not_provided():
    """No icon elements appear when icons dict is empty."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


@pytest.mark.unit
def test_combobox_event_delegation_data_attrs():
    """Suggestion buttons carry data-suggestion for event delegation."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    btn = soup.find("button", {"type": "button"})
    assert btn["data-suggestion"] == "Alpha"


@pytest.mark.unit
def test_combobox_wrapper_has_id():
    """Combobox wrapper div gets an id derived from the field id."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    wrapper = soup.find("div", class_="combobox")
    assert wrapper["id"] == "id_test_combobox"


@pytest.mark.unit
def test_combobox_no_wrapper_id_without_id():
    """Combobox wrapper div has no id when no field id is provided."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="combobox")
    assert not wrapper.has_attr("id")


@pytest.mark.unit
def test_combobox_empty_suggestions_renders_no_buttons():
    """ComboBox with no suggestions renders zero buttons."""
    widget = ComboBox()
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 0


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_combobox_renders_via_form(renderer):
    """ComboBox renders correctly when used inside a FormworkForm."""
    form = ComboBoxForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "tag"})
    assert inp is not None
    assert inp["type"] == "text"


@pytest.mark.integration
def test_combobox_form_wraps_in_fieldset(renderer):
    """Field template wraps the ComboBox in a fieldset with a stable id."""
    form = ComboBoxForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_tag_field")
    assert fieldset is not None


@pytest.mark.integration
def test_combobox_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = ComboBoxForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "tag"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_combobox_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = ComboBoxForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_tag_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_combobox_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = ComboBoxForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-tag"})
    assert inp is not None
    assert inp["id"] == "id_cfg-tag"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_combobox_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """ComboBox produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(ComboBoxForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(ComboBoxForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_combobox_renders_on_page(combobox_page):
    """ComboBox is visible on the /combobox/ page."""
    combo = combobox_page.locator(".dropdown.combobox").first
    assert combo.is_visible()


@pytest.mark.e2e
def test_combobox_typing_shows_filtered_suggestions(combobox_page):
    """Typing in the input filters suggestions to matching entries."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.combobox").first
    assert combo.locator("button", has_text="Python").is_visible()
    assert not combo.locator("button", has_text="Go").is_visible()


@pytest.mark.e2e
def test_combobox_pick_suggestion(combobox_page):
    """Clicking a suggestion populates the input with that value."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Ru")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.combobox").first
    combo.locator("button", has_text="Rust").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Rust"


@pytest.mark.e2e
def test_combobox_free_text_allowed(combobox_page):
    """Arbitrary text can be typed (ComboBox is free text, not constrained)."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combobox_multiple_pick_adds_value(combobox_page):
    """In multiple mode, clicking a suggestion appends it."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" in inp.input_value()


@pytest.mark.e2e
def test_combobox_multiple_pick_second_appends(combobox_page):
    """In multiple mode, a second pick appends to the comma-separated list."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    combo.locator("button", has_text="Sushi").click()
    combobox_page.wait_for_timeout(100)
    val = inp.input_value()
    assert "Pizza" in val
    assert "Sushi" in val


@pytest.mark.e2e
def test_combobox_multiple_toggle_off(combobox_page):
    """In multiple mode, clicking a selected suggestion removes it."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" in inp.input_value()
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" not in inp.input_value()


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# The /combobox/ page has no required ComboBox fields (all required=False),
# so dedicated error-flow tests cannot be triggered without a separate page.
# Skipped until a required-field variant of the ComboBox page is available.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_combobox_morph_preserves_typed_value(combobox_page):
    """Typed free-text value survives an htmx form morph."""
    from tests.e2e.conftest import submit

    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    submit(combobox_page)
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combobox_morph_preserves_multiple_selected(combobox_page):
    """Comma-separated multiple selections survive an htmx form morph."""
    from tests.e2e.conftest import submit

    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    combo.locator("button", has_text="Sushi").click()
    combobox_page.wait_for_timeout(100)
    # Close dropdown and blur to strip trailing comma
    combobox_page.keyboard.press("Escape")
    combobox_page.wait_for_timeout(200)
    inp.blur()
    combobox_page.wait_for_timeout(100)
    val_before = inp.input_value()
    submit(combobox_page)
    assert inp.input_value() == val_before


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.


@pytest.mark.screenshot
def test_combobox_screenshot_default(combobox_page):
    """Visual snapshot: ComboBox in default (empty) state."""
    wrapper = combobox_page.locator(".dropdown.combobox").first
    wrapper.screenshot(path="test-results/combobox-default-actual.png")


@pytest.mark.screenshot
def test_combobox_screenshot_open_dropdown(combobox_page):
    """Visual snapshot: ComboBox with dropdown open."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("P")
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator(".dropdown.combobox").first
    wrapper.screenshot(path="test-results/combobox-open-actual.png")


@pytest.mark.screenshot
def test_combobox_screenshot_suggestion_selected(combobox_page):
    """Visual snapshot: ComboBox after a suggestion has been selected."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combobox_page.locator(".dropdown.combobox").first.locator("button", has_text="Python").click()
    combobox_page.wait_for_timeout(100)
    wrapper = combobox_page.locator(".dropdown.combobox").first
    wrapper.screenshot(path="test-results/combobox-selected-actual.png")
