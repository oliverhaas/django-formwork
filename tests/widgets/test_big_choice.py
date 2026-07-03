"""Tests for the BigRadioSelect and BigCheckboxSelect widgets.

Levels:
    1. unit        — widget object: template_name, base classes, get_context
    2. unit        — widget rendering: cards, inputs, selected + invalid state
    3. integration — form integration: fieldset wrapping, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import BigCheckboxSelect, BigRadioSelect

from .conftest import assert_html_equivalent, render_form, render_widget

PLANS = [("basic", "Basic"), ("pro", "Pro"), ("max", "Max")]
ADDONS = [("ssl", "SSL"), ("cdn", "CDN"), ("wafraud", "WAF")]


class BigRadioForm(FormworkForm):
    """Form fixture for BigRadioSelect integration tests."""

    plan = forms.ChoiceField(choices=PLANS, widget=BigRadioSelect)


class BigCheckboxForm(FormworkForm):
    """Form fixture for BigCheckboxSelect integration tests."""

    addons = forms.MultipleChoiceField(choices=ADDONS, widget=BigCheckboxSelect, required=False)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_big_radio_select_template_name():
    """BigRadioSelect uses the shared big-choice template."""
    assert BigRadioSelect().template_name == "formwork/widgets/big_choice.html"


@pytest.mark.unit
def test_big_checkbox_select_template_name():
    """BigCheckboxSelect uses the same shared big-choice template."""
    assert BigCheckboxSelect().template_name == "formwork/widgets/big_choice.html"


@pytest.mark.unit
def test_big_radio_select_is_radio_select():
    """BigRadioSelect is a RadioSelect (single choice)."""
    assert isinstance(BigRadioSelect(), forms.RadioSelect)


@pytest.mark.unit
def test_big_checkbox_select_is_checkbox_multiple():
    """BigCheckboxSelect is a CheckboxSelectMultiple (multi choice)."""
    assert isinstance(BigCheckboxSelect(), forms.CheckboxSelectMultiple)


@pytest.mark.unit
def test_big_choice_get_context_surfaces_aria_invalid():
    """get_context lifts the hyphenated aria-invalid into a template-friendly key."""
    ctx = BigRadioSelect(choices=PLANS).get_context("plan", None, {"aria-invalid": "true"})
    assert ctx["widget"]["aria_invalid"] == "true"


@pytest.mark.unit
def test_big_choice_get_context_aria_invalid_defaults_none():
    """Without an error, aria_invalid is None so no invalid marker is rendered."""
    ctx = BigRadioSelect(choices=PLANS).get_context("plan", None, {})
    assert ctx["widget"]["aria_invalid"] is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_big_radio_renders_one_card_per_choice():
    """Every choice is rendered as its own selectable card."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", attrs={"id": "id_plan"})
    assert len(soup.select("label.big-choice-card")) == len(PLANS)


@pytest.mark.unit
def test_big_radio_renders_radio_inputs():
    """BigRadioSelect renders <input type='radio'> controls."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", attrs={"id": "id_plan"})
    inputs = soup.select("label.big-choice-card input")
    assert inputs and all(inp["type"] == "radio" for inp in inputs)


@pytest.mark.unit
def test_big_checkbox_renders_checkbox_inputs():
    """BigCheckboxSelect renders <input type='checkbox'> controls."""
    soup = render_widget(BigCheckboxSelect(choices=ADDONS), name="addons", attrs={"id": "id_addons"})
    inputs = soup.select("label.big-choice-card input")
    assert inputs and all(inp["type"] == "checkbox" for inp in inputs)


@pytest.mark.unit
def test_big_radio_marks_selected_card():
    """The chosen value's input is checked; the others are not."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", value="pro", attrs={"id": "id_plan"})
    checked = [inp for inp in soup.select("input") if inp.has_attr("checked")]
    assert len(checked) == 1
    assert checked[0]["value"] == "pro"


@pytest.mark.unit
def test_big_checkbox_marks_multiple_selected():
    """BigCheckboxSelect checks every selected value."""
    soup = render_widget(
        BigCheckboxSelect(choices=ADDONS),
        name="addons",
        value=["ssl", "cdn"],
        attrs={"id": "id_addons"},
    )
    checked = {inp["value"] for inp in soup.select("input") if inp.has_attr("checked")}
    assert checked == {"ssl", "cdn"}


@pytest.mark.unit
def test_big_choice_renders_label_text():
    """Each card shows the choice's human label in a semantic span."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", attrs={"id": "id_plan"})
    labels = [span.get_text(strip=True) for span in soup.select("span.big-choice-label")]
    assert labels == ["Basic", "Pro", "Max"]


@pytest.mark.unit
def test_big_choice_card_class_is_semantic_only():
    """The card carries only its semantic class; styling lives in CSS, not markup."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", attrs={"id": "id_plan"})
    card = soup.select_one("label.big-choice-card")
    assert card["class"] == ["big-choice-card"]


@pytest.mark.unit
def test_big_choice_not_invalid_by_default():
    """No data-invalid marker is emitted when the widget is valid."""
    soup = render_widget(BigRadioSelect(choices=PLANS), name="plan", attrs={"id": "id_plan"})
    wrapper = soup.select_one("div.big-choice")
    assert not wrapper.has_attr("data-invalid")


@pytest.mark.unit
def test_big_choice_marks_invalid_wrapper():
    """An aria-invalid attr surfaces as a data-invalid marker on the wrapper."""
    soup = render_widget(
        BigRadioSelect(choices=PLANS),
        name="plan",
        attrs={"id": "id_plan", "aria-invalid": "true"},
    )
    wrapper = soup.select_one("div.big-choice")
    assert wrapper["data-invalid"] == "true"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_big_radio_renders_via_form(renderer):
    """BigRadioSelect renders its cards inside a FormworkForm."""
    soup = render_form(BigRadioForm(), renderer=renderer)
    assert len(soup.select("label.big-choice-card")) == len(PLANS)


@pytest.mark.integration
def test_big_choice_form_wraps_in_fieldset(renderer):
    """The field template wraps the widget in a fieldset with a stable id."""
    soup = render_form(BigRadioForm(), renderer=renderer)
    assert soup.find("fieldset", id="id_plan_field") is not None


@pytest.mark.integration
def test_big_choice_invalid_form_marks_wrapper(renderer):
    """A bound form with a missing required choice marks the wrapper invalid."""
    form = BigRadioForm(data={})
    assert not form.is_valid()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.select_one("div.big-choice")
    assert wrapper["data-invalid"] == "true"


@pytest.mark.integration
def test_big_choice_form_prefix(renderer):
    """Form prefix propagates to the option input names."""
    soup = render_form(BigCheckboxForm(prefix="cfg"), renderer=renderer)
    inputs = soup.select("label.big-choice-card input")
    assert inputs and all(inp["name"] == "cfg-addons" for inp in inputs)


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_big_radio_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """BigRadioSelect produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(BigRadioForm(initial={"plan": "pro"}), renderer=dtl_renderer)
    soup_jinja2 = render_form(BigRadioForm(initial={"plan": "pro"}), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_big_checkbox_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """BigCheckboxSelect produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(BigCheckboxForm(initial={"addons": ["ssl", "cdn"]}), renderer=dtl_renderer)
    soup_jinja2 = render_form(BigCheckboxForm(initial={"addons": ["ssl", "cdn"]}), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_big_choice_invalid_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """The invalid state stays in parity across engines."""
    soup_dtl = render_form(BigRadioForm(data={}), renderer=dtl_renderer)
    soup_jinja2 = render_form(BigRadioForm(data={}), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
