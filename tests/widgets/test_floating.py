"""Tests for the floating-label widgets (TextInput/Select/Textarea)."""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Select, TextInput, Textarea

from .conftest import assert_html_equivalent, render_form, render_widget

WRAPPER_TEMPLATE = "formwork/widgets/floating_label.html"


class FloatingForm(FormworkForm):
    """Form fixture exercising all three floating widgets."""

    nickname = forms.CharField(
        required=False,
        widget=TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
    )
    role = forms.ChoiceField(
        required=False,
        choices=[("", ""), ("admin", "Admin"), ("user", "User")],
        widget=Select(attrs={"placeholder": "Role"}, floating_label=True),
    )
    note = forms.CharField(
        required=False,
        widget=Textarea(attrs={"placeholder": "Note"}, floating_label=True),
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_floating_label_defaults_off():
    """floating_label defaults to False and leaves template_name untouched."""
    widget = TextInput()
    assert widget.floating_label is False
    assert widget.template_name == forms.TextInput.template_name


@pytest.mark.unit
def test_floating_label_swaps_template():
    """floating_label=True points rendering at the wrapper template."""
    widget = TextInput(floating_label=True)
    assert widget.floating_label is True
    assert widget.template_name == WRAPPER_TEMPLATE
    assert widget._inner_template_name == forms.TextInput.template_name


@pytest.mark.unit
@pytest.mark.parametrize("cls", [TextInput, Select, Textarea])
def test_floating_widgets_accept_flag(cls):
    """Every floating widget accepts the flag alongside stock constructor args."""
    widget = cls(attrs={"placeholder": "X"}, floating_label=True)
    assert widget.floating_label is True
    assert widget.attrs["placeholder"] == "X"
    assert widget.template_name == WRAPPER_TEMPLATE


@pytest.mark.unit
def test_select_forwards_choices():
    """Select still forwards choices through the mixin's *args/**kwargs."""
    widget = Select(choices=[("a", "A")], floating_label=True)
    assert list(widget.choices) == [("a", "A")]


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_floating_render_wraps_input():
    """Floating render wraps the <input> in <label class="floating-label">."""
    soup = render_widget(
        TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
        name="nickname",
        attrs={"id": "id_nickname"},
    )
    label = soup.find("label", class_="floating-label")
    assert label is not None
    assert label.find("input") is not None


@pytest.mark.unit
def test_floating_span_equals_placeholder():
    """The floating <span> text is the placeholder."""
    soup = render_widget(
        TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
        name="nickname",
        attrs={"id": "id_nickname"},
    )
    span = soup.find("label", class_="floating-label").find("span")
    assert span.get_text(strip=True) == "Nickname"


@pytest.mark.unit
def test_floating_input_keeps_placeholder_attr():
    """A text <input> keeps its native placeholder attribute as well."""
    soup = render_widget(
        TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
        name="nickname",
        attrs={"id": "id_nickname"},
    )
    assert soup.find("input").get("placeholder") == "Nickname"


@pytest.mark.unit
def test_textarea_floating_wraps():
    """Textarea floating render wraps a <textarea>, span carries the text."""
    soup = render_widget(
        Textarea(attrs={"placeholder": "Note"}, floating_label=True),
        name="note",
        attrs={"id": "id_note"},
    )
    label = soup.find("label", class_="floating-label")
    assert label is not None
    assert label.find("textarea") is not None
    assert label.find("span").get_text(strip=True) == "Note"


@pytest.mark.unit
def test_select_floating_wraps_and_strips_placeholder():
    """Select floating render wraps a <select>, keeps the span text, and drops
    the placeholder attribute (invalid on <select>)."""
    soup = render_widget(
        Select(attrs={"placeholder": "Role"}, choices=[("", ""), ("a", "A")], floating_label=True),
        name="role",
        attrs={"id": "id_role"},
    )
    label = soup.find("label", class_="floating-label")
    assert label is not None
    select = label.find("select")
    assert select is not None
    assert select.get("placeholder") is None
    assert label.find("span").get_text(strip=True) == "Role"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("floating_cls", "stock_cls"),
    [(TextInput, forms.TextInput), (Textarea, forms.Textarea), (Select, forms.Select)],
)
def test_non_floating_identical_to_stock(floating_cls, stock_cls):
    """floating_label=False renders byte-for-byte identically to Django's widget."""
    kwargs = {"choices": [("a", "A")]} if floating_cls is Select else {}
    ours = floating_cls(attrs={"placeholder": "X"}, **kwargs)
    stock = stock_cls(attrs={"placeholder": "X"}, **kwargs)
    assert ours.render("f", None, attrs={"id": "id_f"}) == stock.render("f", None, attrs={"id": "id_f"})


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_floating_renders_via_form(renderer):
    """All three floating widgets render their wrapper inside a FormworkForm."""
    soup = render_form(FloatingForm(), renderer=renderer)
    assert len(soup.find_all("label", class_="floating-label")) == 3


@pytest.mark.integration
def test_floating_control_names_present(renderer):
    """The real controls render with their field names inside the wrappers."""
    soup = render_form(FloatingForm(), renderer=renderer)
    assert soup.find("input", attrs={"name": "nickname"}) is not None
    assert soup.find("select", attrs={"name": "role"}) is not None
    assert soup.find("textarea", attrs={"name": "note"}) is not None


@pytest.mark.integration
def test_floating_wraps_control_in_form(renderer):
    """Inside the form the control sits within the floating-label wrapper."""
    soup = render_form(FloatingForm(), renderer=renderer)
    label = soup.find("label", class_="floating-label")
    assert label.find("input", attrs={"name": "nickname"}) is not None


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_floating_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Floating widgets produce equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(FloatingForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(FloatingForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
