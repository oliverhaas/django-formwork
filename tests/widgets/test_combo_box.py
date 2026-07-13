"""Canonical test patterns for the ComboBox widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_combo_box.py                 # everything
    uv run pytest tests/widgets/ -m unit                         # all widgets, unit only
    uv run pytest tests/widgets/test_combo_box.py -m "not e2e"   # skip browser tests

Levels:
    1. unit        : widget object: instantiation, get_context, value_from_datadict
    2. unit        : widget rendering: HTML structure, classes, attributes
    3. integration : form integration: field template, error state, morph IDs
    4. integration : Jinja2/DTL parity: identical HTML across engines
    5. e2e         : user interaction: typing, picking suggestion, clear
    6. e2e         : error flow: skipped (no required ComboBox on the /combobox/ page)
    7. e2e         : morph resilience: typed value and selected suggestions preserved
    8. screenshot  : visual states: default, open dropdown, suggestion selected
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ComboBox

from .conftest import assert_html_equivalent, make_server_widget, render_form, render_widget


class ComboBoxForm(FormworkForm):
    """Form fixture for ComboBox integration tests."""

    tag = forms.CharField(
        widget=ComboBox(suggestions=["Alpha", "Beta", "Gamma"]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_combo_box_instantiation_default():
    """ComboBox can be instantiated with no arguments."""
    widget = ComboBox()
    assert widget.suggestions == []
    assert widget.multiple is False


@pytest.mark.unit
def test_combo_box_instantiation_with_suggestions():
    """ComboBox stores provided suggestions."""
    widget = ComboBox(suggestions=["A", "B", "C"])
    assert widget.suggestions == ["A", "B", "C"]


@pytest.mark.unit
def test_combo_box_instantiation_multiple():
    """ComboBox stores multiple flag."""
    widget = ComboBox(suggestions=["A"], multiple=True)
    assert widget.multiple is True


@pytest.mark.unit
def test_combo_box_instantiation_icons():
    """ComboBox stores icons dict."""
    widget = ComboBox(suggestions=["A"], icons={"A": "<svg/>"})
    assert widget.icons == {"A": "<svg/>"}


@pytest.mark.unit
def test_combo_box_get_context_suggestions_as_dicts():
    """get_context() converts suggestion strings to dicts with text/icon/description."""
    widget = ComboBox(suggestions=["A", "B"], icons={"A": mark_safe("<svg/>")})
    ctx = widget.get_context("test", "", {})
    _name, sugs = ctx["widget"]["suggestion_groups"][0]
    assert sugs[0] == {"text": "A", "icon": mark_safe("<svg/>"), "description": ""}
    assert sugs[1] == {"text": "B", "icon": "", "description": ""}


@pytest.mark.unit
def test_combo_box_get_context_multiple_mode():
    """get_context() exposes multiple flag correctly."""
    widget = ComboBox(suggestions=["A", "B"], multiple=True)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is True


@pytest.mark.unit
def test_combo_box_get_context_single_mode():
    """get_context() defaults to multiple=False."""
    widget = ComboBox(suggestions=["A", "B"])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is False


@pytest.mark.unit
def test_combo_box_get_context_search_url_resolved_from_registry():
    """get_context() resolves a search_url for widgets attached to the registry."""
    widget = make_server_widget(ComboBox)
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is not None
    assert ctx["widget"]["search_url"].startswith("/__formwork__/search/")


@pytest.mark.unit
def test_combo_box_get_context_search_url_none_when_unregistered():
    """get_context() leaves search_url None when no registry entry is attached."""
    widget = ComboBox(suggestions=["A"])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_combo_box_value_from_datadict_returns_string():
    """value_from_datadict returns the typed string value."""
    widget = ComboBox(suggestions=["Alpha"])
    data = QueryDict("test=Rust")
    val = widget.value_from_datadict(data, {}, "test")
    assert val == "Rust"


@pytest.mark.unit
def test_combo_box_value_from_datadict_empty():
    """value_from_datadict returns empty string when nothing submitted."""
    widget = ComboBox(suggestions=["Alpha"])
    data = QueryDict("")
    val = widget.value_from_datadict(data, {}, "test")
    assert val is None


@pytest.mark.unit
def test_combo_box_empty_suggestions_get_context():
    """ComboBox with no suggestions produces a single empty group in context."""
    widget = ComboBox()
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["suggestion_groups"] == [("", [])]


@pytest.mark.unit
def test_combo_box_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = ComboBox(suggestions=["a"])
    ctx = widget.get_context("field", None, {"id": "id_field"})
    assert ctx["widget"]["name"] == "field"


# ─── Level 1b: Grouped suggestions (Python API) ──────────────────────────


@pytest.mark.unit
def test_combo_box_suggestion_groups_flat_input():
    """A flat list of strings is wrapped in a single unnamed group."""
    widget = ComboBox(suggestions=["A", "B"])
    groups = widget._suggestion_groups()
    assert len(groups) == 1
    name, items = groups[0]
    assert name == ""
    assert [it["text"] for it in items] == ["A", "B"]


@pytest.mark.unit
def test_combo_box_suggestion_groups_grouped_input():
    """Grouped suggestions ``[(name, [items])]`` are preserved as-is."""
    widget = ComboBox(suggestions=[("Italian", ["Pizza", "Pasta"]), ("Asian", ["Sushi"])])
    groups = widget._suggestion_groups()
    assert [g[0] for g in groups] == ["Italian", "Asian"]
    assert [it["text"] for it in groups[0][1]] == ["Pizza", "Pasta"]
    assert [it["text"] for it in groups[1][1]] == ["Sushi"]


@pytest.mark.unit
def test_combo_box_suggestion_groups_empty():
    """No suggestions produces a single empty group."""
    widget = ComboBox()
    groups = widget._suggestion_groups()
    assert groups == [("", [])]


@pytest.mark.unit
def test_combo_box_suggestion_groups_icons_descriptions_attached():
    """Icons and descriptions populate per-item across groups."""
    widget = ComboBox(
        suggestions=[("G1", ["A"]), ("G2", ["B"])],
        icons={"A": mark_safe("<svg/>"), "B": mark_safe("<svg2/>")},
        descriptions={"A": "alpha", "B": "beta"},
    )
    groups = widget._suggestion_groups()
    assert groups[0][1][0]["icon"] == "<svg/>"
    assert groups[0][1][0]["description"] == "alpha"
    assert groups[1][1][0]["icon"] == "<svg2/>"
    assert groups[1][1][0]["description"] == "beta"


@pytest.mark.unit
def test_combo_box_get_context_grouped_populates_suggestion_groups():
    """get_context exposes the grouped structure under ``suggestion_groups``."""
    widget = ComboBox(suggestions=[("Cuisine", ["Pizza", "Sushi"])])
    ctx = widget.get_context("test", "", {})
    groups = ctx["widget"]["suggestion_groups"]
    assert len(groups) == 1
    name, items = groups[0]
    assert name == "Cuisine"
    assert [it["text"] for it in items] == ["Pizza", "Sushi"]


@pytest.mark.unit
def test_combo_box_get_context_grouped_icons_json_includes_all_groups():
    """``icons_json`` contains icons for items spread across multiple groups."""
    import json as _json

    widget = ComboBox(
        suggestions=[("G1", ["A"]), ("G2", ["B"])],
        icons={"A": "🍕", "B": "🍣"},
    )
    ctx = widget.get_context("test", "", {})
    icon_map = _json.loads(ctx["widget"]["icons_json"])
    assert icon_map == {"A": "🍕", "B": "🍣"}


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_combo_box_renders_without_id():
    """Widget renders without an id attribute."""
    widget = ComboBox(suggestions=["a", "b"])
    soup = render_widget(widget, name="field", attrs={})
    div = soup.find("div", class_="combobox")
    assert div is not None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_combo_box_renders_dropdown_wrapper():
    """render() produces a div with class 'dropdown'."""
    widget = ComboBox(suggestions=["Alpha", "Beta"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="dropdown")
    assert wrapper is not None


@pytest.mark.unit
def test_combo_box_class_on_wrapper():
    """render() produces a div with class 'combobox'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="combobox")
    assert wrapper is not None


