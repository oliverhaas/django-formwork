"""Tests for the SearchInput widget.

Levels:
    1. unit        — widget object: instantiation, flags, get_context
    2. unit        — widget rendering: magnifier, spinner, clear button
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchInput

from .conftest import assert_html_equivalent, render_form, render_widget


class SearchInputForm(FormworkForm):
    """Form fixture for SearchInput integration tests."""

    query = forms.CharField(widget=SearchInput(), required=False)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_search_input_instantiation():
    """SearchInput exposes the expected template_name."""
    assert SearchInput().template_name == "formwork/widgets/search_input.html"


@pytest.mark.unit
def test_search_input_inherits_text_input():
    """SearchInput is a subclass of Django's TextInput."""
    assert isinstance(SearchInput(), forms.TextInput)


@pytest.mark.unit
def test_search_input_type_is_search():
    """The widget renders as an <input type='search'>."""
    assert SearchInput().input_type == "search"


@pytest.mark.unit
def test_search_input_flags_default_true():
    """Both the spinner and clear button are enabled by default."""
    widget = SearchInput()
    assert widget.show_spinner is True
    assert widget.show_clear is True


@pytest.mark.unit
def test_search_input_flags_stored():
    """Disabling the spinner and clear button is retained."""
    widget = SearchInput(show_spinner=False, show_clear=False)
    assert widget.show_spinner is False
    assert widget.show_clear is False


@pytest.mark.unit
def test_search_input_get_context_exposes_flags():
    """get_context surfaces both flags for the template."""
    ctx = SearchInput(show_spinner=False, show_clear=False).get_context("q", None, {})
    assert ctx["widget"]["show_spinner"] is False
    assert ctx["widget"]["show_clear"] is False


@pytest.mark.unit
def test_search_input_default_placeholder():
    """A default 'Search…' placeholder is applied when none is given."""
    ctx = SearchInput().get_context("q", None, {})
    assert ctx["widget"]["attrs"]["placeholder"] == "Search…"


@pytest.mark.unit
def test_search_input_keeps_explicit_placeholder():
    """An explicit placeholder is not overridden by the default."""
    widget = SearchInput(attrs={"placeholder": "Find a city"})
    ctx = widget.get_context("q", None, {})
    assert ctx["widget"]["attrs"]["placeholder"] == "Find a city"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_search_input_renders_search_input():
    """The widget renders an <input type='search'>."""
    soup = render_widget(SearchInput(), name="q", attrs={"id": "id_q"})
    assert soup.find("input", attrs={"type": "search"}) is not None


@pytest.mark.unit
def test_search_input_renders_magnifier_icon():
    """A leading magnifier icon is rendered."""
    soup = render_widget(SearchInput(), name="q", attrs={"id": "id_q"})
    assert soup.select_one("span.search-input-icon i.icon-search") is not None


@pytest.mark.unit
def test_search_input_icon_container_has_id():
    """The icon container carries the '<id>_icon' id for hx-indicator targeting."""
    soup = render_widget(SearchInput(), name="q", attrs={"id": "id_q"})
    assert soup.find("span", id="id_q_icon") is not None


@pytest.mark.unit
def test_search_input_renders_clear_button():
    """When show_clear is on, a labelled clear button is rendered."""
    soup = render_widget(SearchInput(show_clear=True), name="q", attrs={"id": "id_q"})
    button = soup.find("button", attrs={"aria-label": "Clear search"})
    assert button is not None
    assert button.find("i", class_="icon-x") is not None


@pytest.mark.unit
def test_search_input_no_clear_button_when_disabled():
    """When show_clear is off, no clear button is rendered."""
    soup = render_widget(SearchInput(show_clear=False), name="q", attrs={"id": "id_q"})
    assert soup.find("button", attrs={"aria-label": "Clear search"}) is None


@pytest.mark.unit
def test_search_input_renders_spinner():
    """When show_spinner is on, an htmx-indicator spinner is rendered."""
    soup = render_widget(SearchInput(show_spinner=True), name="q", attrs={"id": "id_q"})
    spinner = soup.find("span", class_="search-input-spinner")
    assert spinner is not None
    assert "htmx-indicator" in spinner["class"]


@pytest.mark.unit
def test_search_input_no_spinner_when_disabled():
    """When show_spinner is off, no spinner and no magnifier swap class."""
    soup = render_widget(SearchInput(show_spinner=False), name="q", attrs={"id": "id_q"})
    assert soup.find("span", class_="search-input-spinner") is None
    icon = soup.select_one("i.icon-search")
    assert "htmx-indicator-inverse" not in icon.get("class", [])


@pytest.mark.unit
def test_search_input_magnifier_swaps_when_spinner_on():
    """With the spinner on, the magnifier carries the inverse indicator class."""
    soup = render_widget(SearchInput(show_spinner=True), name="q", attrs={"id": "id_q"})
    icon = soup.select_one("i.icon-search")
    assert "htmx-indicator-inverse" in icon["class"]


@pytest.mark.unit
def test_search_input_clear_button_wires_x_ref():
    """The clear button targets the input via Alpine x-ref."""
    soup = render_widget(SearchInput(show_clear=True), name="q", attrs={"id": "id_q"})
    assert soup.find("input", attrs={"x-ref": "input"}) is not None


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_search_input_renders_via_form(renderer):
    """SearchInput renders correctly inside a FormworkForm."""
    soup = render_form(SearchInputForm(), renderer=renderer)
    inp = soup.find("input", attrs={"name": "query"})
    assert inp is not None
    assert inp.get("type") == "search"


@pytest.mark.integration
def test_search_input_form_wraps_in_fieldset(renderer):
    """The field template wraps SearchInput in a fieldset with a stable id."""
    soup = render_form(SearchInputForm(), renderer=renderer)
    assert soup.find("fieldset", id="id_query_field") is not None


@pytest.mark.integration
def test_search_input_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(SearchInputForm(prefix="cfg"), renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-query"})
    assert inp is not None
    assert inp["id"] == "id_cfg-query"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_search_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """SearchInput produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(SearchInputForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SearchInputForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_search_input_minimal_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """A spinner-less, clear-less SearchInput stays in parity across engines."""

    class MinimalForm(FormworkForm):
        query = forms.CharField(
            widget=SearchInput(show_spinner=False, show_clear=False),
            required=False,
        )

    soup_dtl = render_form(MinimalForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(MinimalForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)
