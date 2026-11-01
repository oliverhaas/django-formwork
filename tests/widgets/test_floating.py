"""Tests for the floating-label widgets (TextInput/Textarea, Select/SelectMultiple)."""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured

from django_formwork.forms import FormworkForm
from django_formwork.widgets import PasswordInput, Select, SelectMultiple, Textarea, TextInput

from .conftest import render_form, render_widget


class FloatingForm(FormworkForm):
    """Form fixture exercising all three floating widgets."""

    nickname = forms.CharField(
        required=False,
        widget=TextInput(attrs={"placeholder": "Nickname"}, floating=True),
    )
    role = forms.ChoiceField(
        required=False,
        choices=[("", ""), ("admin", "Admin"), ("user", "User")],
        widget=Select(attrs={"placeholder": "Role"}, floating=True),
    )
    note = forms.CharField(
        required=False,
        widget=Textarea(attrs={"placeholder": "Note"}, floating=True),
    )


@pytest.mark.unit
@pytest.mark.parametrize("cls", [TextInput, Textarea])
def test_floating_text_requires_placeholder(cls):
    """The placeholder is the floating label's text, so a floating text widget needs one."""
    with pytest.raises(ImproperlyConfigured):
        cls(floating=True).render("f", None, attrs={"id": "id_f"})


@pytest.mark.unit
@pytest.mark.parametrize("cls", [Select, SelectMultiple])
def test_floating_select_requires_placeholder(cls):
    """The placeholder is the floating label's text, so a floating select needs one."""
    with pytest.raises(ImproperlyConfigured):
        cls(choices=[("a", "A")], floating=True).render("f", None, attrs={"id": "id_f"})


@pytest.mark.unit
def test_floating_render_wraps_input():
    """Floating render wraps the <input> in <label class="floating-label">."""
    soup = render_widget(
        TextInput(attrs={"placeholder": "Nickname"}, floating=True),
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
        TextInput(attrs={"placeholder": "Nickname"}, floating=True),
        name="nickname",
        attrs={"id": "id_nickname"},
    )
    span = soup.find("label", class_="floating-label").find("span")
    assert span.get_text(strip=True) == "Nickname"


@pytest.mark.unit
def test_floating_input_keeps_placeholder_attr():
    """A text <input> keeps its native placeholder attribute as well."""
    soup = render_widget(
        TextInput(attrs={"placeholder": "Nickname"}, floating=True),
        name="nickname",
        attrs={"id": "id_nickname"},
    )
    assert soup.find("input").get("placeholder") == "Nickname"


@pytest.mark.unit
def test_textarea_floating_wraps():
    """Textarea floating render wraps a <textarea>, span carries the text."""
    soup = render_widget(
        Textarea(attrs={"placeholder": "Note"}, floating=True),
        name="note",
        attrs={"id": "id_note"},
    )
    label = soup.find("label", class_="floating-label")
    assert label is not None
    assert label.find("textarea") is not None
    assert label.find("span").get_text(strip=True) == "Note"


@pytest.mark.unit
@pytest.mark.parametrize("cls", [Select, SelectMultiple])
def test_select_floating_label_names_the_trigger(cls):
    """The floating label names the summary trigger, and the empty trigger shows no placeholder."""
    field_cls = forms.MultipleChoiceField if cls is SelectMultiple else forms.ChoiceField

    class _Form(FormworkForm):
        fruit = field_cls(
            label="",
            required=False,
            choices=[("a", "Apple"), ("b", "Banana")],
            widget=cls(attrs={"placeholder": "Fruit"}, floating=True),
        )

    soup = render_form(_Form())
    wrapper = soup.select_one(".floating-label.formwork-floating-select")
    summary = wrapper.select_one("details > summary")
    label_id, own_id = str(summary["aria-labelledby"]).split()
    assert own_id == summary["id"] == "id_fruit"
    assert soup.find(id=label_id).get_text(strip=True) == "Fruit"
    assert "Fruit" not in summary.get_text()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("floating_cls", "stock_cls"),
    [(TextInput, forms.TextInput), (Textarea, forms.Textarea)],
)
def test_non_floating_identical_to_stock(floating_cls, stock_cls):
    """Without ``floating`` the widgets render byte-for-byte like Django's own."""
    ours = floating_cls(attrs={"placeholder": "X"})
    stock = stock_cls(attrs={"placeholder": "X"})
    assert ours.render("f", None, attrs={"id": "id_f"}) == stock.render("f", None, attrs={"id": "id_f"})


@pytest.mark.integration
def test_floating_renders_via_form(renderer):
    """All three floating widgets render their wrapper inside a FormworkForm."""
    soup = render_form(FloatingForm(), renderer=renderer)
    assert len(soup.find_all(class_="floating-label")) == 3


@pytest.mark.integration
def test_floating_control_names_present(renderer):
    """The real controls render with their field names inside the wrappers."""
    soup = render_form(FloatingForm(), renderer=renderer)
    assert soup.find("input", attrs={"name": "nickname"}) is not None
    assert soup.select_one(".floating-label input[type=hidden][name=role]") is not None
    assert soup.find("textarea", attrs={"name": "note"}) is not None


@pytest.mark.integration
def test_floating_wraps_control_in_form(renderer):
    """Inside the form the control sits within the floating-label wrapper."""
    soup = render_form(FloatingForm(), renderer=renderer)
    label = soup.find("label", class_="floating-label")
    assert label.find("input", attrs={"name": "nickname"}) is not None


@pytest.mark.unit
def test_floating_password_input_keeps_the_reveal_toggle():
    """The wrapper includes the widget's own template, so a templated widget floats unchanged."""
    soup = render_widget(PasswordInput(attrs={"placeholder": "Password"}, floating=True), name="pw")
    label = soup.find("label", class_="floating-label")
    assert label.select_one('[x-data="formworkPasswordInput"] button') is not None


@pytest.mark.unit
def test_floating_pattern_hint_sits_outside_the_label():
    """The pattern hint follows the floating label, so the label keeps only the control and its text."""

    class CodeInput(TextInput):
        pattern_hint = "Use three digits."

    soup = render_widget(CodeInput(attrs={"placeholder": "Code", "pattern": "[0-9]{3}"}, floating=True), name="code")
    group = soup.select_one("div.group\\/pattern")
    label = group.find("label", class_="floating-label", recursive=False)
    assert label.find("span").get_text() == "Code"
    assert "Use three digits." not in label.get_text()
    assert group.select_one("[role=alert]").get_text() == "Use three digits."