@pytest.mark.unit
def test_combo_box_text_input_is_form_field():
    """The text input submits directly, without a hidden input."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input is not None
    assert text_input["name"] == "test"
    assert text_input["type"] == "text"
    # No hidden input
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden is None


@pytest.mark.unit
def test_combo_box_role():
    """The combobox input has role='combobox' and aria-autocomplete='list'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["role"] == "combobox"
    assert trigger["aria-autocomplete"] == "list"


@pytest.mark.unit
def test_combo_box_suggestions_as_buttons():
    """Each suggestion renders as a button[type=button]."""
    widget = ComboBox(suggestions=["Alpha", "Beta", "Gamma"])
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 3


@pytest.mark.unit
def test_combo_box_suggestion_labels():
    """Suggestion text appears in span elements."""
    widget = ComboBox(suggestions=["Alpha", "Beta"])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_combo_box_preserves_value():
    """render() sets the input value to the current field value."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", value="hello")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input["value"] == "hello"


@pytest.mark.unit
def test_combo_box_default_placeholder():
    """Default placeholder contains 'search'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert "search" in text_input.get("placeholder", "").lower()


@pytest.mark.unit
def test_combo_box_custom_placeholder():
    """Custom placeholder is rendered."""
    widget = ComboBox(suggestions=["Alpha"], attrs={"placeholder": "Type here"})
    soup = render_widget(widget, name="test")
    text_input = soup.find("input", class_="combobox-input")
    assert text_input["placeholder"] == "Type here"


