"""Tests for the OTPInput widget.

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, attributes
    3. integration — form integration: field template, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — SKIPPED (no e2e page for OTPInput yet)
    6. e2e         — SKIPPED (see above)
    7. e2e         — SKIPPED (see above)
    8. screenshot  — SKIPPED (no e2e page for OTPInput yet)
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import OTPInput

from .conftest import assert_html_equivalent, render_form, render_widget


class OTPForm(FormworkForm):
    """Form fixture for OTPInput integration tests."""

    code = forms.CharField(widget=OTPInput(length=6), required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_otp_input_instantiation():
    """OTPInput default length is 6."""
    widget = OTPInput()
    assert widget.length == 6


@pytest.mark.unit
def test_otp_input_custom_length():
    """OTPInput(length=4) stores length=4."""
    widget = OTPInput(length=4)
    assert widget.length == 4


@pytest.mark.unit
def test_otp_input_get_context():
    """get_context() exposes length, digits, and initial_digits on the widget context."""
    widget = OTPInput(length=6)
    ctx = widget.get_context("code", None, {"id": "id_code"})
    assert ctx["widget"]["length"] == 6
    assert ctx["widget"]["digits"] == [0, 1, 2, 3, 4, 5]
    assert ctx["widget"]["initial_digits"] == ["", "", "", "", "", ""]


@pytest.mark.unit
def test_otp_input_get_context_with_value():
    """Pre-existing value is split into individual digits."""
    widget = OTPInput(length=6)
    ctx = widget.get_context("code", "123456", {"id": "id_code"})
    assert ctx["widget"]["initial_digits"] == ["1", "2", "3", "4", "5", "6"]


@pytest.mark.unit
def test_otp_input_get_context_with_none():
    """get_context() tolerates None value — all digits are empty strings."""
    widget = OTPInput(length=4)
    ctx = widget.get_context("code", None, {"id": "id_code"})
    assert ctx["widget"]["initial_digits"] == ["", "", "", ""]


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_otp_input_renders_hidden_input():
    """OTPInput renders a hidden input that holds the combined value."""
    soup = render_widget(OTPInput(length=4), name="code", attrs={"id": "id_code"})
    hidden = soup.find("input", attrs={"type": "hidden", "name": "code"})
    assert hidden is not None


@pytest.mark.unit
def test_otp_input_renders_digit_inputs():
    """OTPInput renders exactly N visible single-character inputs."""
    length = 4
    soup = render_widget(OTPInput(length=length), name="code", attrs={"id": "id_code"})
    # Visible digit inputs have type="text" and maxlength="1".
    digit_inputs = soup.find_all("input", attrs={"type": "text", "maxlength": "1"})
    assert len(digit_inputs) == length


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_otp_input_renders_via_form(renderer):
    """OTPInput renders correctly when used inside a FormworkForm."""
    form = OTPForm()
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", attrs={"type": "hidden", "name": "code"})
    assert hidden is not None


@pytest.mark.integration
def test_otp_input_form_wraps_in_fieldset(renderer):
    """Field template wraps OTPInput in a fieldset with a stable id."""
    form = OTPForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_code_field")
    assert fieldset is not None


@pytest.mark.integration
def test_otp_input_form_prefix(renderer):
    """Form prefix propagates to the hidden input's name and id."""
    form = OTPForm(prefix="auth")
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", attrs={"type": "hidden", "name": "auth-code"})
    assert hidden is not None
    assert hidden["id"] == "id_auth-code"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_otp_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """OTPInput produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(OTPForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(OTPForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────
#
# No e2e page exists for OTPInput yet.  Tests to add once a page fixture
# is available: renders on page, typing into digit inputs advances focus,
# pasting fills all digits.


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# No e2e page exists for OTPInput yet.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# No e2e page exists for OTPInput yet.  Key case to cover once available:
# entered digits preserved across htmx morph.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# No e2e page exists for OTPInput yet.  Planned screenshots:
# otp-input-empty.png, otp-input-filled.png.
