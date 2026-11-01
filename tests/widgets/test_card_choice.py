from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import CardCheckboxSelectMultiple, CardRadioSelect

from .conftest import render_form, render_widget

PLANS = [("free", "Free"), ("pro", "Pro")]


class PlanForm(FormworkForm):
    plan = forms.ChoiceField(choices=PLANS, widget=CardRadioSelect)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("widget_cls", "input_type"), [(CardRadioSelect, "radio"), (CardCheckboxSelectMultiple, "checkbox")]
)
def test_card_choice_renders_one_card_per_option(widget_cls, input_type):
    """Each option is a card label around its input and text; the selected one is checked."""
    soup = render_widget(widget_cls(choices=PLANS), name="plan", value=["pro"], attrs={"id": "id_plan"})
    cards = soup.select("#id_plan > label")
    assert [card.get_text(strip=True) for card in cards] == ["Free", "Pro"]
    inputs = [card.select_one("input") for card in cards]
    assert [i["type"] for i in inputs] == [input_type, input_type]
    assert [i["id"] for i in inputs] == ["id_plan_0", "id_plan_1"]
    assert [i.has_attr("checked") for i in inputs] == [False, True]


@pytest.mark.unit
def test_card_choice_escapes_option_labels():
    """Option labels are text, never markup."""
    soup = render_widget(CardRadioSelect(choices=[("x", "<b>X</b>")]), name="plan")
    assert soup.select_one("b") is None
    assert soup.select_one("span").get_text() == "<b>X</b>"


@pytest.mark.integration
def test_card_choice_group_is_a_fieldset_with_an_error_border(renderer):
    """The group renders in a fieldset under a legend, and an error marks every card."""
    form = PlanForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_plan_field")
    assert fieldset.find("legend").get_text(strip=True) == "Plan"
    cards = fieldset.select("#id_plan > label")
    assert all("border-error" in card["class"] for card in cards)