@pytest.mark.unit
def test_combo_box_alpine_x_data():
    """Wrapper div binds to the formworkComboBox Alpine.data component."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", attrs={"x-data": "formworkComboBox"})
    assert wrapper is not None


@pytest.mark.unit
def test_combo_box_no_results_alert():
    """A DaisyUI alert-info alert-soft is rendered for client-side mode."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    alert = soup.find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert" in alert["class"]
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


@pytest.mark.unit
def test_combo_box_listbox_role():
    """The suggestions list has role='listbox'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert listbox is not None


@pytest.mark.unit
def test_combo_box_aria_invalid():
    """aria-invalid='true' on wrapper propagates to the input."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["aria-invalid"] == "true"


@pytest.mark.unit
def test_combo_box_aria_describedby():
    """aria-describedby propagates to the combobox input."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-describedby": "id_test_helptext"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["aria-describedby"] == "id_test_helptext"


@pytest.mark.unit
def test_combo_box_no_aria_describedby_by_default():
    """The input has no aria-describedby without help text or errors."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    trigger = soup.find("input", class_="combobox-input")
    assert not trigger.has_attr("aria-describedby")


@pytest.mark.unit
def test_combo_box_htmx_attrs_when_registered():
    """When the widget is attached to the registry, htmx attributes are added to the input."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["hx-get"].startswith("/__formwork__/search/")
    assert "input changed delay:300ms" in trigger["hx-trigger"]
    assert trigger["hx-target"] == "#id_tags_listbox"
    assert trigger["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_combo_box_no_htmx_attrs_without_search_url():
    """Without search_url, no htmx attributes are added."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    trigger = soup.find("input", class_="combobox-input")
    assert not trigger.has_attr("hx-get")


