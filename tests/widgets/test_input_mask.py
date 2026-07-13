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
    """Placeholder is auto-generated from the mask: # -> \u00b7, A -> \u00b7, * -> \u00b7."""
    widget = InputMask(mask="(###) ###-####")
    ctx = widget.get_context("phone", None, {"id": "id_phone"})
    assert ctx["widget"]["attrs"]["placeholder"] == "(\u00b7\u00b7\u00b7) \u00b7\u00b7\u00b7-\u00b7\u00b7\u00b7\u00b7"


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
def test_input_mask_renders_wrapper():
    """InputMask renders a div wrapper with hidden + display inputs."""
    soup = render_widget(InputMask(mask="(###) ###-####"), attrs={"id": "id_phone"})
    wrapper = soup.find("div", class_="input-mask")
    assert wrapper is not None
    hidden = wrapper.find("input", attrs={"type": "hidden"})
    assert hidden is not None
    display = wrapper.find("input", class_="input-mask-display")
    assert display is not None


@pytest.mark.unit
def test_input_mask_renders_placeholder():
    """Auto-generated placeholder appears on the display input element."""
    soup = render_widget(InputMask(mask="(###) ###-####"), attrs={"id": "id_phone"})
    display = soup.find("input", class_="input-mask-display")
    assert display is not None
    assert display.get("placeholder") == "(\u00b7\u00b7\u00b7) \u00b7\u00b7\u00b7-\u00b7\u00b7\u00b7\u00b7"


@pytest.mark.unit
def test_input_mask_alpine_x_data():
    """The wrapper div binds to the formworkInputMask Alpine.data component."""
    soup = render_widget(InputMask(mask="(###) ###-####"), attrs={"id": "id_phone"})
    wrapper = soup.find("div", attrs={"x-data": "formworkInputMask"})
    assert wrapper is not None
    assert wrapper["data-mask"] == "(###) ###-####"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_input_mask_renders_via_form(renderer):
    """Field renders an input named after the form field."""
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
    """Bound form with errors adds aria-invalid='true' to the display input."""
    form = InputMaskForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    # The hidden input has name="phone"; the display input has aria-invalid.
    display = soup.find("input", class_="input-mask-display")
    assert display is not None
    assert display.get("aria-invalid") == "true"


@pytest.mark.integration
def test_input_mask_form_prefix(renderer):
    """Form prefix propagates to the hidden input name and the display input id."""
    form = InputMaskForm(prefix="contact")
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", attrs={"name": "contact-phone"})
    assert hidden is not None
    assert not hidden.has_attr("id")
    display = soup.find("input", class_="input-mask-display")
    assert display["id"] == "id_contact-phone"


@pytest.mark.integration
def test_input_mask_label_targets_display_input(renderer):
    """The field label's for attribute points at the visible display input."""
    form = InputMaskForm()
    soup = render_form(form, renderer=renderer)
    label = soup.find("label", class_="fieldset-legend")
    display = soup.find("input", class_="input-mask-display")
    assert label["for"] == display["id"]


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_input_mask_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """InputMask produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(InputMaskForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(InputMaskForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_input_mask_formats_typed_input(new_widgets_page):
    """Smoke: typing digits into the masked phone input applies the pattern."""
    from playwright.sync_api import expect

    display = new_widgets_page.locator("#id_phone_masked_mask input.input-mask-display")
    display.click()
    new_widgets_page.keyboard.type("5551234567")
    expect(display).to_have_value("(555) 123-4567")
    hidden = new_widgets_page.locator("input[name='phone_masked']")
    expect(hidden).to_have_value("(555) 123-4567")


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Needs a page with a required InputMask; both masked fields on /new-widgets/
# are optional.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# No morph test for InputMask yet.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# No InputMask screenshot baselines yet.
