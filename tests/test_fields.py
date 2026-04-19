"""Tests for FormworkChoiceLabel, FormworkModelChoiceField, and FormworkModelMultipleChoiceField."""

from __future__ import annotations

import pytest

from django_formwork.fields import FormworkChoiceLabel


class TestFormworkChoiceLabel:
    def test_str_returns_label(self):
        label = FormworkChoiceLabel("New York", icon="building", description="East Coast")
        assert str(label) == "New York"

    def test_icon_attribute(self):
        label = FormworkChoiceLabel("New York", icon="building")
        assert label.icon == "building"

    def test_description_attribute(self):
        label = FormworkChoiceLabel("New York", description="East Coast")
        assert label.description == "East Coast"

    def test_defaults_empty_strings(self):
        label = FormworkChoiceLabel("New York")
        assert label.icon == ""
        assert label.description == ""

    def test_equality_by_str(self):
        """FormworkChoiceLabel compares equal to its string representation."""
        label = FormworkChoiceLabel("New York", icon="building")
        assert label == "New York"

    def test_repr(self):
        label = FormworkChoiceLabel("NYC", icon="building", description="East Coast")
        assert "NYC" in repr(label)