@pytest.mark.unit
def test_combo_box_static_suggestions_ignored_when_search_url():
    """When server search is wired, static ``suggestions`` are ignored:
    the listbox renders pre-rendered registry options instead.  ``count=0``
    here so the listbox renders only the empty-state alert."""
    widget = make_server_widget(ComboBox, count=0, suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    assert listbox.find_all("li", attrs={"role": "option"}) == []


@pytest.mark.unit
def test_combo_box_renders_no_results_alert_when_initial_options_empty():
    """An empty initial set still communicates state: the listbox carries
    the same ``role=status`` alert that the htmx response would render."""
    widget = make_server_widget(ComboBox, count=0)
    soup = render_widget(widget, attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    alert = listbox.find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


@pytest.mark.unit
def test_combo_box_no_alpine_no_results_when_search_url():
    """When search_url is set, 'No results' element is not rendered."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_combo_box_prerenders_initial_options_when_registered():
    """The first ``max_results`` registry items are baked into the listbox
    so the dropdown opens with real suggestions; htmx replaces them on
    first focus."""
    widget = make_server_widget(ComboBox, count=3)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    items = listbox.find_all("li", attrs={"role": "option"})
    assert len(items) == 3
    first = items[0].find("button")
    assert first["data-suggestion"] == "Item 0"


@pytest.mark.unit
def test_combo_box_prerendered_count_caps_at_registry_max_results():
    """Pre-rendered options never exceed ``reg.max_results`` (default 50)."""
    widget = make_server_widget(ComboBox, count=120)
    soup = render_widget(widget, attrs={"id": "id_x"})
    assert len(soup.find("ul", attrs={"id": "id_x_listbox"}).find_all("li", attrs={"role": "option"})) == 50


@pytest.mark.unit
def test_combo_box_prerendered_options_include_descriptions_when_registry_has_descriptions():
    """When ``description_from_instance`` is registered, pre-rendered options carry a description span."""
    widget = make_server_widget(ComboBox, count=1, descriptions=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"})
    desc = first.find("span", class_="text-xs")
    assert desc is not None
    assert "desc 0" in desc.get_text()


@pytest.mark.unit
def test_combo_box_no_prerendered_options_without_search_url():
    """No server-search → no pre-rendered options (the listbox shows static suggestions instead)."""
    widget = ComboBox(suggestions=["Alpha"])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["initial_options"] == []


@pytest.mark.unit
def test_combo_box_renders_error_alert_when_search_url():
    """The error alert is rendered as a plain DaisyUI alert, hidden by
    default via x-show='hasError'."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert is not None
    assert alert.get("x-show") == "hasError"
    assert "alert" in alert["class"]
    assert "alert-error" in alert["class"]
    assert "Search failed" in alert.get_text()


@pytest.mark.unit
def test_combo_box_no_error_alert_without_search_url():
    """No error alert without server-side search."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    assert soup.find("div", attrs={"role": "alert"}) is None


@pytest.mark.unit
def test_combo_box_input_wires_error_handlers():
    """``hasError`` clears in ``before:swap`` on success and sets on
    error events.  The ``before:request`` reset was removed to avoid
    briefly re-showing the prerendered listbox between request and
    failed response."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
    trigger = soup.find("input", class_="combobox-input")
    assert "hx-on::before:request" not in trigger.attrs
    assert "preventDefault" in trigger["hx-on::before:swap"]
    assert "hasError = false" in trigger["hx-on::before:swap"]
    assert "hasError = true" in trigger["hx-on::response:error"]
    assert "hasError = true" in trigger["hx-on::error"]


@pytest.mark.unit
def test_combo_box_listbox_hidden_only_on_error():
    """The listbox stays visible at all times except when an error occurs."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", id="id_test_listbox")
    assert listbox.get("x-show") == "!hasError"


@pytest.mark.unit
def test_combo_box_binds_alpine_component_when_search_url():
    """The wrapper binds to the formworkComboBox component regardless of search_url;
    hasError state lives in the component, not the markup."""
    widget = make_server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    wrapper = soup.find("div", class_="combobox")
    assert wrapper["x-data"] == "formworkComboBox"


@pytest.mark.unit
def test_combo_box_icon_rendering():
    """Icons are rendered inline in suggestion buttons."""
    widget = ComboBox(
        suggestions=["Python", "Go"],
        icons={"Python": mark_safe('<img src="py.svg">')},
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "py.svg"})
    assert icon is not None


@pytest.mark.unit
def test_combo_box_no_icon_when_not_provided():
    """No icon elements appear when icons dict is empty."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


@pytest.mark.unit
def test_combo_box_event_delegation_data_attrs():
    """Suggestion buttons carry data-suggestion for event delegation."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    btn = soup.find("button", {"type": "button"})
    assert btn["data-suggestion"] == "Alpha"


@pytest.mark.unit
def test_combo_box_wrapper_has_id():
    """Combobox wrapper div gets an id derived from the field id."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    wrapper = soup.find("div", class_="combobox")
    assert wrapper["id"] == "id_test_combobox"


@pytest.mark.unit
def test_combo_box_no_wrapper_id_without_id():
    """Combobox wrapper div has no id when no field id is provided."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="combobox")
    assert not wrapper.has_attr("id")


@pytest.mark.unit
def test_combo_box_empty_suggestions_renders_no_buttons():
    """ComboBox with no suggestions renders zero buttons."""
    widget = ComboBox()
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 0


# ─── Level 2b: Grouped suggestions (HTML rendering) ──────────────────────


@pytest.mark.unit
def test_combo_box_grouped_renders_group_headers():
    """Grouped suggestions render a ``<li class='menu-title'>`` per group."""
    widget = ComboBox(
        suggestions=[("Italian", ["Pizza", "Pasta"]), ("Asian", ["Sushi"])],
    )
    soup = render_widget(widget, name="food", attrs={"id": "id_food"})
    headers = soup.find_all("li", class_="menu-title")
    assert [h.text.strip() for h in headers] == ["Italian", "Asian"]


@pytest.mark.unit
def test_combo_box_no_group_headers_for_flat_suggestions():
    """A flat suggestion list never produces ``menu-title`` headers."""
    widget = ComboBox(suggestions=["A", "B", "C"])
    soup = render_widget(widget, name="test")
    headers = soup.find_all("li", class_="menu-title")
    assert headers == []


@pytest.mark.unit
def test_combo_box_grouped_options_keep_icons():
    """Each option inside a group still renders its icon."""
    widget = ComboBox(
        suggestions=[("G1", ["Pizza"]), ("G2", ["Sushi"])],
        icons={"Pizza": mark_safe("<svg>p</svg>"), "Sushi": mark_safe("<svg>s</svg>")},
    )
    soup = render_widget(widget, name="food")
    buttons = soup.find_all("button", {"data-suggestion": True})
    assert {b["data-suggestion"] for b in buttons} == {"Pizza", "Sushi"}
    # Icons appear as data-icon attribute
    assert {b.get("data-icon", "") for b in buttons} == {"<svg>p</svg>", "<svg>s</svg>"}


@pytest.mark.unit
def test_combo_box_grouped_group_header_xshow_includes_child_labels():
    """Group ``<li>`` ``x-show`` lists the child labels for matching."""
    widget = ComboBox(suggestions=[("Italian", ["Pizza", "Pasta"])])
    soup = render_widget(widget, name="food")
    header = soup.find("li", class_="menu-title")
    xshow = header["x-show"]
    assert "'Pizza'" in xshow
    assert "'Pasta'" in xshow
    assert "matches(l)" in xshow


@pytest.mark.unit
def test_combo_box_grouped_renders_all_suggestion_buttons():
    """All items across all groups render as suggestion buttons."""
    widget = ComboBox(
        suggestions=[("G1", ["A", "B"]), ("G2", ["C"])],
    )
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"data-suggestion": True})
    assert {b["data-suggestion"] for b in buttons} == {"A", "B", "C"}


# ─── Level 2c: Keyboard navigation scaffolding ───────────────────────────


@pytest.mark.unit
def test_combo_box_keydown_handlers_on_wrapper():
    """The combobox wrapper has @keydown handlers for arrows and enter."""
    widget = ComboBox(suggestions=["A"])
    html = widget.render("test", "")
    assert "@keydown.arrow-down" in html
    assert "@keydown.arrow-up" in html
    assert "@keydown.enter" in html
    assert "@keydown.escape" in html


@pytest.mark.unit
def test_combo_box_keydown_invokes_nav_methods():
    """Inline keydown handlers reference the nav/confirm methods on the component."""
    widget = ComboBox(suggestions=["A"])
    html = widget.render("test", "")
    assert "nav(1)" in html
    assert "nav(-1)" in html
    assert "confirm()" in html


@pytest.mark.unit
def test_combo_box_xdata_binds_alpine_component():
    """Wrapper binds to the formworkComboBox component (state including
    highlightedEl is defined in the JS module)."""
    widget = ComboBox(suggestions=["A"])
    html = widget.render("test", "")
    assert 'x-data="formworkComboBox"' in html


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_combo_box_renders_via_form(renderer):
    """ComboBox renders correctly when used inside a FormworkForm."""
    form = ComboBoxForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "tag"})
    assert inp is not None
    assert inp["type"] == "text"


@pytest.mark.integration
def test_combo_box_form_wraps_in_fieldset(renderer):
    """Field template wraps the ComboBox in a fieldset with a stable id."""
    form = ComboBoxForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_tag_field")
    assert fieldset is not None


@pytest.mark.integration
def test_combo_box_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the input."""
    form = ComboBoxForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "tag"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_combo_box_error_state_aria_describedby(renderer):
    """Django's auto aria-describedby (→ the error container) reaches the input."""
    form = ComboBoxForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "tag"})
    assert inp.get("aria-describedby") == "id_tag_error"


