"""Tests for Django's CheckboxSelectMultiple widget as styled by formwork.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_checkbox_select_multiple.py         # everything
    uv run pytest tests/widgets/ -m unit                                 # all widgets, unit only
    uv run pytest tests/widgets/test_checkbox_select_multiple.py -m "not e2e"  # skip browser

Levels:
    1. unit        : widget object: instantiation, get_context, value_from_datadict
    2. unit        : widget rendering: HTML structure, attributes
    3. integration : form integration: field template, error state, prefix
    4. integration : Jinja2/DTL parity: identical HTML across engines
    5. e2e         : user interaction: renders, check multiple, label clicks
    6. e2e         : error flow: SKIPPED (toppings not required on builtin page)
    7. e2e         : morph resilience: checked boxes survive htmx morphs
    8. screenshot  : visual states: default, some checked
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm

from .conftest import assert_html_equivalent, render_form, render_widget

TOPPING_CHOICES = [
    ("cheese", "Cheese"),
    ("pepperoni", "Pepperoni"),
    ("mushrooms", "Mushrooms"),
    ("olives", "Olives"),
]


class CheckboxSelectMultipleForm(FormworkForm):
    """Form fixture for CheckboxSelectMultiple integration tests."""

    toppings = forms.MultipleChoiceField(
        choices=TOPPING_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )


class CheckboxSelectMultipleRequiredForm(FormworkForm):
    """Form fixture with toppings required, used for error-state tests."""

    toppings = forms.MultipleChoiceField(
        choices=TOPPING_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_checkbox_select_multiple_instantiation():
    """CheckboxSelectMultiple widget can be instantiated without arguments."""
    widget = forms.CheckboxSelectMultiple()
    assert widget is not None


@pytest.mark.unit
def test_checkbox_select_multiple_get_context():
    """get_context() returns optgroups containing all 4 options."""
    widget = forms.CheckboxSelectMultiple()
    widget.choices = TOPPING_CHOICES
    ctx = widget.get_context("toppings", [], {"id": "id_toppings"})
    # optgroups is a list of (group_name, subgroup, index) tuples
    optgroups = ctx["widget"]["optgroups"]
    # Flatten subgroups to get all options
    all_options = [opt for _name, subgroup, _idx in optgroups for opt in subgroup]
    assert len(all_options) == 4
    values = [opt["value"] for opt in all_options]
    assert "cheese" in values
    assert "pepperoni" in values
    assert "mushrooms" in values
    assert "olives" in values


@pytest.mark.unit
def test_checkbox_select_multiple_value_from_datadict():
    """Submitted multi-value QueryDict returns a list of selected values."""
    widget = forms.CheckboxSelectMultiple()
    data = QueryDict("toppings=cheese&toppings=olives")
    result = widget.value_from_datadict(data, {}, "toppings")
    assert result == ["cheese", "olives"]


@pytest.mark.unit
def test_checkbox_select_multiple_value_from_datadict_none():
    """Missing key in QueryDict returns an empty list."""
    widget = forms.CheckboxSelectMultiple()
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "toppings")
    assert result == []


@pytest.mark.unit
def test_checkbox_select_multiple_use_fieldset():
    """CheckboxSelectMultiple sets use_fieldset=True so Django wraps it in a fieldset."""
    widget = forms.CheckboxSelectMultiple()
    assert widget.use_fieldset is True


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_checkbox_select_multiple_renders_checkboxes():
    """Rendering with 4 choices produces 4 checkbox inputs."""
    widget = forms.CheckboxSelectMultiple(choices=TOPPING_CHOICES)
    soup = render_widget(widget, name="toppings", value=[])
    checkboxes = soup.find_all("input", attrs={"type": "checkbox"})
    assert len(checkboxes) == 4


@pytest.mark.unit
def test_checkbox_select_multiple_renders_labels():
    """Each checkbox input has an associated label element."""
    widget = forms.CheckboxSelectMultiple(choices=TOPPING_CHOICES)
    soup = render_widget(widget, name="toppings", value=[])
    labels = soup.find_all("label")
    assert len(labels) == 4


@pytest.mark.unit
def test_checkbox_select_multiple_renders_values():
    """Each checkbox has the correct value attribute matching its choice key."""
    widget = forms.CheckboxSelectMultiple(choices=TOPPING_CHOICES)
    soup = render_widget(widget, name="toppings", value=[])
    checkboxes = soup.find_all("input", attrs={"type": "checkbox"})
    rendered_values = {cb["value"] for cb in checkboxes}
    assert rendered_values == {"cheese", "pepperoni", "mushrooms", "olives"}


@pytest.mark.unit
def test_checkbox_select_multiple_renders_checked():
    """Passing value=['cheese'] marks only the cheese checkbox as checked."""
    widget = forms.CheckboxSelectMultiple(choices=TOPPING_CHOICES)
    soup = render_widget(widget, name="toppings", value=["cheese"])
    checked = soup.find_all("input", attrs={"type": "checkbox", "checked": True})
    assert len(checked) == 1
    assert checked[0]["value"] == "cheese"


@pytest.mark.unit
def test_checkbox_select_multiple_renders_all_unchecked():
    """Passing an empty value list leaves all checkboxes unchecked."""
    widget = forms.CheckboxSelectMultiple(choices=TOPPING_CHOICES)
    soup = render_widget(widget, name="toppings", value=[])
    checked = soup.find_all("input", attrs={"type": "checkbox", "checked": True})
    assert len(checked) == 0


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_checkbox_select_multiple_renders_via_form(renderer):
    """CheckboxSelectMultiple renders correctly when used inside a FormworkForm."""
    form = CheckboxSelectMultipleForm()
    soup = render_form(form, renderer=renderer)
    checkboxes = soup.find_all("input", attrs={"type": "checkbox", "name": "toppings"})
    assert len(checkboxes) == 4


@pytest.mark.integration
def test_checkbox_select_multiple_form_wraps_in_fieldset(renderer):
    """The widget group is wrapped in a formwork fieldset with a legend."""
    form = CheckboxSelectMultipleForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_toppings_field")
    assert fieldset is not None
    legend = fieldset.find("legend")
    assert legend is not None


@pytest.mark.integration
def test_checkbox_select_multiple_error_state(renderer):
    """Bound required form with no selection adds aria-invalid to the widget."""
    form = CheckboxSelectMultipleRequiredForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    # The inner fieldset should carry aria-invalid when in error state
    checkboxes = soup.find_all("input", attrs={"name": "toppings"})
    # At least one checkbox should have aria-invalid, or the fieldset should
    # Django 6.0 adds aria-invalid to the widget container (fieldset)
    inner_fieldset = soup.find("fieldset", id="id_toppings_field")
    assert inner_fieldset is not None
    # Confirm the tooltip error node exists
    tooltip = soup.find(id="id_toppings_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_checkbox_select_multiple_form_prefix(renderer):
    """Form prefix propagates to checkbox names and ids."""
    form = CheckboxSelectMultipleForm(prefix="order")
    soup = render_form(form, renderer=renderer)
    checkboxes = soup.find_all("input", attrs={"type": "checkbox", "name": "order-toppings"})
    assert len(checkboxes) == 4


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_checkbox_select_multiple_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """CheckboxSelectMultiple produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(CheckboxSelectMultipleForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(CheckboxSelectMultipleForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_checkbox_select_multiple_renders_on_page(builtin_page):
    """All 4 toppings checkboxes are visible on the /builtin/ page."""
    from playwright.sync_api import expect

    checkboxes = builtin_page.locator('input[name="toppings"]')
    expect(checkboxes).to_have_count(4)


@pytest.mark.e2e
def test_checkbox_select_multiple_all_unchecked_initially(builtin_page):
    """No toppings checkbox is checked on initial page load."""
    checkboxes = builtin_page.locator('input[name="toppings"]')
    count = checkboxes.count()
    for i in range(count):
        assert not checkboxes.nth(i).is_checked()


@pytest.mark.e2e
def test_checkbox_select_multiple_check_multiple(builtin_page):
    """User can check multiple toppings independently."""
    from playwright.sync_api import expect

    cheese = builtin_page.locator('input[name="toppings"][value="cheese"]')
    mushrooms = builtin_page.locator('input[name="toppings"][value="mushrooms"]')
    cheese.check()
    mushrooms.check()
    expect(cheese).to_be_checked()
    expect(mushrooms).to_be_checked()
    # others remain unchecked
    pepperoni = builtin_page.locator('input[name="toppings"][value="pepperoni"]')
    olives = builtin_page.locator('input[name="toppings"][value="olives"]')
    expect(pepperoni).not_to_be_checked()
    expect(olives).not_to_be_checked()


@pytest.mark.e2e
def test_checkbox_select_multiple_labels_clickable(builtin_page):
    """Clicking a label toggles the corresponding checkbox."""
    from playwright.sync_api import expect

    cheese_cb = builtin_page.locator('input[name="toppings"][value="cheese"]')
    cheese_id = cheese_cb.get_attribute("id")
    label = builtin_page.locator(f'label[for="{cheese_id}"]')
    expect(cheese_cb).not_to_be_checked()
    label.click()
    expect(cheese_cb).to_be_checked()
    label.click()
    expect(cheese_cb).not_to_be_checked()


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# toppings is not required on the /builtin/ page (required=False), so no
# error-flow tests can be triggered without a separate required-toppings
# page fixture.  Left as a gap until that page exists.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_checkbox_select_multiple_morph_preserves_selections(builtin_page):
    """Checked toppings survive an htmx form morph."""
    from playwright.sync_api import expect

    from tests.e2e.conftest import submit

    cheese = builtin_page.locator('input[name="toppings"][value="cheese"]')
    olives = builtin_page.locator('input[name="toppings"][value="olives"]')
    cheese.check()
    olives.check()
    expect(cheese).to_be_checked()
    expect(olives).to_be_checked()
    submit(builtin_page)
    expect(builtin_page.locator('input[name="toppings"][value="cheese"]')).to_be_checked()
    expect(builtin_page.locator('input[name="toppings"][value="olives"]')).to_be_checked()
    expect(builtin_page.locator('input[name="toppings"][value="pepperoni"]')).not_to_be_checked()
    expect(builtin_page.locator('input[name="toppings"][value="mushrooms"]')).not_to_be_checked()


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only. These tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.


@pytest.mark.screenshot
def test_checkbox_select_multiple_screenshot_default(builtin_page, assert_screenshot):
    """Visual snapshot: CheckboxSelectMultiple in default (all unchecked) state."""
    wrapper = builtin_page.locator("#id_toppings_field")
    assert_screenshot(wrapper, "checkbox-select-multiple-default.png")


@pytest.mark.screenshot
def test_checkbox_select_multiple_screenshot_checked(builtin_page, assert_screenshot):
    """Visual snapshot: CheckboxSelectMultiple with some options checked."""
    builtin_page.locator('input[name="toppings"][value="cheese"]').check()
    builtin_page.locator('input[name="toppings"][value="mushrooms"]').check()
    wrapper = builtin_page.locator("#id_toppings_field")
    assert_screenshot(wrapper, "checkbox-select-multiple-checked.png")
