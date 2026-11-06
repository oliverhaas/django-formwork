from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import TextInput

from .conftest import render_form, render_widget


class ZipInput(TextInput):
    pattern_hint = "Five digits, like 10115."


class ZipForm(FormworkForm):
    zip_code = forms.CharField(widget=ZipInput(attrs={"pattern": "[0-9]{5}"}))


@pytest.mark.unit
@pytest.mark.parametrize("input_type", ["email", "tel", "url"])
def test_text_input_input_type(input_type):
    """``input_type`` covers the text-like types with one widget."""
    assert render_widget(TextInput(input_type=input_type), name="f").select_one("input")["type"] == input_type


@pytest.mark.unit
def test_text_input_keeps_the_type_from_attrs_and_the_class():
    """A ``type`` in attrs and a subclass's ``input_type`` survive, as with Django's own widget."""

    class SearchInput(TextInput):
        input_type = "search"

    assert render_widget(TextInput(attrs={"type": "email"}), name="f").select_one("input")["type"] == "email"
    assert render_widget(SearchInput(), name="f").select_one("input")["type"] == "search"


@pytest.mark.unit
def test_text_input_without_hint_renders_like_django():
    """Without a pattern hint the widget renders exactly like Django's own."""
    stock = forms.TextInput(attrs={"placeholder": "X"}).render("f", "v", attrs={"id": "id_f"})
    assert TextInput(attrs={"placeholder": "X"}).render("f", "v", attrs={"id": "id_f"}) == stock


@pytest.mark.unit
def test_pattern_hint_follows_the_input_in_a_css_group():
    """The hint is an alert after the input that CSS shows while the value misses the pattern."""
    soup = render_widget(ZipInput(attrs={"pattern": "[0-9]{5}"}), name="zip")
    group = soup.select_one("div.group\\/pattern")
    assert [child.name for child in group.find_all(recursive=False)] == ["input", "div"]
    hint = group.select_one("[role=alert]")
    assert hint.get_text() == "Five digits, like 10115."
    assert "hidden" in hint.parent["class"]


@pytest.mark.integration
def test_pattern_hint_keeps_the_field_ids(renderer):
    """The hint wrapper keeps the input id the label targets."""
    soup = render_form(ZipForm(), renderer=renderer)
    assert soup.find("label", id="id_zip_code_label")["for"] == "id_zip_code"
    assert soup.select_one("div.group\\/pattern > input#id_zip_code") is not None