@pytest.mark.integration
def test_combo_box_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = ComboBoxForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_tag_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_combo_box_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = ComboBoxForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "cfg-tag"})
    assert inp is not None
    assert inp["id"] == "id_cfg-tag"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_combo_box_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """ComboBox produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(ComboBoxForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(ComboBoxForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_combo_box_grouped_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Grouped ComboBox renders identically via DTL and Jinja2."""

    class GroupedComboBoxForm(FormworkForm):
        food = forms.CharField(
            widget=ComboBox(
                suggestions=[("Italian", ["Pizza", "Pasta"]), ("Asian", ["Sushi"])],
                icons={"Pizza": mark_safe("<i>p</i>")},
            ),
            required=False,
        )

    soup_dtl = render_form(GroupedComboBoxForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(GroupedComboBoxForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_combo_box_renders_on_page(combobox_page):
    """ComboBox is visible on the /combobox/ page."""
    combo = combobox_page.locator(".dropdown.combobox").first
    assert combo.is_visible()


@pytest.mark.e2e
def test_combo_box_typing_shows_filtered_suggestions(combobox_page):
    """Typing in the input filters suggestions to matching entries."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.combobox").first
    assert combo.locator("button", has_text="Python").is_visible()
    assert not combo.locator("button", has_text="Go").is_visible()


@pytest.mark.e2e
def test_combo_box_pick_suggestion(combobox_page):
    """Clicking a suggestion populates the input with that value."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Ru")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.combobox").first
    combo.locator("button", has_text="Rust").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Rust"


@pytest.mark.e2e
def test_combo_box_free_text_allowed(combobox_page):
    """Arbitrary text can be typed (ComboBox is free text, not constrained)."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combo_box_multiple_pick_adds_value(combobox_page):
    """In multiple mode, clicking a suggestion appends it."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" in inp.input_value()


@pytest.mark.e2e
def test_combo_box_multiple_pick_second_appends(combobox_page):
    """In multiple mode, a second pick appends to the comma-separated list."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    combo.locator("button", has_text="Sushi").click()
    combobox_page.wait_for_timeout(100)
    val = inp.input_value()
    assert "Pizza" in val
    assert "Sushi" in val


@pytest.mark.e2e
def test_combo_box_multiple_toggle_off(combobox_page):
    """In multiple mode, clicking a selected suggestion removes it."""
    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" in inp.input_value()
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" not in inp.input_value()


# ─── Level 5b: E2e, grouped ComboBox ─────────────────────────────────────
#
# food_grouped is the 8th ComboBox on the page (nth(7)).


@pytest.mark.e2e
def test_combo_box_grouped_shows_headers(combobox_page):
    """Grouped ComboBox shows ``menu-title`` headers for each cuisine."""
    combo = combobox_page.locator(".dropdown.combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    headers = [h.inner_text().strip() for h in combo.locator("li.menu-title").all() if h.is_visible()]
    assert headers == ["Italian", "Japanese", "Mexican"]


@pytest.mark.e2e
def test_combo_box_grouped_filter_hides_empty_groups(combobox_page):
    """Typing 'pi' (matches only 'Pizza') hides Japanese and Mexican headers."""
    combo = combobox_page.locator(".dropdown.combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    inp.fill("pi")
    combobox_page.wait_for_timeout(150)
    visible_headers = [h.inner_text().strip() for h in combo.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Italian"]


@pytest.mark.e2e
def test_combo_box_grouped_pick_from_group(combobox_page):
    """Picking a suggestion inside a group sets the input value."""
    combo = combobox_page.locator(".dropdown.combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button[data-suggestion='Sushi']").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Sushi"


# ─── Level 5c: E2e, keyboard navigation ──────────────────────────────────
#
# Keyboard handlers live on the wrapper ``<div class='dropdown combobox'>``,
# so the input must be focused (dropdown open) for events to bubble up.


def _open_combo_box(page, name: str):
    """Open a ComboBox by clicking its input; returns input + wrapper locators."""
    inp = page.locator(f'input[name="{name}"]')
    inp.click()
    page.wait_for_timeout(150)
    return inp


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_highlights_first(combobox_page):
    """ArrowDown highlights the first visible suggestion."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(100)
    highlighted = combobox_page.locator(".dropdown.combobox").first.locator("[data-suggestion].highlighted")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-suggestion") == "Python"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_navigates(combobox_page):
    """Each ArrowDown moves to the next suggestion."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.combobox").first.locator("[data-suggestion].highlighted")
    assert highlighted.first.get_attribute("data-suggestion") == "JavaScript"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_wraps_to_first(combobox_page):
    """ArrowDown past the last suggestion wraps back to the first."""
    inp = _open_combo_box(combobox_page, "language_single")
    # 6 options: Python, JavaScript, Go, Rust, TypeScript, Ruby
    for _ in range(7):
        inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.combobox").first.locator("[data-suggestion].highlighted")
    assert highlighted.first.get_attribute("data-suggestion") == "Python"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowup_wraps_to_last(combobox_page):
    """ArrowUp from no highlight goes to the last visible suggestion."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("ArrowUp")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.combobox").first.locator("[data-suggestion].highlighted")
    assert highlighted.first.get_attribute("data-suggestion") == "Ruby"


