"""CountryInput widget tests: unit → integration → e2e → screenshot.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_country_input.py                 # everything
    uv run pytest tests/widgets/test_country_input.py -m unit         # fast only
    uv run pytest tests/widgets/test_country_input.py -m "not e2e"    # skip browser

Levels:
    1. unit        — widget object: instantiation, choices, inheritance
    2. unit        — widget rendering: HTML structure, options
    3. integration — form integration: fieldset, error state, prefix
    4. integration — Jinja2/DTL parity
    5. e2e         — user interaction (no dedicated page yet — see comment)
    6. e2e         — error flow (no dedicated page yet — see comment)
    7. e2e         — morph resilience (no dedicated page yet — see comment)
    8. screenshot  — visual states (no dedicated page yet — see comment)
"""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import CountryInput, SearchSelect

from .conftest import assert_html_equivalent, render_form, render_widget


class CountryForm(FormworkForm):
    """Form fixture for CountryInput integration tests."""

    country = forms.ChoiceField(widget=CountryInput, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_country_input_instantiation():
    """CountryInput can be instantiated and has choices loaded."""
    widget = CountryInput()
    assert list(widget.choices)  # non-empty


@pytest.mark.unit
def test_country_input_inherits_search_select():
    """CountryInput is a subclass of SearchSelect."""
    widget = CountryInput()
    assert isinstance(widget, SearchSelect)


@pytest.mark.unit
def test_country_input_has_countries():
    """Choices include well-known country codes (US, DE, JP)."""
    widget = CountryInput()
    codes = [code for code, _label in widget.choices]
    assert "US" in codes
    assert "DE" in codes
    assert "JP" in codes


@pytest.mark.unit
def test_country_input_choices_have_flags():
    """Each choice label contains a flag emoji (regional indicator symbols)."""
    widget = CountryInput()
    labels = [label for _code, label in widget.choices]
    # Regional indicator symbols are in the range U+1F1E6..U+1F1FF.
    # A flag is two consecutive regional indicators.  Check that at least
    # one label contains such a character pair.
    has_flag = any(any("\U0001f1e6" <= ch <= "\U0001f1ff" for ch in label) for label in labels)
    assert has_flag


@pytest.mark.unit
def test_country_input_choice_labels_include_name():
    """Choice labels contain the country name (not just a code)."""
    widget = CountryInput()
    label_map = dict(widget.choices)
    # "United States" is the long name for "US"
    assert "United States" in label_map.get("US", "")


@pytest.mark.unit
def test_country_input_many_choices():
    """CountryInput has a large number of choices (all ISO 3166-1 countries)."""
    widget = CountryInput()
    assert len(list(widget.choices)) > 100


@pytest.mark.unit
def test_country_input_no_search_url_by_default():
    """No registry entry by default → no server-side search URL in context."""
    widget = CountryInput()
    ctx = widget.get_context("country", "", {"id": "id_country"})
    assert ctx["widget"]["search_url"] is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_country_input_renders_details_dropdown():
    """CountryInput renders a <details class='dropdown'> wrapper."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    wrapper = soup.find("details", class_="dropdown")
    assert wrapper is not None


@pytest.mark.unit
def test_country_input_renders_search_select_class():
    """Wrapper also has the 'search-select' class inherited from SearchSelect."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    wrapper = soup.find("details", class_="search-select")
    assert wrapper is not None


@pytest.mark.unit
def test_country_input_renders_options():
    """Country options are rendered as <button type='button'> elements."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) > 10


@pytest.mark.unit
def test_country_input_renders_us_option():
    """The rendered list contains a button for the United States ('US')."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    buttons = soup.find_all("button", {"data-value": "US"})
    assert len(buttons) == 1


@pytest.mark.unit
def test_country_input_renders_hidden_value_input():
    """Widget renders a hidden <input> to submit the selected country code."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden is not None
    assert hidden["name"] == "country"


@pytest.mark.unit
def test_country_input_renders_summary_trigger():
    """The dropdown trigger is a <summary> element."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    summary = soup.find("summary")
    assert summary is not None


@pytest.mark.unit
def test_country_input_option_labels_contain_flags():
    """Rendered option button text contains flag emoji characters."""
    soup = render_widget(CountryInput(), name="country", attrs={"id": "id_country"})
    buttons = soup.find_all("button", {"type": "button"})
    text = " ".join(btn.get_text() for btn in buttons)
    has_flag = any("\U0001f1e6" <= ch <= "\U0001f1ff" for ch in text)
    assert has_flag


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_country_input_renders_via_form(renderer):
    """CountryInput renders correctly when used inside a FormworkForm."""
    form = CountryForm()
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "country"})
    assert hidden is not None


@pytest.mark.integration
def test_country_input_form_wraps_in_fieldset(renderer):
    """Field template wraps the CountryInput in a fieldset with a stable id."""
    form = CountryForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_country_field")
    assert fieldset is not None


@pytest.mark.integration
def test_country_input_form_prefix(renderer):
    """Form prefix propagates to the hidden input name and widget id."""
    form = CountryForm(prefix="addr")
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "addr-country"})
    assert hidden is not None
    assert hidden["id"] == "id_addr-country"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_country_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """CountryInput produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(CountryForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(CountryForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────
#
# CountryInput has no dedicated e2e page yet.  Tests will be added once a
# /country/ page is wired up — tracked under the e2e coverage work.


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Same as Level 5 — no dedicated page yet.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# Same as Level 5 — no dedicated page yet.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Same as Level 5 — no dedicated page yet.
