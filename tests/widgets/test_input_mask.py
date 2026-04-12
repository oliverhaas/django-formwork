"""Tests for the InputMask widget.

Levels:
    1. unit        — widget object: instantiation, get_context, placeholder generation
    2. unit        — widget rendering: HTML structure, placeholder attribute
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5–8. e2e / screenshot — SKIPPED (no e2e page for InputMask yet)
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import InputMask

from .conftest import assert_html_equivalent, render_form, render_widget


class InputMaskForm(FormworkForm):
    """Form fixture for InputMask integration tests."""

    phone = forms.CharField(widget=InputMask(mask="(###) ###-####"), required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_input_mask_instantiation():
    """InputMask stores the mask parameter."""
    widget = InputMask(mask="(###) ###-####")
    assert widget.mask == "(###) ###-####"


@pytest.mark.unit
def test_input_mask_get_context_has_mask():
    """get_context() exposes the mask value on the widget context."""
    widget = InputMask(mask="(###) ###-####")
    ctx = widget.get_context("phone", None, {"id": "id_phone"})
    assert ctx["widget"]["mask"] == "(###) ###-####"


@pytest.mark.unit
def test_input_mask_auto_placeholder():
    """Placeholder is auto-generated from the mask: # -> _, A -> _, * -> _."""
    widget = InputMask(mask="(###) ###-####")
    ctx = widget.get_context("phone", None, {"id": "id_phone"})
    assert ctx["widget"]["attrs"]["placeholder"] == "(___) ___-____"


@pytest.mark.unit
def test_input_mask_custom_placeholder():
    """An explicit placeholder in attrs overrides the auto-generated one."""
    widget = InputMask(attrs={"placeholder": "Enter phone"}, mask="(###) ###-####")
    ctx = widget.get_context("phone", None, {"id": "id_phone"})
    assert ctx["widget"]["attrs"]["placeholder"] == "Enter phone"


@pytest.mark.unit
def test_input_mask_value_from_datadict():
    """value_from_datadict behaves like standard TextInput."""
    widget = InputMask(mask="(###) ###-####")
    data = QueryDict("phone=1234567890")
    result = widget.value_from_datadict(data, {}, "phone")
    assert result == "1234567890"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_input_mask_renders_input():
    """InputMask renders an <input> element."""
    soup = render_widget(InputMask(mask="(###) ###-####"))
    assert soup.find("input") is not None


@pytest.mark.unit
def test_input_mask_renders_placeholder():
    """Auto-generated placeholder appears on the rendered input element."""
    soup = render_widget(InputMask(mask="(###) ###-####"), attrs={"id": "id_phone"})
    inp = soup.find("input")
    assert inp is not None
    assert inp.get("placeholder") == "(___) ___-____"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_input_mask_renders_via_form(renderer):
    """InputMask renders correctly when used inside a FormworkForm."""
    form = InputMaskForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "phone"})
    assert inp is not None


@pytest.mark.integration
def test_input_mask_form_wraps_in_fieldset(renderer):
    """Field template wraps InputMask in a fieldset with a stable id."""
    form = InputMaskForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_phone_field")
    assert fieldset is not None


@pytest.mark.integration
def test_input_mask_error_state(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = InputMaskForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "phone"})
    assert inp is not None
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_input_mask_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    form = InputMaskForm(prefix="contact")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "contact-phone"})
    assert inp is not None
    assert inp["id"] == "id_contact-phone"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_input_mask_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """InputMask produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(InputMaskForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(InputMaskForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────
#
# No e2e page for InputMask yet — tests would live here once a page
# fixture is added.  Tracked as a gap in e2e coverage.


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Requires an e2e page fixture.  Left as a gap.