@pytest.mark.e2e
def test_combo_box_keyboard_filter_skips_hidden_options(combobox_page):
    """After filtering, ArrowDown only highlights visible (matching) options."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.fill("Ru")  # Matches Rust + Ruby
    combobox_page.wait_for_timeout(150)
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    inp.press("ArrowDown")  # Should wrap back to Rust
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.combobox").first.locator("[data-suggestion].highlighted")
    val = highlighted.first.get_attribute("data-suggestion")
    assert val == "Rust"


@pytest.mark.e2e
def test_combo_box_single_keyboard_enter_picks_and_closes(combobox_page):
    """Single-mode: Enter on highlighted option sets value and closes dropdown."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    inp.press("ArrowDown")  # JavaScript
    combobox_page.wait_for_timeout(50)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    assert inp.input_value() == "JavaScript"
    # Dropdown should be closed (open=false)
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.combobox')[0]).open",
    )
    assert is_open is False


@pytest.mark.e2e
def test_combo_box_single_keyboard_enter_no_highlight_picks_first(combobox_page):
    """With no highlight, Enter picks the first visible suggestion."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.fill("Go")
    combobox_page.wait_for_timeout(150)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    assert inp.input_value() == "Go"


@pytest.mark.e2e
def test_combo_box_multiple_keyboard_enter_toggles_keeps_open(combobox_page):
    """Multi-mode: Enter on highlighted toggles into the comma list, dropdown stays open."""
    inp = _open_combo_box(combobox_page, "toppings_multi")
    inp.press("ArrowDown")  # Pizza
    combobox_page.wait_for_timeout(50)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    val = inp.input_value()
    assert "Pizza" in val
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.combobox')[1]).open",
    )
    assert is_open is True


@pytest.mark.e2e
def test_combo_box_multiple_keyboard_enter_toggles_off(combobox_page):
    """Multi-mode: pressing Enter again on the same value removes it."""
    inp = _open_combo_box(combobox_page, "toppings_multi")
    inp.press("ArrowDown")
    inp.press("Enter")  # Add Pizza
    combobox_page.wait_for_timeout(150)
    assert "Pizza" in inp.input_value()
    # ArrowDown to Pizza again. Note: after Enter, Alpine clears the highlight
    # (in pick()), so we restart navigation.
    inp.press("ArrowDown")  # Pizza highlighted again
    combobox_page.wait_for_timeout(50)
    inp.press("Enter")  # Toggle Pizza off
    combobox_page.wait_for_timeout(150)
    assert "Pizza" not in inp.input_value()


@pytest.mark.e2e
def test_combo_box_keyboard_close_clears_highlight(combobox_page):
    """Closing the dropdown via Escape clears ``.highlighted`` from the DOM."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    combo = combobox_page.locator(".dropdown.combobox").first
    assert combo.locator("[data-suggestion].highlighted").count() == 1
    inp.press("Escape")
    combobox_page.wait_for_timeout(150)
    assert combo.locator("[data-suggestion].highlighted").count() == 0


