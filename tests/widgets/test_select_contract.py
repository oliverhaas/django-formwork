"""Rendering contract shared by the select family: toggle text, client rows, labels."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.contrib.auth.models import User

import django_formwork
from django_formwork.forms import FormworkForm
from django_formwork.widgets import ComboBox, ComboBoxMultiple, Select, SelectMultiple

FRUITS = [("a", "Apples"), ("b", "Bananas"), ("c", "Cherries"), ("d", "Dates")]
MANY = [(str(i), f"Option {i}") for i in range(200)]
WIDGET_TEMPLATES = Path(django_formwork.__file__).parent / "templates" / "formwork" / "widgets"


def _users(request):
    return User.objects.all()


class _ToggleForm(FormworkForm):
    """One field the browser filters, one the search endpoint feeds."""

    client = forms.MultipleChoiceField(choices=FRUITS, widget=SelectMultiple)
    served = forms.MultipleChoiceField(
        choices=FRUITS,
        widget=SelectMultiple(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _ClientForm(FormworkForm):
    """No endpoint: the browser filters the rows, so all of them must stay in the DOM."""

    one = forms.ChoiceField(choices=MANY, widget=Select)
    many = forms.MultipleChoiceField(choices=MANY, widget=SelectMultiple)


class _FamilyForm(FormworkForm):
    select = forms.ChoiceField(choices=FRUITS, widget=Select)
    select_multiple = forms.MultipleChoiceField(choices=FRUITS, widget=SelectMultiple)
    combo_box = forms.CharField(widget=ComboBox(suggestions=["Apples", "Bananas"]))
    combo_box_multiple = forms.CharField(widget=ComboBoxMultiple(suggestions=["Apples", "Bananas"]))
    floating = forms.ChoiceField(choices=FRUITS, widget=Select(attrs={"placeholder": "Fruit"}, floating=True))


def _toggle_text(field: str, selected: list[str]) -> str:
    html = str(_ToggleForm(initial={field: selected})[field])
    span = BeautifulSoup(html, "html.parser").select_one("summary [x-text]")
    assert span is not None
    return " ".join(span.get_text().split())


@pytest.mark.unit
@pytest.mark.parametrize("field", ["client", "served"])
def test_toggle_names_the_selected_options(field: str) -> None:
    assert _toggle_text(field, ["a", "b"]) == "Apples, Bananas"


@pytest.mark.unit
@pytest.mark.parametrize("field", ["client", "served"])
def test_toggle_counts_selections_past_the_summary_threshold(field: str) -> None:
    assert _toggle_text(field, ["a", "b", "c", "d"]) == "4 selected"


@pytest.mark.unit
@pytest.mark.parametrize("field", ["one", "many"])
def test_client_side_filtering_keeps_every_option(field: str) -> None:
    soup = BeautifulSoup(str(_ClientForm()[field]), "html.parser")
    listbox = soup.select_one("ul[role=listbox]")
    assert listbox is not None
    assert len(listbox.select("li")) == len(MANY)


@pytest.mark.unit
def test_widget_templates_carry_no_script() -> None:
    """Alpine components live in static modules; a template script repeats on every swap."""
    templates = sorted(WIDGET_TEMPLATES.rglob("*.html"))
    assert templates
    for template in templates:
        assert "<script" not in template.read_text(), template.name


@pytest.mark.unit
@pytest.mark.parametrize("field", ["select", "select_multiple", "combo_box", "combo_box_multiple", "floating"])
def test_no_label_targets_a_hidden_input(field: str) -> None:
    soup = BeautifulSoup(str(_FamilyForm()[field].as_field_group()), "html.parser")
    for label in soup.select("label[for]"):
        target = soup.find(id=label["for"])
        assert target is not None, label["for"]
        assert target.get("type") != "hidden", label["for"]
