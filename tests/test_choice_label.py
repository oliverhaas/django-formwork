"""Tests for ChoiceLabel."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms

from django_formwork import ChoiceLabel
from django_formwork.widgets import Select, SelectMultiple


class TestChoiceLabel:
    def test_str_returns_label(self):
        label = ChoiceLabel("New York", icon="building", description="East Coast")
        assert str(label) == "New York"

    def test_icon_attribute(self):
        label = ChoiceLabel("New York", icon="building")
        assert label.icon == "building"

    def test_description_attribute(self):
        label = ChoiceLabel("New York", description="East Coast")
        assert label.description == "East Coast"

    def test_defaults_empty_strings(self):
        label = ChoiceLabel("New York")
        assert label.icon == ""
        assert label.description == ""

    def test_equality_by_str(self):
        """ChoiceLabel compares equal to its string representation."""
        label = ChoiceLabel("New York", icon="building")
        assert label == "New York"

    def test_repr(self):
        label = ChoiceLabel("NYC", icon="building", description="East Coast")
        assert "NYC" in repr(label)


def test_choice_label_eq_choice_label_all_attributes():
    """Two ChoiceLabels compare equal only when all four attributes match."""
    a = ChoiceLabel("NY", icon="b", description="d", selected_toggle_class="c")
    b = ChoiceLabel("NY", icon="b", description="d", selected_toggle_class="c")
    assert a == b
    assert a != ChoiceLabel("NY", icon="other", description="d", selected_toggle_class="c")


def test_choice_label_hash_equal_for_equal_labels():
    """Equal ChoiceLabels hash identically, so they collapse in sets."""
    a = ChoiceLabel("NY", icon="b")
    b = ChoiceLabel("NY", icon="b")
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_the_forms_of_a_form_class_share_its_choice_labels():
    """A label is a value, so each form's copy of the choices keeps it."""

    class StatusForm(forms.Form):
        status = forms.ChoiceField(choices=[("active", ChoiceLabel("Active", color="success"))], widget=Select)

    first, second = StatusForm(), StatusForm()

    assert first.fields["status"].choices[0][1] is second.fields["status"].choices[0][1]


@pytest.mark.parametrize("widget_class", [Select, SelectMultiple])
def test_counts_show_at_the_end_of_each_option(widget_class):
    widget = widget_class(choices=[("a", "Apples"), ("b", "Pears")], counts={"a": 1200})

    soup = BeautifulSoup(widget.render("fruit", ""), "html.parser")

    rows = {el["data-value"]: el.get_text(" ", strip=True) for el in soup.select("[role=option] > [data-value]")}
    assert rows == {"a": "Apples 1,200", "b": "Pears 0"}


@pytest.mark.parametrize("widget_class", [Select, SelectMultiple])
def test_badges_show_each_option_as_a_badge_in_its_color(widget_class):
    """The empty choice and a label with its own HTML stay as they are."""
    choices = [
        ("", "None"),
        ("active", ChoiceLabel("Active", color="success")),
        ("draft", "Draft"),
        ("other", ChoiceLabel("Other", label_html="<b>Other</b>")),
    ]
    widget = widget_class(choices=choices, badges=True, allow_clear=True)

    soup = BeautifulSoup(widget.render("status", ""), "html.parser")

    badges = {}
    for row in soup.select("[role=option] > [data-value]"):
        badge = row.select_one(".badge")
        badges[row["data-value"]] = badge and (badge.get_text(), badge["class"][2:])
    assert badges == {
        "": None,
        "active": ("Active", ["badge-soft", "badge-success"]),
        "draft": ("Draft", ["badge-ghost"]),
        "other": None,
    }


def test_badge_of_the_selected_option_shows_in_the_closed_select():
    widget = Select(choices=[("active", ChoiceLabel("Active", color="success"))], badges=True)

    soup = BeautifulSoup(widget.render("status", "active"), "html.parser")

    assert soup.select_one("summary [x-html=labelHtml] .badge.badge-success").get_text() == "Active"


def test_closed_select_with_badges_takes_its_width_from_the_badges():
    """The hidden copy that sizes the trigger holds the badges, which are wider than their text."""
    widget = Select(choices=[("active", ChoiceLabel("Active", color="success")), ("draft", "Draft")], badges=True)

    soup = BeautifulSoup(widget.render("status", "active"), "html.parser")

    assert [badge.get_text() for badge in soup.select(".formwork-autowidth .badge")] == ["Active", "Draft"]