@pytest.mark.e2e
def test_combo_box_keyboard_escape_closes_dropdown(combobox_page):
    """Escape closes the dropdown (open=false)."""
    inp = _open_combo_box(combobox_page, "language_single")
    inp.press("Escape")
    combobox_page.wait_for_timeout(150)
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.combobox')[0]).open",
    )
    assert is_open is False


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# The /combobox/ page has no required ComboBox fields (all required=False),
# so dedicated error-flow tests cannot be triggered without a separate page.
# Skipped until a required-field variant of the ComboBox page is available.


# ─── Level 6b: E2e, server-side search loading + failure UX ──────────────
#
# Indices on /combobox/:  4 = language_htmx (working),
#                         8 = language_failing (slow + always 500).


@pytest.mark.e2e
def test_combo_box_prerenders_options_on_initial_load(combobox_page):
    """Real options render in every htmx-mode ComboBox on first page load, before any user interaction, with no
    skeleton flicker. The combobox at index 4 wires ``search_choices_language_htmx`` against ``E2E_LANGUAGES`` (6
    entries), all baked in since the default ``reg.max_results`` is 50."""
    htmx_combo = combobox_page.locator(".dropdown.combobox").nth(4)
    items = htmx_combo.locator("ul[role='listbox'] > li[role='option']")
    assert items.count() == 6


