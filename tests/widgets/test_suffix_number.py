from __future__ import annotations

import pytest

from django_formwork.widgets import SuffixNumberInput

from .conftest import render_widget


@pytest.mark.unit
def test_suffix_number_shows_the_unit_after_the_value():
    """The suffix sits inside the field, after a native number input."""
    soup = render_widget(SuffixNumberInput(suffix="kg"), name="weight", value=3, attrs={"id": "id_weight"})
    inp = soup.select_one("input#id_weight")
    assert inp["type"] == "number"
    assert inp["value"] == "3"
    assert not inp.has_attr("style")
    assert [span.get_text() for span in soup.select("span")] == ["kg"]


@pytest.mark.unit
def test_suffix_number_prefix_pads_the_input_by_its_length():
    """A prefix gets room in front of the value that grows with the prefix."""
    soup = render_widget(SuffixNumberInput(prefix="EUR"), name="price")
    assert soup.select_one("input")["style"] == "padding-inline-start: calc(1.25rem + 3ch)"
    assert [span.get_text() for span in soup.select("span")] == ["EUR"]


@pytest.mark.unit
def test_suffix_number_without_affixes_renders_the_bare_input():
    """Without prefix or suffix only the input renders."""
    soup = render_widget(SuffixNumberInput(), name="n")
    assert soup.select("span") == []
