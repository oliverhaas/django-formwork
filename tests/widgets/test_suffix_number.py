"""Tests for the SuffixNumberInput widget.

Levels:
    1. unit        — widget object: instantiation, suffix flag, get_context
    2. unit        — widget rendering: input plus affix HTML structure
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import SuffixNumberInput

from .conftest import assert_html_equivalent, render_form, render_widget


class SuffixNumberForm(FormworkForm):
    """Form fixture for SuffixNumberInput integration tests."""

    weight = forms.DecimalField(
        widget=SuffixNumberInput(suffix="kg", attrs={"step": "0.1"}),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_suffix_number_instantiation():
    """SuffixNumberInput exposes the expected template_name."""
    widget = SuffixNumberInput()
    assert widget.template_name == "formwork/widgets/suffix_number.html"


@pytest.mark.unit
def test_suffix_number_inherits_number_input():
    """SuffixNumberInput is a subclass of Django's NumberInput."""
    assert isinstance(SuffixNumberInput(), forms.NumberInput)


@pytest.mark.unit
def test_suffix_number_suffix_stored():
    """The suffix is retained on the widget."""
    assert SuffixNumberInput(suffix="%").suffix == "%"


@pytest.mark.unit
def test_suffix_number_suffix_defaults_empty():
    """Without a suffix the widget carries an empty string."""
    assert SuffixNumberInput().suffix == ""


@pytest.mark.unit
def test_suffix_number_get_context_exposes_suffix():
    """get_context surfaces the suffix for the template."""
    ctx = SuffixNumberInput(suffix="USD").get_context("field", None, {})
    assert ctx["widget"]["suffix"] == "USD"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_suffix_number_renders_number_input():
    """The widget renders an <input type='number'>."""
    soup = render_widget(SuffixNumberInput(suffix="kg"), name="weight", attrs={"id": "id_weight"})
    assert soup.find("input", attrs={"type": "number"}) is not None


@pytest.mark.unit
def test_suffix_number_renders_affix_with_suffix_text():
    """The suffix text renders in the affix span."""
    soup = render_widget(SuffixNumberInput(suffix="kg"), name="weight", attrs={"id": "id_weight"})
    affix = soup.find("span", class_="suffix-number-affix")
    assert affix is not None
    assert affix.get_text(strip=True) == "kg"


@pytest.mark.unit
def test_suffix_number_no_affix_without_suffix():
    """No affix span is rendered when the suffix is empty."""
    soup = render_widget(SuffixNumberInput(), name="weight", attrs={"id": "id_weight"})
    assert soup.find("span", class_="suffix-number-affix") is None


@pytest.mark.unit
def test_suffix_number_affix_styling_lives_in_css():
    """The affix carries only its semantic class; positioning is applied via CSS."""
    soup = render_widget(SuffixNumberInput(suffix="%"), name="rate", attrs={"id": "id_rate"})
    affix = soup.find("span", class_="suffix-number-affix")
    assert affix["class"] == ["suffix-number-affix"]


@pytest.mark.unit
def test_suffix_number_value_rendered():
    """A bound value is rendered in the value attribute."""
    soup = render_widget(SuffixNumberInput(suffix="kg"), name="weight", value=42, attrs={"id": "id_weight"})
    assert soup.find("input")["value"] == "42"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_suffix_number_renders_via_form(renderer):
    """SuffixNumberInput renders correctly inside a FormworkForm."""
    soup = render_form(SuffixNumberForm(), renderer=renderer)
    inp = soup.find("input", attrs={"name": "weight"})
    assert inp is not None
    assert inp.get("type") == "number"


@pytest.mark.integration
def test_suffix_number_form_wraps_in_fieldset(renderer):
    """The field template wraps SuffixNumberInput in a fieldset with a stable id."""
    soup = render_form(SuffixNumberForm(), renderer=renderer)
    assert soup.find("fieldset", id="id_weight_field") is not None


@pytest.mark.integration
def test_suffix_number_form_error_state(renderer):
    """A bound form with errors renders a tooltip containing the error text."""
    form = SuffixNumberForm(data={"weight": ""})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_weight_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_suffix_number_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(SuffixNumberForm(prefix="cfg"), renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-weight"})
    assert inp is not None
    assert inp["id"] == "id_cfg-weight"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_suffix_number_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """SuffixNumberInput produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(SuffixNumberForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SuffixNumberForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_suffix_number_no_suffix_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """A suffix-less SuffixNumberInput stays in parity across engines."""

    class NoSuffixForm(FormworkForm):
        count = forms.IntegerField(widget=SuffixNumberInput())

    soup_dtl = render_form(NoSuffixForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(NoSuffixForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
