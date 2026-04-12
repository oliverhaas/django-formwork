"""Tests for the DataList widget.

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, attributes
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: renders, fill input
    6. e2e         — error flow: SKIPPED (see comment)
    7. e2e         — morph resilience: typed value preserved across morph
    8. screenshot  — visual states: default, filled
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import DataList

from .conftest import assert_html_equivalent, render_form, render_widget


class DataListForm(FormworkForm):
    """Form fixture for DataList integration tests."""

    browser = forms.CharField(
        widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_datalist_instantiation_stores_list():
    """DataList stores the datalist parameter."""
    widget = DataList(datalist=["A", "B", "C"])
    assert widget.datalist == ["A", "B", "C"]


@pytest.mark.unit
def test_datalist_instantiation_default_empty():
    """DataList with no arguments has an empty datalist."""
    widget = DataList()
    assert widget.datalist == []


@pytest.mark.unit
def test_datalist_get_context_sets_list_attr():
    """get_context() sets the list attribute when an id is present."""
    widget = DataList(datalist=["X"])
    ctx = widget.get_context("browser", None, {"id": "id_browser"})
    assert ctx["widget"]["attrs"]["list"] == "id_browser_list"


@pytest.mark.unit
def test_datalist_get_context_no_list_without_id():
    """get_context() does not set list attr when no id is provided."""
    widget = DataList(datalist=["X"])
    ctx = widget.get_context("browser", None, {})
    assert "list" not in ctx["widget"]["attrs"]


@pytest.mark.unit
def test_datalist_get_context_stores_datalist():
    """get_context() exposes the datalist on the widget context."""
    widget = DataList(datalist=["Chrome", "Firefox"])
    ctx = widget.get_context("browser", None, {"id": "id_browser"})
    assert ctx["widget"]["datalist"] == ["Chrome", "Firefox"]


@pytest.mark.unit
def test_datalist_get_context_empty_datalist():
    """Empty datalist is preserved in context."""
    widget = DataList()
    ctx = widget.get_context("browser", None, {"id": "id_browser"})
    assert ctx["widget"]["datalist"] == []


@pytest.mark.unit
def test_datalist_value_from_datadict_returns_text():
    """Submitted text value is returned as-is."""
    widget = DataList(datalist=["Chrome"])
    data = QueryDict("browser=Firefox")
    result = widget.value_from_datadict(data, {}, "browser")
    assert result == "Firefox"


@pytest.mark.unit
def test_datalist_value_from_datadict_missing_key():
    """Missing key in QueryDict returns None."""
    widget = DataList(datalist=["Chrome"])
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "browser")
    assert result is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_datalist_renders_text_input():
    """DataList renders an <input type='text'>."""
    soup = render_widget(DataList(datalist=["A"]), name="browser", attrs={"id": "id_browser"})
    inp = soup.find("input")
    assert inp is not None
    assert inp.get("type") == "text"


@pytest.mark.unit
def test_datalist_renders_list_attribute():
    """Rendered input has list attribute pointing to the datalist id."""
    soup = render_widget(DataList(datalist=["A"]), name="browser", attrs={"id": "id_browser"})
    inp = soup.find("input")
    assert inp["list"] == "id_browser_list"


@pytest.mark.unit
def test_datalist_renders_datalist_element():
    """A <datalist> element with the correct id is rendered."""
    soup = render_widget(DataList(datalist=["A"]), name="browser", attrs={"id": "id_browser"})
    datalist = soup.find("datalist")
    assert datalist is not None
    assert datalist["id"] == "id_browser_list"


@pytest.mark.unit
def test_datalist_renders_options():
    """Each entry in datalist appears as an <option> element."""
    soup = render_widget(
        DataList(datalist=["Chrome", "Firefox", "Safari"]),
        name="browser",
        attrs={"id": "id_browser"},
    )
    options = soup.find("datalist").find_all("option")
    assert len(options) == 3
    values = [o["value"] for o in options]
    assert values == ["Chrome", "Firefox", "Safari"]


@pytest.mark.unit
def test_datalist_no_datalist_element_without_id():
    """Without an id, no <datalist> element and no list attr is rendered."""
    soup = render_widget(DataList(datalist=["A"]), name="browser")
    datalist = soup.find("datalist")
    assert datalist is None
    inp = soup.find("input")
    assert not inp.has_attr("list")


@pytest.mark.unit
def test_datalist_renders_empty_options():
    """Empty datalist renders a <datalist> with no options."""
    soup = render_widget(DataList(), name="browser", attrs={"id": "id_browser"})
    options = soup.find("datalist").find_all("option")
    assert len(options) == 0


@pytest.mark.unit
def test_datalist_preserves_value():
    """Rendered input reflects the provided value."""
    soup = render_widget(
        DataList(datalist=["A"]),
        name="browser",
        value="hello",
        attrs={"id": "id_browser"},
    )
    inp = soup.find("input")
    assert inp["value"] == "hello"


@pytest.mark.unit
def test_datalist_preserves_placeholder():
    """Placeholder attr from widget attrs is passed through to the input."""
    widget = DataList(datalist=["A"], attrs={"placeholder": "Pick one"})
    soup = render_widget(widget, name="browser", attrs={"id": "id_browser"})
    inp = soup.find("input")
    assert inp["placeholder"] == "Pick one"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_datalist_renders_via_form(renderer):
    """DataList renders correctly when used inside a FormworkForm."""
    form = DataListForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "browser"})
    assert inp is not None
    assert inp.get("type") == "text"


@pytest.mark.integration
def test_datalist_form_wraps_in_fieldset(renderer):
    """Field template wraps DataList in a fieldset with a stable id."""
    form = DataListForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_browser_field")
    assert fieldset is not None


@pytest.mark.integration
def test_datalist_form_has_datalist_element(renderer):
    """The rendered form includes the <datalist> element with options."""
    form = DataListForm()
    soup = render_form(form, renderer=renderer)
    datalist = soup.find("datalist")
    assert datalist is not None
    options = datalist.find_all("option")
    assert len(options) == 3


@pytest.mark.integration
def test_datalist_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = DataListForm(data={"browser": ""})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "browser"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_datalist_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = DataListForm(data={"browser": ""})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_browser_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_datalist_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = DataListForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-browser"})
    assert inp is not None
    assert inp["id"] == "id_cfg-browser"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_datalist_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """DataList produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(DataListForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(DataListForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_datalist_renders_on_page(simple_page):
    """DataList input is visible on the /simple/ page."""
    from playwright.sync_api import expect

    inp = simple_page.locator('input[name="browser"]')
    expect(inp).to_be_visible()


@pytest.mark.e2e
def test_datalist_has_list_attribute(simple_page):
    """Input on page has a list attribute pointing to a datalist element."""
    inp = simple_page.locator('input[name="browser"]')
    list_attr = inp.get_attribute("list")
    assert list_attr is not None
    dl = simple_page.locator(f"#{list_attr}")
    assert dl.count() == 1


@pytest.mark.e2e
def test_datalist_page_has_options(simple_page):
    """The datalist element on the page has the expected options."""
    inp = simple_page.locator('input[name="browser"]')
    list_id = inp.get_attribute("list")
    options = simple_page.locator(f"#{list_id} option")
    assert options.count() == 5  # Chrome, Firefox, Safari, Edge, Opera


@pytest.mark.e2e
def test_datalist_user_can_type(simple_page):
    """User can type freely into the datalist input."""
    inp = simple_page.locator('input[name="browser"]')
    inp.fill("Custom value")
    assert inp.input_value() == "Custom value"


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# DataList is not required on the /simple/ page (required=False), so no
# error-flow tests can be triggered without a separate required-DataList
# page fixture.  Left as a gap — tracked as part of broader error-state
# test coverage work.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_datalist_morph_preserves_typed_value(simple_page):
    """Typed value in the datalist input survives an htmx form morph."""
    from tests.e2e.conftest import submit

    inp = simple_page.locator('input[name="browser"]')
    inp.fill("Chrome")
    submit(simple_page)
    assert simple_page.locator('input[name="browser"]').input_value() == "Chrome"


@pytest.mark.e2e
def test_datalist_morph_preserves_empty(simple_page):
    """Empty datalist input remains empty after morph."""
    from tests.e2e.conftest import submit

    inp = simple_page.locator('input[name="browser"]')
    assert inp.input_value() == ""
    submit(simple_page)
    assert simple_page.locator('input[name="browser"]').input_value() == ""


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.


@pytest.mark.screenshot
def test_datalist_screenshot_default(simple_page, assert_screenshot):
    """Visual snapshot: DataList in default (empty) state."""
    wrapper = simple_page.locator("#id_browser_field")
    assert_screenshot(wrapper, "datalist-default.png")


@pytest.mark.screenshot
def test_datalist_screenshot_filled(simple_page, assert_screenshot):
    """Visual snapshot: DataList with a typed value."""
    simple_page.locator('input[name="browser"]').fill("Firefox")
    wrapper = simple_page.locator("#id_browser_field")
    assert_screenshot(wrapper, "datalist-filled.png")
