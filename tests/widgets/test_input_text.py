"""Tests for the InputText widget.

Levels:
    1. unit        — widget object: instantiation, floating flag, input_type
    2. unit        — widget rendering: floating vs plain HTML structure
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import InputText

from .conftest import assert_html_equivalent, render_form, render_widget


class InputTextForm(FormworkForm):
    """Form fixture for InputText integration tests."""

    email = forms.EmailField(
        widget=InputText(
            floating=True,
            input_type="email",
            attrs={"placeholder": "Email address"},
        ),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_input_text_instantiation():
    """InputText exposes the expected template_name."""
    widget = InputText()
    assert widget.template_name == "formwork/widgets/input_text.html"


@pytest.mark.unit
def test_input_text_inherits_text_input():
    """InputText is a subclass of Django's TextInput."""
    assert isinstance(InputText(), forms.TextInput)


@pytest.mark.unit
def test_input_text_floating_defaults_false():
    """Without opting in, the widget is a plain text input."""
    assert InputText().floating is False


@pytest.mark.unit
def test_input_text_floating_flag_stored():
    """floating=True is retained on the widget."""
    assert InputText(floating=True).floating is True


@pytest.mark.unit
def test_input_text_input_type_default_text():
    """The default input type is 'text'."""
    ctx = InputText().get_context("field", None, {})
    assert ctx["widget"]["type"] == "text"


@pytest.mark.unit
def test_input_text_input_type_custom():
    """A custom input_type flows into the widget context."""
    ctx = InputText(input_type="email").get_context("field", None, {})
    assert ctx["widget"]["type"] == "email"


@pytest.mark.unit
def test_input_text_get_context_exposes_floating():
    """get_context surfaces the floating flag for the template."""
    ctx = InputText(floating=True).get_context("field", None, {})
    assert ctx["widget"]["floating"] is True


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_input_text_plain_renders_bare_input():
    """Without floating, the widget renders a bare input and no floating label."""
    soup = render_widget(InputText(), name="name", attrs={"id": "id_name"})
    assert soup.find("label", class_="floating-label") is None
    inp = soup.find("input")
    assert inp is not None
    assert inp["type"] == "text"


@pytest.mark.unit
def test_input_text_floating_wraps_input_in_label():
    """floating=True wraps the input in a <label class='floating-label'>."""
    widget = InputText(floating=True, attrs={"placeholder": "Email"})
    soup = render_widget(widget, name="email", attrs={"id": "id_email"})
    label = soup.find("label", class_="floating-label")
    assert label is not None
    assert label.find("input") is not None


@pytest.mark.unit
def test_input_text_floating_span_is_placeholder():
    """The floating label span carries the placeholder text."""
    widget = InputText(floating=True, attrs={"placeholder": "Email"})
    soup = render_widget(widget, name="email", attrs={"id": "id_email"})
    span = soup.find("label", class_="floating-label").find("span")
    assert span.get_text(strip=True) == "Email"


@pytest.mark.unit
def test_input_text_custom_input_type_rendered():
    """The custom input_type is reflected in the rendered type attribute."""
    soup = render_widget(InputText(input_type="url"), name="site", attrs={"id": "id_site"})
    assert soup.find("input")["type"] == "url"


@pytest.mark.unit
def test_input_text_value_rendered():
    """A bound value is rendered in the value attribute."""
    soup = render_widget(InputText(), name="name", value="Ada", attrs={"id": "id_name"})
    assert soup.find("input")["value"] == "Ada"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_input_text_renders_via_form(renderer):
    """InputText renders correctly inside a FormworkForm."""
    soup = render_form(InputTextForm(), renderer=renderer)
    inp = soup.find("input", attrs={"name": "email"})
    assert inp is not None
    assert inp.get("type") == "email"


@pytest.mark.integration
def test_input_text_form_wraps_in_fieldset(renderer):
    """The field template wraps InputText in a fieldset with a stable id."""
    soup = render_form(InputTextForm(), renderer=renderer)
    assert soup.find("fieldset", id="id_email_field") is not None


@pytest.mark.integration
def test_input_text_form_error_state(renderer):
    """A bound form with errors renders a tooltip containing the error text."""
    form = InputTextForm(data={"email": ""})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_email_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_input_text_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(InputTextForm(prefix="cfg"), renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-email"})
    assert inp is not None
    assert inp["id"] == "id_cfg-email"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_input_text_floating_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Floating InputText produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(InputTextForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(InputTextForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_input_text_plain_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Plain (non-floating) InputText produces equivalent HTML via DTL and Jinja2."""

    class PlainForm(FormworkForm):
        name = forms.CharField(widget=InputText(attrs={"placeholder": "Name"}))

    soup_dtl = render_form(PlainForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(PlainForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
