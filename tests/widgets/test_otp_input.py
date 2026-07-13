"""Tests for the OTPInput widget.

Levels:
    1. unit (widget object: instantiation, get_context, value_from_datadict)
    2. unit (widget rendering: HTML structure, attributes)
    3. integration (form integration: field template, prefix)
    4. integration (Jinja2/DTL parity: identical HTML across engines)
    5. e2e (smoke: typing advances focus, hidden input collects value)
    6. e2e: SKIPPED (gap; smoke coverage only)
    7. e2e: SKIPPED (see above)
    8. screenshot: SKIPPED (no baseline for OTPInput yet)
"""

from __future__ import annotations

import json

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
    """get_context() tolerates None value. All digits are empty strings."""
    widget = OTPInput(length=4)
    ctx = widget.get_context("code", None, {"id": "id_code"})
    assert ctx["widget"]["initial_digits"] == ["", "", "", ""]


@pytest.mark.unit
def test_otp_input_get_context_initial_digits_json():
    """initial_digits_json is the JSON-encoded twin of initial_digits."""
    widget = OTPInput(length=4)
    ctx = widget.get_context("code", "12", {"id": "id_code"})
    assert json.loads(ctx["widget"]["initial_digits_json"]) == ["1", "2", "", ""]


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


@pytest.mark.unit
def test_otp_input_alpine_x_data():
    """The wrapper div binds to the formworkOtpInput Alpine.data component."""
    soup = render_widget(OTPInput(length=4), name="code", value="12", attrs={"id": "id_code"})
    wrapper = soup.find("div", attrs={"x-data": "formworkOtpInput"})
    assert wrapper is not None
    assert json.loads(wrapper["data-digits"]) == ["1", "2", "", ""]


@pytest.mark.unit
def test_otp_input_digit_boxes_have_aria_labels():
    """Each digit box carries a positional aria-label for assistive tech."""
    soup = render_widget(OTPInput(length=4), name="code", attrs={"id": "id_code"})
    labels = [inp.get("aria-label") for inp in soup.find_all("input", class_="otp-digit")]
    assert labels == [f"Digit {i} of 4" for i in range(1, 5)]


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


@pytest.mark.integration
def test_otp_input_escapes_digits_in_x_data(renderer):
    """SECURITY: redisplayed value characters never land in an executable context."""
    # Regression: a quote character in the submitted value broke out of its
    # '...' array element in the inline x-data.  The digits now ride in an
    # autoescaped data-digits JSON attribute read via dataset (never evaluated
    # as JS), and x-data holds only the fixed component name.
    form = OTPForm(data={"code": "1'2<3\\"})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", class_="otp-input")
    assert wrapper["x-data"] == "formworkOtpInput"
    # BeautifulSoup entity-decodes: exact JSON round-trip proves lossless escaping.
    assert json.loads(wrapper["data-digits"]) == ["1", "'", "2", "<", "3", "\\"]


@pytest.mark.integration
def test_otp_input_renders_with_int_initial(renderer):
    """Non-str initial values are coerced to strings instead of crashing the render."""
    # Regression: int initial raised TypeError in get_context on first render.
    form = OTPForm(initial={"code": 123456})
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", attrs={"x-data": "formworkOtpInput"})
    assert json.loads(wrapper["data-digits"]) == ["1", "2", "3", "4", "5", "6"]


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_otp_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """OTPInput produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(OTPForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(OTPForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_otp_input_typing_auto_advances(new_widgets_page):
    """Smoke: typing a digit advances focus; the hidden input collects the value."""
    from playwright.sync_api import expect

    boxes = new_widgets_page.locator("#id_otp_code_otp .otp-digit")
    boxes.nth(0).click()
    new_widgets_page.keyboard.type("1")
    expect(boxes.nth(1)).to_be_focused()
    new_widgets_page.keyboard.type("23456")
    hidden = new_widgets_page.locator("input[name='otp_code']")
    expect(hidden).to_have_value("123456")


def _paste_into_first_box(page, text):
    page.evaluate(
        """(text) => {
            const box = document.querySelector('#id_otp_code_otp .otp-digit');
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            box.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
        }""",
        text,
    )


@pytest.mark.e2e
def test_otp_input_paste_fills_digits_and_fires_input(new_widgets_page):
    """Pasting a code fills the boxes, updates the hidden input, and fires input."""
    from playwright.sync_api import expect

    new_widgets_page.evaluate("""() => {
        window._otpInputEvents = 0;
        document.querySelector("input[name='otp_code']")
            .addEventListener('input', () => window._otpInputEvents++);
    }""")
    new_widgets_page.locator("#id_otp_code_otp .otp-digit").nth(0).click()
    _paste_into_first_box(new_widgets_page, "987654")
    hidden = new_widgets_page.locator("input[name='otp_code']")
    expect(hidden).to_have_value("987654")
    assert new_widgets_page.evaluate("() => window._otpInputEvents") >= 1


@pytest.mark.e2e
def test_otp_input_paste_filters_non_digits(new_widgets_page):
    """Pasted text keeps only digits, matching the numeric input boxes."""
    from playwright.sync_api import expect

    new_widgets_page.locator("#id_otp_code_otp .otp-digit").nth(0).click()
    _paste_into_first_box(new_widgets_page, "12-34 ab5")
    hidden = new_widgets_page.locator("input[name='otp_code']")
    expect(hidden).to_have_value("12345")


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Requires a dedicated error-flow page.  Left as a gap.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# No e2e page exists for OTPInput yet.  Key case to cover once available:
# entered digits preserved across htmx morph.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# No e2e page exists for OTPInput yet.  Planned screenshots:
# otp-input-empty.png, otp-input-filled.png.