@pytest.mark.e2e
def test_combo_box_options_refresh_on_first_focus(combobox_page):
    """First focus fires htmx; the swap replaces pre-rendered options with
    the fresh response: same count, same listbox."""
    from playwright.sync_api import expect

    combo = combobox_page.locator(".dropdown.combobox").nth(4)
    inp = combobox_page.locator('input[name="language_htmx"]')
    inp.click()
    expect(combo.locator("ul button")).to_have_count(6, timeout=10000)


@pytest.mark.e2e
def test_combo_box_failing_search_shows_error_alert(combobox_page):
    """When the search endpoint returns 500, the error alert replaces the listbox."""
    from playwright.sync_api import expect

    combo = combobox_page.locator(".dropdown.combobox").nth(8)
    inp = combobox_page.locator('input[name="language_failing"]')
    inp.click()
    alert = combo.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    assert "Search failed" in alert.text_content()
    expect(combo.locator("ul[role='listbox']")).to_be_hidden()


@pytest.mark.e2e
def test_combo_box_input_works_after_error(combobox_page):
    """The combobox input remains usable after a failure: typing fires a
    new request and the value lands in the input."""
    from playwright.sync_api import expect

    combo = combobox_page.locator(".dropdown.combobox").nth(8)
    inp = combobox_page.locator('input[name="language_failing"]')
    requests: list[str] = []
    combobox_page.on("request", lambda r: requests.append(r.url) if "search/" in r.url else None)
    inp.click()
    alert = combo.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    initial_count = len(requests)
    inp.fill("x")
    # 300ms input-changed debounce + buffer for the request to fire.
    combobox_page.wait_for_timeout(500)
    assert len(requests) > initial_count, "expected typing to fire a new search request"
    assert inp.input_value() == "x"


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_combo_box_morph_preserves_typed_value(combobox_page):
    """Typed free-text value survives an htmx form morph."""
    from tests.e2e.conftest import submit

    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    submit(combobox_page)
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combo_box_morph_preserves_multiple_selected(combobox_page):
    """Comma-separated multiple selections survive an htmx form morph."""
    from tests.e2e.conftest import submit

    combo = combobox_page.locator(".dropdown.combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    combo.locator("button", has_text="Sushi").click()
    combobox_page.wait_for_timeout(100)
    # Close dropdown and blur to strip trailing comma
    combobox_page.keyboard.press("Escape")
    combobox_page.wait_for_timeout(200)
    inp.blur()
    combobox_page.wait_for_timeout(100)
    val_before = inp.input_value()
    submit(combobox_page)
    assert inp.input_value() == val_before


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only: these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.


@pytest.mark.screenshot
def test_combo_box_screenshot_default(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox in default (empty) state."""
    wrapper = combobox_page.locator(".dropdown.combobox").first
    assert_screenshot(wrapper, "combobox-default.png")


@pytest.mark.screenshot
def test_combo_box_screenshot_open_dropdown(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox with dropdown open."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("P")
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator(".dropdown.combobox").first
    assert_screenshot(wrapper, "combobox-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_grouped_open(combobox_page, assert_screenshot):
    """Visual snapshot: grouped ComboBox with dropdown open showing optgroup headers."""
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator("#id_food_grouped_combobox")
    assert_screenshot(wrapper, "combobox-grouped-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_keyboard_highlighted(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox with a suggestion highlighted via keyboard."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    inp.press("ArrowDown")  # Highlight first option
    inp.press("ArrowDown")  # JavaScript
    combobox_page.wait_for_timeout(50)
    wrapper = combobox_page.locator(".dropdown.combobox").first
    assert_screenshot(wrapper, "combobox-keyboard-highlighted.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_suggestion_selected(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox after a suggestion has been selected."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combobox_page.locator(".dropdown.combobox").first.locator("button", has_text="Python").click()
    combobox_page.wait_for_timeout(100)
    wrapper = combobox_page.locator(".dropdown.combobox").first
    assert_screenshot(wrapper, "combobox-selected.png")
