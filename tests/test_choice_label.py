"""Tests for ChoiceLabel."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

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


@pytest.mark.parametrize("widget_class", [Select, SelectMultiple])
def test_counts_show_at_the_end_of_each_option(widget_class):
    widget = widget_class(choices=[("a", "Apples"), ("b", "Pears")], counts={"a": 1200})

    soup = BeautifulSoup(widget.render("fruit", ""), "html.parser")

    rows = {el["data-value"]: el.get_text(" ", strip=True) for el in soup.select("[role=option] > [data-value]")}
    assert rows == {"a": "Apples 1,200", "b": "Pears 0"}
