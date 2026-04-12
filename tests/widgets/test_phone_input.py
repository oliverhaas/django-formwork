"""PhoneInput widget tests: unit → integration → e2e → screenshot.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_phone_input.py                 # everything
    uv run pytest tests/widgets/test_phone_input.py -m unit         # fast only
    uv run pytest tests/widgets/test_phone_input.py -m "not e2e"    # skip browser

Levels:
    1. unit        — widget object: instantiation, decompress, value_from_datadict
    2. unit        — widget rendering: HTML structure, select + text input
    3. integration — form integration: fieldset, error state, morph IDs
    4. integration — Jinja2/DTL parity
    5. e2e         — user interaction (no dedicated page yet — see comment)
    6. e2e         — error flow (no dedicated page yet — see comment)
    7. e2e         — morph resilience (no dedicated page yet — see comment)
    8. screenshot  — visual states (no dedicated page yet — see comment)
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import PhoneInput

from .conftest import assert_html_equivalent, render_form, render_widget


class PhoneForm(FormworkForm):
    """Form fixture for PhoneInput integration tests."""

    phone = forms.CharField(widget=PhoneInput, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_phone_input_instantiation():
    """PhoneInput is a MultiWidget with exactly 2 sub-widgets."""
    widget = PhoneInput()
    assert len(widget.widgets) == 2


@pytest.mark.unit
def test_phone_input_default_code():
    """default_code defaults to '+1'."""
    widget = PhoneInput()
    assert widget.default_code == "+1"


@pytest.mark.unit
def test_phone_input_custom_default_code():
    """A custom default_code is stored on the widget."""
    widget = PhoneInput(default_code="+49")
    assert widget.default_code == "+49"


@pytest.mark.unit
def test_phone_input_first_subwidget_is_select():
    """The first sub-widget is a Select (country code prefix)."""
    widget = PhoneInput()
    assert isinstance(widget.widgets[0], forms.Select)


@pytest.mark.unit
def test_phone_input_second_subwidget_is_text_input():
    """The second sub-widget is a TextInput (phone number)."""
    widget = PhoneInput()
    assert isinstance(widget.widgets[1], forms.TextInput)


@pytest.mark.unit
def test_phone_input_decompress_full():
    """decompress splits '+44 1234567' into ['+44', '1234567']."""
    widget = PhoneInput()
    result = widget.decompress("+44 1234567")
    assert result == ["+44", "1234567"]


@pytest.mark.unit
def test_phone_input_decompress_number_only():
    """decompress falls back to default_code when no space-separated prefix."""
    widget = PhoneInput()
    result = widget.decompress("1234567")
    assert result == ["+1", "1234567"]


@pytest.mark.unit
def test_phone_input_decompress_none():
    """decompress(None) returns [default_code, '']."""
    widget = PhoneInput()
    result = widget.decompress(None)
    assert result == ["+1", ""]


@pytest.mark.unit
def test_phone_input_decompress_empty_string():
    """decompress('') returns [default_code, '']."""
    widget = PhoneInput()
    result = widget.decompress("")
    assert result == ["+1", ""]


@pytest.mark.unit
def test_phone_input_value_from_datadict():
    """value_from_datadict combines prefix and number into '{prefix} {number}'."""
    data = QueryDict("phone_0=%2B44&phone_1=1234567")  # %2B is +
    widget = PhoneInput()
    result = widget.value_from_datadict(data, {}, "phone")
    assert result == "+44 1234567"


@pytest.mark.unit
def test_phone_input_value_from_datadict_empty_number():
    """value_from_datadict returns '' when the number part is empty."""
    data = QueryDict("phone_0=%2B1&phone_1=")
    widget = PhoneInput()
    result = widget.value_from_datadict(data, {}, "phone")
    assert result == ""


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_phone_input_renders_non_empty_html():
    """widget.render() produces non-empty output."""
    soup = render_widget(PhoneInput(), attrs={"id": "id_phone"})
    assert soup.find("div") is not None


@pytest.mark.unit
def test_phone_input_renders_join_wrapper():
    """The widget wraps sub-widgets in a .phone-input.join div."""
    soup = render_widget(PhoneInput(), attrs={"id": "id_phone"})
    wrapper = soup.find("div", class_="phone-input")
    assert wrapper is not None
    assert "join" in wrapper.get("class", [])


@pytest.mark.unit
def test_phone_input_wrapper_has_stable_id():
    """The outer wrapper gets an id derived from the widget id."""
    soup = render_widget(PhoneInput(), attrs={"id": "id_phone"})
    wrapper = soup.find("div", class_="phone-input")
    assert wrapper.get("id") == "id_phone_phone"


@pytest.mark.unit
def test_phone_input_prefix_subwidget_renders_select():
    """The first sub-widget (prefix select) renders a <select> with options."""
    from bs4 import BeautifulSoup

    widget = PhoneInput()
    html = widget.widgets[0].render("phone_0", "+1")
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select")
    assert select is not None
    options = select.find_all("option")
    assert len(options) > 10


@pytest.mark.unit
def test_phone_input_prefix_subwidget_has_us_option():
    """The prefix select contains a '+1' option."""
    from bs4 import BeautifulSoup

    widget = PhoneInput()
    html = widget.widgets[0].render("phone_0", "+1")
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select")
    option_values = [opt.get("value", "") for opt in select.find_all("option")]
    assert "+1" in option_values


@pytest.mark.unit
def test_phone_input_number_subwidget_renders_tel_input():
    """The second sub-widget (number input) renders an <input type='tel'>."""
    from bs4 import BeautifulSoup

    widget = PhoneInput()
    html = widget.widgets[1].render("phone_1", "")
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", {"type": "tel"})
    assert inp is not None


@pytest.mark.unit
def test_phone_input_prefix_subwidget_selects_matching_option():
    """The prefix select marks the current prefix as selected."""
    from bs4 import BeautifulSoup

    widget = PhoneInput()
    html = widget.widgets[0].render("phone_0", "+44")
    soup = BeautifulSoup(html, "html.parser")
    selected = soup.find("option", selected=True)
    assert selected is not None
    assert selected.get("value") == "+44"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_phone_input_renders_via_form(renderer):
    """PhoneInput renders correctly when used inside a FormworkForm."""
    form = PhoneForm()
    soup = render_form(form, renderer=renderer)
    wrapper = soup.find("div", class_="phone-input")
    assert wrapper is not None


@pytest.mark.integration
def test_phone_input_form_wraps_in_fieldset(renderer):
    """Field template wraps the PhoneInput in a fieldset with a stable id."""
    form = PhoneForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_phone_field")
    assert fieldset is not None


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_phone_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """PhoneInput produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(PhoneForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(PhoneForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────
#
# PhoneInput has no dedicated e2e page yet.  Tests will be added once a
# /phone/ page is wired up — tracked under the e2e coverage work.


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Same as Level 5 — no dedicated page yet.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# Same as Level 5 — no dedicated page yet.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Same as Level 5 — no dedicated page yet.
