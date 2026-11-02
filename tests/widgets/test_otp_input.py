from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import OTPInput

from .conftest import render_form, render_widget


class OTPForm(FormworkForm):
    """Form fixture for OTPInput integration tests."""

    code = forms.CharField(widget=OTPInput(length=6), required=True)


@pytest.mark.unit
@pytest.mark.parametrize("length", [4, 6])
def test_otp_input_length_sets_the_limits_and_the_boxes(length):
    """``length`` sets ``maxlength``, the digit pattern and one box per digit."""
    soup = render_widget(OTPInput(length=length), name="code")
    inp = soup.select_one("input")
    assert inp["maxlength"] == str(length)
    assert inp["pattern"] == f"[0-9]{{{length}}}"
    assert len(soup.select("label.otp > span")) == length


@pytest.mark.unit
def test_otp_input_is_one_input_for_autofill():
    """One text input with the id and the one-time-code hints keeps SMS autofill and paste working."""
    soup = render_widget(OTPInput(), name="code", attrs={"id": "id_code"})
    inputs = soup.select("input")
    assert len(inputs) == 1
    assert inputs[0]["id"] == "id_code"
    assert inputs[0]["type"] == "text"
    assert inputs[0]["inputmode"] == "numeric"
    assert inputs[0]["autocomplete"] == "one-time-code"


@pytest.mark.unit
def test_otp_input_caller_hints_win():
    """A caller's ``inputmode`` and ``autocomplete`` replace the defaults."""
    soup = render_widget(OTPInput(attrs={"inputmode": "text", "autocomplete": "off"}), name="code")
    inp = soup.select_one("input")
    assert inp["inputmode"] == "text"
    assert inp["autocomplete"] == "off"


@pytest.mark.unit
def test_otp_input_length_overrides_the_field_max_length():
    """The widget's ``length`` decides ``maxlength``, not the field's."""

    class _Form(FormworkForm):
        code = forms.CharField(max_length=10, widget=OTPInput(length=4))

    inp = render_form(_Form()).find("input", attrs={"name": "code"})
    assert inp["maxlength"] == "4"


@pytest.mark.unit
@pytest.mark.parametrize(("value", "expected"), [("123456", "123456"), (42, "42")])
def test_otp_input_renders_the_value(value, expected):
    """The value is redisplayed, so a failed submit keeps the typed code."""
    soup = render_widget(OTPInput(), name="code", value=value)
    assert soup.select_one("input")["value"] == expected


@pytest.mark.unit
def test_otp_input_has_no_script_and_no_component():
    """The boxes are CSS only: no Alpine component and no <script>."""
    soup = render_widget(OTPInput(), name="code")
    assert soup.select_one("[x-data]") is None
    assert soup.select_one("script") is None


@pytest.mark.integration
def test_otp_input_label_targets_the_input(renderer):
    """The field label points at the one input."""
    soup = render_form(OTPForm(), renderer=renderer)
    assert soup.find("label", id="id_code_label")["for"] == "id_code"
    assert soup.find(id="id_code")["name"] == "code"


@pytest.mark.integration
def test_otp_input_escapes_a_hostile_value(renderer):
    """SECURITY: a hostile redisplayed value stays an escaped attribute."""
    payload = "1'); alert(1); ('"
    form = OTPForm(data={"code": payload})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", attrs={"name": "code"})["value"] == payload
    assert soup.select_one("script") is None


@pytest.mark.integration
def test_otp_input_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(OTPForm(prefix="auth"), renderer=renderer)
    assert soup.find("input", attrs={"name": "auth-code"})["id"] == "id_auth-code"


@pytest.mark.e2e
def test_otp_input_typing_fills_the_one_input(new_widgets_page):
    """Typing a code fills the input; the browser blocks a seventh digit."""
    from playwright.sync_api import expect

    inp = new_widgets_page.locator("input[name='otp_code']")
    inp.press_sequentially("1234567")
    expect(inp).to_have_value("123456")
