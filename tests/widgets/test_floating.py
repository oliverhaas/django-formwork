"""Tests for the floating-label widgets (TextInput/Textarea, Select/SelectMultiple)."""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Select, SelectMultiple, Textarea, TextInput

from .conftest import render_form, render_widget

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
        widget=Select(attrs={"placeholder": "Role"}, floating=True),
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
@pytest.mark.parametrize("cls", [TextInput, Textarea])
def test_floating_widgets_accept_flag(cls):
    """Every floating widget accepts the flag alongside stock constructor args."""
    widget = cls(attrs={"placeholder": "X"}, floating_label=True)
    assert widget.floating_label is True
    assert widget.attrs["placeholder"] == "X"
    assert widget.template_name == WRAPPER_TEMPLATE


@pytest.mark.unit
@pytest.mark.parametrize("cls", [Select, SelectMultiple])
def test_floating_select_requires_placeholder(cls):
    """The placeholder is the floating label's text, so a floating select needs one."""
    with pytest.raises(ImproperlyConfigured):
        cls(choices=[("a", "A")], floating=True).render("f", None, attrs={"id": "id_f"})


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
    """floating_label=False renders byte-for-byte identically to Django's widget."""
    ours = floating_cls(attrs={"placeholder": "X"})
    stock = stock_cls(attrs={"placeholder": "X"})
    assert ours.render("f", None, attrs={"id": "id_f"}) == stock.render("f", None, attrs={"id": "id_f"})


# ─── Level 3: Form integration ───────────────────────────────────────────


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


# ─── Level 5+: E2e, morph, screenshot ────────────────────────────────────
#
# No e2e page renders Floating widgets yet, so the e2e, morph-resilience,
# and screenshot levels are missing entirely.
