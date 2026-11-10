"""Tests for the formwork SearchInput widget, and the guard that Django's own stays stock."""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchInput

from .conftest import render_form, render_widget


class SearchForm(FormworkForm):
    """Form fixture using the formwork SearchInput."""

    q = forms.CharField(required=False, label="", widget=SearchInput(attrs={"placeholder": "Search…"}))


class NativeSearchForm(FormworkForm):
    """Form fixture using Django's built-in SearchInput (must stay stock)."""

    q = forms.CharField(required=False, label="", widget=forms.SearchInput(attrs={"placeholder": "Search…"}))


@pytest.mark.unit
def test_search_input_has_a_magnifier_spinner_and_clear_button():
    """By default the input gets a leading magnifier, an htmx spinner and a clear button."""
    soup = render_widget(SearchInput(), name="q", attrs={"id": "id_q"})
    root = soup.select_one('[x-data="formworkSearchInput"]')
    inp = root.select_one("input")
    assert inp["type"] == "search"
    assert inp["x-ref"] == "input"
    icon = root.select_one("#id_q_icon")
    assert icon.select_one("i.icon-search")["aria-hidden"] == "true"
    assert icon.select_one(".loading.htmx-indicator") is not None
    button = root.select_one("button")
    assert button["type"] == "button"
    assert button["@click"] == "clear()"
    assert button["aria-label"] == "Clear search"


@pytest.mark.unit
def test_search_input_without_clear_or_filter_needs_no_component():
    """Without the clear button and the filter there is nothing for Alpine to do."""
    soup = render_widget(SearchInput(show_clear=False, show_spinner=False), name="q")
    assert soup.select_one("[x-data]") is None
    assert soup.select_one("button") is None
    assert soup.select_one(".htmx-indicator") is None
    assert "htmx-indicator-inverse" not in soup.select_one("i.icon-search")["class"]


@pytest.mark.unit
@pytest.mark.parametrize(("show_clear", "padding"), [(True, ["ps-10", "pe-10"]), (False, ["ps-10"])])
def test_search_input_pads_for_its_icons(show_clear, padding):
    """The input keeps the caller's classes and makes room for the icons it shows."""
    soup = render_widget(SearchInput(attrs={"class": "w-64"}, show_clear=show_clear), name="q")
    assert soup.select_one("input")["class"] == ["clearable-search", "w-64", *padding]


@pytest.mark.unit
def test_search_input_default_placeholder():
    """A placeholder is set unless the caller gives one."""
    assert render_widget(SearchInput(), name="q").select_one("input")["placeholder"] == "Search..."
    custom = render_widget(SearchInput(attrs={"placeholder": "Find"}), name="q")
    assert custom.select_one("input")["placeholder"] == "Find"


@pytest.mark.unit
def test_search_input_filter_items_wires_the_filter():
    """``filter_items`` names the rows to filter and refilters after every htmx settle."""
    soup = render_widget(SearchInput(filter_items="#rows > li"), name="q")
    root = soup.select_one('[x-data="formworkSearchInput"]')
    assert root["data-filter-items"] == "#rows > li"
    assert root["@input"] == "sync()"
    assert root["@htmx:after:settle.window"] == "sync()"
    assert root.select_one("input").has_attr("@keydown.enter.prevent")


@pytest.mark.unit
@pytest.mark.parametrize(("value", "disabled"), [(None, True), ("", True), ("desk", False)])
def test_search_input_clear_button_is_disabled_while_empty(value, disabled):
    """An empty search has nothing to clear, so the button starts disabled."""
    button = render_widget(SearchInput(), name="q", value=value).select_one("button")
    assert button.has_attr("disabled") is disabled
    assert button[":disabled"] == "empty"


@pytest.mark.integration
def test_search_input_preserves_value_and_attrs(renderer):
    """The bound value and stock attrs survive the widget template."""
    soup = render_form(SearchForm({"q": "design"}), renderer=renderer)
    inp = soup.select_one("input[type=search]")
    assert inp["value"] == "design"
    assert inp["placeholder"] == "Search…"
    assert inp["id"] == "id_q"


@pytest.mark.integration
def test_builtin_search_widget_is_not_shadowed(renderer):
    """Django's built-in SearchInput renders stock through the formwork renderer.

    Shadowing ``django/forms/widgets/search.html`` would leak into the admin and every third-party form.
    """
    soup = render_form(NativeSearchForm(), renderer=renderer)
    assert soup.select_one("i.icon-search") is None
    assert soup.select_one("[x-data]") is None
    assert soup.select_one("input[type=search]")["name"] == "q"
