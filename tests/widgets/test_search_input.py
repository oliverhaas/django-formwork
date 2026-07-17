"""Tests for the SearchInput widget-template shadow (leading magnifier)."""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm

from .conftest import assert_html_equivalent, render_form


class SearchForm(FormworkForm):
    """Form fixture with a plain native SearchInput."""

    q = forms.CharField(
        required=False,
        label="",
        widget=forms.SearchInput(attrs={"placeholder": "Search…"}),
    )


@pytest.mark.integration
def test_search_input_wraps_control_in_magnifier(renderer):
    """A native SearchInput renders inside the `.input` container with a leading magnifier."""
    soup = render_form(SearchForm(), renderer=renderer)
    label = soup.select_one("label.input")
    assert label is not None
    kids = label.find_all(recursive=False)
    assert kids[0].name == "i"
    assert "icon-search" in kids[0]["class"]
    assert kids[1].name == "input"
    assert kids[1]["type"] == "search"
    assert kids[1]["name"] == "q"


@pytest.mark.integration
def test_search_input_preserves_value_and_attrs(renderer):
    """The bound value and stock attrs survive the shadow."""
    soup = render_form(SearchForm({"q": "design"}), renderer=renderer)
    inp = soup.select_one("label.input input[type=search]")
    assert inp["value"] == "design"
    assert inp["placeholder"] == "Search…"


@pytest.mark.integration
def test_search_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """The shadow produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(SearchForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SearchForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
