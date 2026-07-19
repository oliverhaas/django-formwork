"""Tests for the formwork SearchInput widget (leading magnifier).

Also guards the framework rule that Django's built-in search widget is never
shadowed, so the admin and third-party forms keep their stock rendering.
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchInput

from .conftest import assert_html_equivalent, render_form


class SearchForm(FormworkForm):
    """Form fixture using the formwork SearchInput."""

    q = forms.CharField(
        required=False,
        label="",
        widget=SearchInput(attrs={"placeholder": "Search…"}),
    )


class NativeSearchForm(FormworkForm):
    """Form fixture using Django's built-in SearchInput (must stay stock)."""

    q = forms.CharField(
        required=False,
        label="",
        widget=forms.SearchInput(attrs={"placeholder": "Search…"}),
    )


@pytest.mark.integration
def test_search_input_wraps_control_in_magnifier(renderer):
    """The formwork SearchInput renders inside the `.input` container with a leading magnifier."""
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
    """The bound value and stock attrs survive the widget template."""
    soup = render_form(SearchForm({"q": "design"}), renderer=renderer)
    inp = soup.select_one("label.input input[type=search]")
    assert inp["value"] == "design"
    assert inp["placeholder"] == "Search…"


@pytest.mark.integration
def test_search_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """The widget produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(SearchForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SearchForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_builtin_search_widget_is_not_shadowed(renderer):
    """Django's built-in SearchInput renders stock through the formwork renderer.

    Shadowing ``django/forms/widgets/search.html`` would leak into Django admin
    and every third-party form, since widgets resolve through the global
    ``FORM_RENDERER``. The built-in widget stays a bare ``<input type="search">``
    with no magnifier wrapper; the styled affordance is opt-in via the formwork
    SearchInput.
    """
    soup = render_form(NativeSearchForm(), renderer=renderer)
    assert soup.select_one("label.input") is None
    assert soup.select_one("i.icon-search") is None
    inp = soup.select_one("input[type=search]")
    assert inp is not None
    assert inp["name"] == "q"
