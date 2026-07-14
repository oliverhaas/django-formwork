"""SearchSelect tests, ordered unit, integration, e2e, screenshot; filter levels with -m."""

from __future__ import annotations

import json
import re

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork.fields import ChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchSelect

from .conftest import assert_html_equivalent, make_server_widget, open_dropdown, render_form, render_widget, submit


class SearchSelectForm(FormworkForm):
    """Local form fixture for SearchSelect integration tests."""

    city = forms.ChoiceField(
        widget=SearchSelect(choices=[("nyc", "New York"), ("ldn", "London")]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_search_select_default_choices_empty():
    """SearchSelect can be instantiated with no choices."""
    widget = SearchSelect()
    assert list(widget.choices) == []


@pytest.mark.unit
def test_search_select_accepts_choices():
    """Choices passed to constructor are stored on the widget."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    vals = [v for v, _label in widget.choices]
    assert "a" in vals
    assert "b" in vals


@pytest.mark.unit
def test_search_select_show_search_default_none():
    """show_search defaults to None (auto-detect from threshold)."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    assert widget.show_search is None


@pytest.mark.unit
def test_search_select_show_search_explicit_true():
    """Explicit show_search=True is stored on the widget."""
    widget = SearchSelect(choices=[("a", "Alpha")], show_search=True)
    assert widget.show_search is True


@pytest.mark.unit
def test_search_select_show_search_explicit_false():
    """Explicit show_search=False is stored on the widget."""
    widget = SearchSelect(choices=[("a", "Alpha")], show_search=False)
    assert widget.show_search is False


@pytest.mark.unit
def test_search_select_get_context_selected_label():
    """get_context returns the label for the currently selected value."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", "a", {})
    assert ctx["widget"]["selected_label"] == "Alpha"


@pytest.mark.unit
def test_search_select_get_context_selected_label_empty_when_no_value():
    """selected_label is empty string when value is the empty option."""
    widget = SearchSelect(choices=[("", ""), ("a", "Alpha")])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["selected_label"] == ""


@pytest.mark.unit
def test_search_select_get_context_search_url_resolved_from_registry():
    """get_context resolves a search_url for widgets attached to the registry."""
    widget = make_server_widget(SearchSelect, choices=[("a", "Alpha")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is not None
    assert ctx["widget"]["search_url"].startswith("/__formwork__/search/")


@pytest.mark.unit
def test_search_select_get_context_search_url_none_when_unregistered():
    """search_url in context is None when no registry entry is attached."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_search_select_get_context_show_search_false_below_threshold():
    """show_search is False when choice count is below search_threshold."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is False


@pytest.mark.unit
def test_search_select_get_context_show_search_true_at_threshold():
    """show_search is True when choice count >= search_threshold (20)."""
    choices = [(str(i), f"Option {i}") for i in range(20)]
    widget = SearchSelect(choices=choices)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_search_select_get_context_show_search_explicit_overrides():
    """Explicit show_search=True overrides the threshold check."""
    widget = SearchSelect(choices=[("a", "Alpha")], show_search=True)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_search_select_get_context_optgroups_with_icons():
    """Icons from ChoiceLabel are injected into optgroups."""
    widget = SearchSelect(
        choices=[
            ("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>"))),
            ("b", "Beta"),
        ],
    )
    ctx = widget.get_context("test", "", {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["icon"] == "<svg>icon</svg>"
            else:
                assert option["icon"] == ""


@pytest.mark.unit
def test_search_select_value_from_datadict_present():
    """value_from_datadict returns the submitted value from POST data."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    data = QueryDict("city=b")
    result = widget.value_from_datadict(data, {}, "city")
    assert result == "b"


@pytest.mark.unit
def test_search_select_value_from_datadict_missing():
    """value_from_datadict returns None when the key is absent."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "city")
    assert result is None


@pytest.mark.unit
def test_search_select_no_icons_kwarg():
    """SearchSelect no longer accepts an icons kwarg."""
    with pytest.raises(TypeError):
        SearchSelect(choices=[("a", "Alpha")], icons={"a": "icon"})


@pytest.mark.unit
def test_search_select_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = SearchSelect(choices=[("a", "A")])
    ctx = widget.get_context("field", None, {"id": "id_field"})
    assert ctx["widget"]["name"] == "field"


@pytest.mark.unit
def test_search_select_renders_without_id():
    """Widget renders without an id attribute."""
    widget = SearchSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="field", attrs={})
    details = soup.find("details")
    assert details is not None


@pytest.mark.unit
def test_search_select_optgroup_rendering():
    """Grouped choices render all options from all groups."""
    choices = [
        ("Europe", [("ldn", "London"), ("par", "Paris")]),
        ("Asia", [("tyo", "Tokyo")]),
    ]
    widget = SearchSelect(choices=choices)
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    buttons = soup.find_all("button")
    text = " ".join(btn.get_text() for btn in buttons)
    assert "London" in text
    assert "Paris" in text
    assert "Tokyo" in text


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_search_select_renders_details_dropdown():
    """Widget renders a <details class='dropdown'> wrapper."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", class_="dropdown")
    assert wrapper is not None


@pytest.mark.unit
def test_search_select_class_on_wrapper():
    """Widget wrapper also has the 'search-select' class."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", class_="search-select")
    assert wrapper is not None


@pytest.mark.unit
def test_search_select_renders_summary_trigger():
    """The trigger is a <summary> with text-left class (DaisyUI .select via @apply)."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    summary = soup.find("summary")
    assert summary is not None
    assert "text-left" in summary.get("class", [])


@pytest.mark.unit
def test_search_select_renders_hidden_value_input():
    """Widget renders a hidden <input> that submits the selected value."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden is not None
    assert hidden["name"] == "test"


@pytest.mark.unit
def test_search_select_hidden_input_has_id():
    """The hidden input gets the id from attrs."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_city"})
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden["id"] == "id_city"


@pytest.mark.unit
def test_search_select_renders_dropdown_content():
    """Widget renders a <div class='dropdown-content'>."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    assert dropdown is not None


@pytest.mark.unit
def test_search_select_options_as_buttons():
    """Each non-empty choice is rendered as a <button type='button'>."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 2


@pytest.mark.unit
def test_search_select_option_labels_rendered():
    """Option button labels appear in the rendered HTML."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_search_select_empty_option_excluded():
    """The empty option (value='') is excluded from the dropdown button list."""
    widget = SearchSelect(choices=[("", "Select..."), ("a", "Alpha")])
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 1


@pytest.mark.unit
def test_search_select_alpine_x_data():
    """The wrapper <details> binds to the formworkSearchSelect Alpine.data component."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", attrs={"x-data": "formworkSearchSelect"})
    assert wrapper is not None


@pytest.mark.unit
def test_search_select_show_search_false_in_data_attr():
    """data-show-search is 'false' on the wrapper when below threshold."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    details = soup.find("details")
    assert details.get("data-show-search") == "false"


@pytest.mark.unit
def test_search_select_selected_label_in_data_attr():
    """Selected option label appears in data-label when value is pre-set."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test", value="b")
    wrapper = soup.find("details", attrs={"x-data": "formworkSearchSelect"})
    assert wrapper["data-label"] == "Beta"
    assert wrapper["data-value"] == "b"


@pytest.mark.unit
def test_search_select_listbox_role():
    """The option list uses role='listbox' for accessibility."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert listbox is not None


@pytest.mark.unit
def test_search_select_ul_has_click_handler():
    """The listbox ul has an Alpine @click event handler for delegation."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert "@click" in str(listbox)


@pytest.mark.unit
def test_search_select_event_delegation_data_attrs():
    """Buttons carry data-value and data-label for event delegation."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    btn = soup.find("button", {"type": "button"})
    assert btn["data-value"] == "a"
    assert btn["data-label"] == "Alpha"


@pytest.mark.unit
def test_search_select_no_results_alert():
    """A DaisyUI alert-info alert-soft is rendered with x-show='noResults'."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    alert = soup.find("div", attrs={"role": "status"})
    assert alert is not None
    assert alert.get("x-show") == "noResults"
    assert "alert" in alert["class"]
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


# ─── Level 2b: Keyboard navigation scaffolding ───────────────────────────


@pytest.mark.unit
def test_search_select_keydown_handlers_on_wrapper():
    """The ``<details>`` wrapper has @keydown handlers for arrows and enter."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    html = widget.render("test", "")
    assert "@keydown.arrow-down" in html
    assert "@keydown.arrow-up" in html
    assert "@keydown.enter" in html


@pytest.mark.unit
def test_search_select_xdata_binds_alpine_component():
    """Both client- and htmx-mode templates bind to the formworkSearchSelect component."""
    plain = SearchSelect(choices=[("a", "A")]).render("test", "")
    htmx_mode = make_server_widget(SearchSelect, choices=[]).render("test", "")
    for html in (plain, htmx_mode):
        assert 'x-data="formworkSearchSelect"' in html


@pytest.mark.unit
def test_search_select_keydown_invokes_nav_methods():
    """Inline keydown handlers reference the nav/confirm methods on the component."""
    widget = SearchSelect(choices=[("a", "A")])
    html = widget.render("test", "")
    assert "nav(1)" in html
    assert "nav(-1)" in html
    assert "confirm()" in html


@pytest.mark.unit
def test_search_select_aria_invalid_on_summary():
    """aria-invalid='true' propagates to the summary trigger element."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    summary = soup.find("summary")
    assert summary["aria-invalid"] == "true"


@pytest.mark.unit
def test_search_select_no_aria_invalid_when_valid():
    """summary does not have aria-invalid when the widget has no errors."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-invalid")


@pytest.mark.unit
def test_search_select_aria_describedby_on_summary():
    """aria-describedby propagates to the summary trigger element."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-describedby": "id_test_helptext"})
    summary = soup.find("summary")
    assert summary["aria-describedby"] == "id_test_helptext"


@pytest.mark.unit
def test_search_select_no_aria_describedby_by_default():
    """summary does not have aria-describedby without help text or errors."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-describedby")


@pytest.mark.unit
def test_search_select_wrapper_has_stable_id():
    """details wrapper id is derived from the widget id."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="search-select")
    assert details["id"] == "id_test_searchselect"


@pytest.mark.unit
def test_search_select_no_wrapper_id_without_attrs_id():
    """details wrapper has no id when no widget id is supplied."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="search-select")
    assert not details.has_attr("id")


@pytest.mark.unit
def test_search_select_htmx_wrapper_id():
    """details wrapper id is present even when search_url is set."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="search-select")
    assert details["id"] == "id_test_searchselect"


@pytest.mark.unit
def test_search_select_search_input_inside_dropdown():
    """Search text input is rendered inside dropdown-content when show_search=True."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")], show_search=True)
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "text"})
    assert search is not None


@pytest.mark.unit
def test_search_select_htmx_attrs_when_registered():
    """Search input carries htmx attrs when the widget is attached to the registry."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "text"})
    assert search["hx-get"].startswith("/__formwork__/search/")
    assert "input changed delay:300ms" in search["hx-trigger"]
    assert search["hx-target"] == "#id_city_listbox"
    assert search["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_search_select_no_htmx_attrs_without_search_url():
    """Search input does NOT have hx-get when no search_url is set."""
    widget = SearchSelect(choices=[("a", "Alpha")], show_search=True)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "text"})
    assert not search.has_attr("hx-get")


@pytest.mark.unit
def test_search_select_static_choices_ignored_when_search_url():
    """Static ``choices`` are ignored when server search is wired. The
    listbox renders pre-rendered registry options instead.  ``count=0``
    here so the listbox renders the empty-state alert (no options)."""
    widget = make_server_widget(SearchSelect, count=0, choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    assert listbox.find_all("li", attrs={"role": "option"}) == []


@pytest.mark.unit
def test_search_select_renders_no_results_alert_when_initial_options_empty():
    """An empty initial set still communicates state. The listbox carries
    the same ``role=status`` alert that the htmx response would render."""
    widget = make_server_widget(SearchSelect, count=0)
    soup = render_widget(widget, attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    alert = listbox.find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


@pytest.mark.unit
def test_search_select_no_alpine_no_results_when_search_url():
    """No 'No results' paragraph when search_url is set (server handles no results)."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_search_select_prerenders_initial_options_when_registered():
    """The first ``max_results`` registry items are baked straight into the
    listbox so the dropdown opens with real data; htmx replaces them on
    first focus."""
    widget = make_server_widget(SearchSelect, count=3)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    options = listbox.find_all("li", attrs={"role": "option"})
    assert len(options) == 3
    # Items carry the same data attrs as the htmx response markup.
    first = options[0].find("button")
    assert first["data-value"] == "0"
    assert first["data-label"] == "Item 0"


@pytest.mark.unit
def test_search_select_prerendered_count_caps_at_registry_max_results():
    """Pre-rendered options never exceed ``reg.max_results`` (default 50)."""
    widget = make_server_widget(SearchSelect, count=2)
    soup = render_widget(widget, attrs={"id": "id_x"})
    assert len(soup.find("ul", attrs={"id": "id_x_listbox"}).find_all("li", attrs={"role": "option"})) == 2

    widget = make_server_widget(SearchSelect, count=120)
    soup = render_widget(widget, attrs={"id": "id_y"})
    # Default reg.max_results is 50.
    assert len(soup.find("ul", attrs={"id": "id_y_listbox"}).find_all("li", attrs={"role": "option"})) == 50


@pytest.mark.unit
def test_search_select_prerendered_options_include_icons_when_registry_has_icons():
    """When ``icon_from_instance`` is registered, pre-rendered options include the icon glyph."""
    widget = make_server_widget(SearchSelect, count=1, icons=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"}).find("button")
    assert first.has_attr("data-icon")
    assert "📍0" in first.get_text()


@pytest.mark.unit
def test_search_select_prerendered_options_include_descriptions_when_registry_has_descriptions():
    """When ``description_from_instance`` is registered, pre-rendered options carry a description span."""
    widget = make_server_widget(SearchSelect, count=1, descriptions=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"})
    desc = first.find("span", class_="text-xs")
    assert desc is not None
    assert "desc 0" in desc.get_text()


@pytest.mark.unit
def test_search_select_no_prerendered_options_without_search_url():
    """No server-search → no pre-rendered options (the listbox shows static optgroups instead)."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["initial_options"] == []


@pytest.mark.unit
def test_search_select_renders_error_alert_when_search_url():
    """The error alert is rendered as a plain DaisyUI alert, hidden by
    default via x-show='hasError'."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert is not None
    assert alert.get("x-show") == "hasError"
    assert "alert" in alert["class"]
    assert "alert-error" in alert["class"]
    assert "Search failed" in alert.get_text()


@pytest.mark.unit
def test_search_select_no_error_alert_without_search_url():
    """No error alert rendered when there is no server-side search."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    assert soup.find("div", attrs={"role": "alert"}) is None


@pytest.mark.unit
def test_search_select_search_input_wires_error_handlers():
    """The htmx search input toggles ``hasError`` on the response side
    only: it clears in ``before:swap`` when the swap will succeed
    (status < 400) and sets back to ``true`` on ``response:error`` /
    ``error``.  Resetting on ``before:request`` was removed because it
    briefly re-showed the prerendered listbox between request and
    response, producing a 'No results' flicker."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    search = soup.find("div", class_="dropdown-content").find("input", {"type": "text"})
    assert "hx-on::before:request" not in search.attrs
    assert "preventDefault" in search["hx-on::before:swap"]
    assert "hasError = false" in search["hx-on::before:swap"]
    assert "hasError = true" in search["hx-on::response:error"]
    assert "hasError = true" in search["hx-on::error"]


@pytest.mark.unit
def test_search_select_listbox_hidden_only_on_error():
    """The listbox stays visible at all times except when an error occurs;
    the spinner indicates loading without blanking the listbox."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", id="id_test_listbox")
    assert listbox.get("x-show") == "!hasError"


@pytest.mark.unit
def test_search_select_has_search_url_flag_when_search_url():
    """data-has-search-url is 'true' when server search is wired."""
    widget = make_server_widget(SearchSelect, choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="search-select")
    assert details["data-has-search-url"] == "true"


@pytest.mark.unit
def test_search_select_show_search_visible_from_first_render_when_count_meets_threshold():
    """When the registry count meets the threshold, the search input opens from first paint."""
    widget = make_server_widget(SearchSelect, count=30)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="search-select")
    assert details["data-show-search"] == "true"


@pytest.mark.unit
def test_search_select_show_search_hidden_when_count_below_threshold():
    """A small registry count keeps the search input hidden."""
    widget = make_server_widget(SearchSelect, count=5)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="search-select")
    assert details["data-show-search"] == "false"


@pytest.mark.unit
def test_search_select_icon_rendered_in_option():
    """ChoiceLabel icons appear in the rendered option buttons."""
    widget = SearchSelect(
        choices=[
            ("a", ChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_search_select_no_icon_element_when_not_provided():
    """No <img> elements rendered when no ChoiceLabel icons."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


@pytest.mark.unit
def test_search_select_option_data_icon_attribute_escaped():
    """Icon HTML with quotes must not break the option's data-icon attribute.

    The button carries data-icon so the JS can restore the icon on select.
    Without escaping, the icon's quotes close the attribute early; the parsed
    value must round-trip to the full icon string.
    """
    icon = '<img src="a.svg">'
    widget = SearchSelect(choices=[("a", ChoiceLabel("Alpha", icon=mark_safe(icon)))])  # noqa: S308
    soup = render_widget(widget, name="test")
    button = soup.find("button", attrs={"data-value": "a"})
    assert button is not None
    assert button["data-icon"] == icon


# ─── Level 2c: selected_toggle_class (trigger recolor) ───────────────────


@pytest.mark.unit
def test_search_select_get_context_optgroups_with_selected_toggle_class():
    """selected_toggle_class from ChoiceLabel is injected into optgroups."""
    widget = SearchSelect(
        choices=[
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
            ("b", "Beta"),
        ],
    )
    ctx = widget.get_context("test", "", {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["selected_toggle_class"] == "select-error"
            else:
                assert option["selected_toggle_class"] == ""


@pytest.mark.unit
def test_search_select_widget_selected_toggle_class_seeded_from_selection():
    """The preselected option's class is exposed at widget level so JS init seeds it."""
    widget = SearchSelect(
        choices=[
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
            ("b", ChoiceLabel("Beta", selected_toggle_class="select-success")),
        ],
    )
    ctx = widget.get_context("test", "b", {})
    assert ctx["widget"]["selected_toggle_class"] == "select-success"


@pytest.mark.unit
def test_search_select_widget_selected_toggle_class_empty_without_selection():
    """No selection → the widget-level class seed is empty."""
    widget = SearchSelect(choices=[("a", ChoiceLabel("Alpha", selected_toggle_class="select-error"))])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["selected_toggle_class"] == ""


@pytest.mark.unit
def test_search_select_option_data_selected_toggle_class_attribute():
    """Option buttons carry data-selected-toggle-class; the attribute is absent when empty."""
    widget = SearchSelect(
        choices=[
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    a = soup.find("button", attrs={"data-value": "a"})
    b = soup.find("button", attrs={"data-value": "b"})
    assert a["data-selected-toggle-class"] == "select-error"
    assert not b.has_attr("data-selected-toggle-class")


@pytest.mark.unit
def test_search_select_root_data_selected_toggle_class_from_preselected():
    """The root <details> carries the selected option's class for JS init."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
        ],
    )
    soup = render_widget(widget, name="test", value="a", attrs={"id": "id_test"})
    details = soup.find("details")
    assert details["data-selected-toggle-class"] == "select-error"


@pytest.mark.unit
def test_search_select_summary_static_class_includes_selected_toggle_class():
    """A preselected option's toggle class is server-rendered on the summary, before Alpine runs."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
        ],
    )
    soup = render_widget(widget, name="test", value="a")
    assert "select-error" in soup.find("summary")["class"]


@pytest.mark.unit
def test_search_select_summary_static_placeholder_class_tracks_selection():
    """Without a selection the summary is server-rendered with formwork-placeholder; with one it is not."""
    widget = SearchSelect(choices=[("", ""), ("a", "Alpha")])
    empty = render_widget(widget, name="test")
    selected = render_widget(widget, name="test", value="a")
    assert "formwork-placeholder" in empty.find("summary")["class"]
    assert "formwork-placeholder" not in selected.find("summary")["class"]


@pytest.mark.unit
def test_search_select_selected_icon_server_rendered_without_cloak():
    """A preselected option's icon is server-rendered inside the trigger span, not x-cloaked."""
    widget = SearchSelect(
        choices=[("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>")))],
    )
    soup = render_widget(widget, name="test", value="a")
    span = soup.find("summary").find("span", attrs={"x-show": "icon"})
    assert span.find("svg") is not None
    assert not span.has_attr("x-cloak")


@pytest.mark.unit
def test_search_select_icon_span_cloaked_without_selection():
    """No selected icon → the trigger icon span stays empty and x-cloaked until Alpine decides."""
    widget = SearchSelect(
        choices=[("", ""), ("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>")))],
    )
    soup = render_widget(widget, name="test")
    span = soup.find("summary").find("span", attrs={"x-show": "icon"})
    assert span.has_attr("x-cloak")
    assert span.find("svg") is None


@pytest.mark.unit
def test_search_select_summary_class_binding_includes_selected_toggle_class():
    """The summary :class array binds selectedToggleClass so Alpine can swap it live."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    summary = soup.find("summary")
    assert "selectedToggleClass" in summary.get(":class", "")


@pytest.mark.unit
def test_search_select_option_data_selected_toggle_class_escaped():
    """A class string with a quote must not break the data attribute (plain autoescape suffices)."""
    widget = SearchSelect(choices=[("a", ChoiceLabel("Alpha", selected_toggle_class='c" x'))])
    soup = render_widget(widget, name="test")
    button = soup.find("button", attrs={"data-value": "a"})
    assert button["data-selected-toggle-class"] == 'c" x'


@pytest.mark.unit
def test_search_select_prerendered_options_include_selected_toggle_class_when_registered():
    """When selected_toggle_class_from_instance is registered, pre-rendered options carry the data attr."""
    widget = make_server_widget(SearchSelect, count=1, selected_toggle_classes=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"}).find("button")
    assert first["data-selected-toggle-class"] == "select-error"


# ─── Level 2b: Optgroup rendering ────────────────────────────────────────


@pytest.mark.unit
def test_search_select_renders_group_headers():
    """Grouped choices produce <li class='menu-title'> headers per non-empty group."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            ("Europe", [("ldn", "London"), ("par", "Paris")]),
            ("Asia", [("tyo", "Tokyo")]),
        ],
    )
    soup = render_widget(widget, attrs={"id": "id_city"})
    titles = [li.get_text(strip=True) for li in soup.find_all("li", class_="menu-title")]
    assert titles == ["Europe", "Asia"]


@pytest.mark.unit
def test_search_select_no_group_headers_for_flat_choices():
    """Flat choices produce no menu-title headers."""
    widget = SearchSelect(choices=[("", ""), ("nyc", "New York"), ("ldn", "London")])
    soup = render_widget(widget, attrs={"id": "id_city"})
    assert soup.find_all("li", class_="menu-title") == []


@pytest.mark.unit
def test_search_select_group_header_xshow_includes_child_labels():
    """Group <li class='menu-title'> has an x-show whose JS array contains
    every child option label, so it auto-hides when no child matches search."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            ("Europe", [("ldn", "London"), ("par", "Paris"), ("ber", "Berlin")]),
            ("Asia", [("tyo", "Tokyo")]),
        ],
    )
    soup = render_widget(widget, attrs={"id": "id_city"})
    titles = soup.find_all("li", class_="menu-title")
    assert len(titles) == 2

    europe = next(t for t in titles if "Europe" in t.get_text())
    xshow = europe.get("x-show", "")
    assert "London" in xshow
    assert "Paris" in xshow
    assert "Berlin" in xshow
    assert "search" in xshow


@pytest.mark.unit
def test_search_select_grouped_options_keep_icons_and_descriptions():
    """ChoiceLabel icons/descriptions render inside grouped options."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            (
                "Europe",
                [
                    (
                        "ldn",
                        ChoiceLabel("London", icon="\U0001f1ec\U0001f1e7", description="UK capital"),
                    ),
                ],
            ),
        ],
    )
    soup = render_widget(widget, attrs={"id": "id_city"})
    button = soup.find("button", attrs={"data-value": "ldn"})
    assert button is not None
    assert "London" in button.get_text()
    assert "UK capital" in button.get_text()
    assert "\U0001f1ec\U0001f1e7" in button.decode()


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_search_select_renders_via_form(renderer):
    """A FormworkForm field renders the SearchSelect hidden value input."""
    form = SearchSelectForm()
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "city"})
    assert hidden is not None


@pytest.mark.integration
def test_search_select_form_wraps_in_fieldset(renderer):
    """Field template wraps the SearchSelect in a fieldset with a stable id."""
    form = SearchSelectForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_city_field")
    assert fieldset is not None


@pytest.mark.integration
def test_search_select_form_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the summary."""
    form = SearchSelectForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary is not None
    assert summary.get("aria-invalid") == "true"


@pytest.mark.integration
def test_search_select_form_error_state_aria_describedby(renderer):
    """Django's auto aria-describedby (→ the error container) reaches the summary."""
    form = SearchSelectForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary.get("aria-describedby") == "id_city_error"


@pytest.mark.integration
def test_search_select_form_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = SearchSelectForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_city_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_search_select_form_prefix_handling(renderer):
    """Form prefix propagates to the hidden input name and widget id."""
    form = SearchSelectForm(prefix="loc")
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "loc-city"})
    assert hidden is not None
    assert hidden["id"] == "id_loc-city"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_search_select_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """SearchSelect produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(SearchSelectForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SearchSelectForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_search_select_grouped_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Grouped SearchSelect produces equivalent HTML via DTL and Jinja2."""

    class GroupedForm(FormworkForm):
        city = forms.ChoiceField(
            choices=[
                ("", ""),
                ("Europe", [("ldn", "London"), ("par", "Paris")]),
                ("Asia", [("tyo", "Tokyo")]),
            ],
            widget=SearchSelect,
            required=False,
        )

    soup_dtl = render_form(GroupedForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(GroupedForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


@pytest.mark.integration
def test_search_select_selected_toggle_class_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """selected_toggle_class renders identically via DTL and Jinja2 (root + option attrs)."""

    class PriorityForm(FormworkForm):
        priority = forms.ChoiceField(
            choices=[
                ("", ""),
                ("low", ChoiceLabel("Low", selected_toggle_class="select-success")),
                ("high", ChoiceLabel("High", selected_toggle_class="select-error")),
            ],
            widget=SearchSelect,
            required=False,
        )

    # Bound with "high" so the root data attr and the option attrs both render.
    soup_dtl = render_form(PriorityForm({"priority": "high"}), renderer=dtl_renderer)
    soup_jinja2 = render_form(PriorityForm({"priority": "high"}), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 4b: Escaping regressions (both engines) ───────────────────────


class RoundTripSearchSelectForm(FormworkForm):
    """Form whose choice value and label contain characters escapejs mangles."""

    supplier = forms.ChoiceField(
        choices=[("uuid-1234", "O'Brien & Sons")],
        widget=SearchSelect,
        required=False,
    )


@pytest.mark.integration
def test_search_select_option_data_attrs_round_trip_raw(renderer):
    """Regression: escapejs on data-value/data-label mangled values the JS reads raw via dataset."""
    soup = render_form(RoundTripSearchSelectForm(), renderer=renderer)
    btn = soup.find("button", attrs={"data-value": "uuid-1234"})
    assert btn is not None
    assert btn["data-label"] == "O'Brien & Sons"


@pytest.mark.integration
def test_search_select_checkmark_literal_decodes_to_data_value(renderer):
    """The Alpine :class comparison literal decodes to the raw data-value string."""
    soup = render_form(RoundTripSearchSelectForm(), renderer=renderer)
    btn = soup.find("button", attrs={"data-value": "uuid-1234"})
    check = btn.find("span", class_="formwork-check")
    literal = re.search(r"value === '(.*)' &&", check[":class"]).group(1)
    assert json.loads(f'"{literal}"') == btn["data-value"]


@pytest.mark.integration
def test_search_select_data_icon_escaped_under_both_engines(renderer):
    """Regression: Jinja2's |e honors __html__, leaving mark_safe icon SVG raw inside data-icon."""
    icon = '<img src="a.svg">'

    class IconForm(FormworkForm):
        lang = forms.ChoiceField(
            choices=[("a", ChoiceLabel("Alpha", icon=mark_safe(icon)))],  # noqa: S308
            widget=SearchSelect,
            required=False,
        )

    soup = render_form(IconForm({"lang": "a"}), renderer=renderer)
    details = soup.find("details", class_="search-select")
    assert details["data-icon"] == icon
    btn = soup.find("button", attrs={"data-value": "a"})
    assert btn["data-icon"] == icon


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


def _open_dropdown(page, index):
    """Open the nth SearchSelect on the page like a summary click (open + toggle event)."""
    page.evaluate(
        """(i) => {
            const dd = document.querySelectorAll('details.dropdown.search-select')[i];
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""",
        index,
    )


def _focus_search(page, index):
    """Focus the nth SearchSelect's search input, firing its htmx focus trigger."""
    page.evaluate(
        """(i) => {
            const search = document.querySelectorAll('details.dropdown.search-select')[i]
                .querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""",
        index,
    )


def _type_search(page, index, text):
    """Set the nth SearchSelect's search input value, firing its input handlers."""
    page.evaluate(
        """([i, text]) => {
            const search = document.querySelectorAll('details.dropdown.search-select')[i]
                .querySelector('.dropdown-content input[type="text"]');
            search.value = text;
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""",
        [index, text],
    )


def _search_response(page):
    """Context manager waiting for a formwork search endpoint response."""
    return page.expect_response(lambda r: "/__formwork__/search/" in r.url, timeout=10000)


@pytest.mark.e2e
def test_search_select_renders_on_page(search_select_page):
    """SearchSelect is visible on the /search-select/ page."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_open_close_dropdown(search_select_page):
    """Clicking the summary trigger opens the dropdown; clicking again closes it."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    summary = sel.locator("summary")
    summary.click()
    search_select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is not None
    summary.click()
    search_select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_search_select_no_search_input_with_few_options(search_select_page):
    """Search input is hidden when option count is below threshold."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    _open_dropdown(search_select_page, 0)
    search_select_page.wait_for_timeout(200)
    search_wrapper = sel.locator(".dropdown-content > div").first
    assert not search_wrapper.is_visible()


@pytest.mark.e2e
def test_search_select_pick_option_sets_value(search_select_page):
    """Clicking an option sets the hidden input value."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(search_select_page, 0)
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    search_select_page.wait_for_timeout(100)
    assert hidden.input_value() == "ldn"


@pytest.mark.e2e
def test_search_select_pick_closes_dropdown(search_select_page):
    """Picking an option closes the dropdown and updates the summary label."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    summary = sel.locator("summary")
    summary.click()
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    search_select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None
    assert "London" in summary.text_content()


@pytest.mark.e2e
def test_search_select_wrapper_has_id(search_select_page):
    """The details wrapper element has a stable id ending in '_searchselect'."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    el_id = sel.get_attribute("id")
    assert el_id is not None
    assert "_searchselect" in el_id


@pytest.mark.e2e
def test_search_select_many_search_input_shown(search_select_page):
    """Search input is visible when option count is at or above threshold."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    _open_dropdown(search_select_page, 1)
    search_select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="text"]')
    assert search.count() == 1


@pytest.mark.e2e
def test_search_select_many_filters_options(search_select_page):
    """Typing in the search input filters the visible options."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    _open_dropdown(search_select_page, 1)
    search_select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.fill("Jap")
    search_select_page.wait_for_timeout(100)
    assert sel.locator("button", has_text="Japan").is_visible()
    assert not sel.locator("button", has_text="Brazil").is_visible()


@pytest.mark.e2e
def test_search_select_many_pick_option_sets_value(search_select_page):
    """Picking an option from the many-options list sets the correct value."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(search_select_page, 1)
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Germany").click()
    search_select_page.wait_for_timeout(100)
    assert hidden.input_value() == "de"


@pytest.mark.e2e
def test_search_select_icons_renders(search_select_page):
    """SearchSelect with icons (third dropdown) renders visibly."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(2)
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_icons_pick_shows_label_in_summary(search_select_page):
    """After picking an icon-option, the label appears in the summary."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(2)
    summary = sel.locator("summary")
    _open_dropdown(search_select_page, 2)
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="New York").click()
    search_select_page.wait_for_timeout(100)
    assert "New York" in summary.text_content()


@pytest.mark.e2e
def test_search_select_selected_toggle_class_applied_on_pick(search_select_page):
    """Picking a priority option moves its class onto the closed trigger, no round-trip.

    The priority dropdown is the 9th SearchSelect on the page (nth(8)); it is
    appended last precisely so it does not shift the other dropdowns' indices.
    """
    sel = search_select_page.locator("details.dropdown.search-select").nth(8)
    summary = sel.locator("summary")
    # Nothing selected yet: the trigger carries none of the priority classes.
    assert "select-error" not in (summary.get_attribute("class") or "")
    summary.click()
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    search_select_page.wait_for_timeout(100)
    assert sel.get_attribute("open") is None
    assert "High" in summary.text_content()
    classes = (summary.get_attribute("class") or "").split()
    assert "select-error" in classes
    assert "false" not in classes, "falsy :class array entry stringified into a literal token"


@pytest.mark.e2e
def test_search_select_selected_toggle_class_swaps_between_options(search_select_page):
    """Re-picking swaps the trigger class: the previous option's class is removed."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(8)
    summary = sel.locator("summary")
    summary.click()
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    search_select_page.wait_for_timeout(100)
    assert "select-error" in (summary.get_attribute("class") or "")
    summary.click()
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Low").click()
    search_select_page.wait_for_timeout(100)
    cls = summary.get_attribute("class") or ""
    assert "select-success" in cls
    assert "select-error" not in cls


@pytest.mark.e2e
def test_search_select_htmx_renders(search_select_page):
    """SearchSelect with htmx search (fourth dropdown) renders visibly."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_htmx_open_loads_results(search_select_page):
    """Opening the htmx search dropdown loads results from the server."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    _open_dropdown(search_select_page, 3)
    search_select_page.wait_for_timeout(200)
    with _search_response(search_select_page):
        _focus_search(search_select_page, 3)
    expect(sel.locator("ul button")).to_have_count(4, timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_filters_via_htmx(search_select_page):
    """Typing in the htmx search input triggers a server request and filters results."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    _open_dropdown(search_select_page, 3)
    search_select_page.wait_for_timeout(200)
    with _search_response(search_select_page):
        _focus_search(search_select_page, 3)
    expect(sel.locator("ul button")).to_have_count(4, timeout=10000)
    _type_search(search_select_page, 3, "Tok")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    assert "Tokyo" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_search_select_htmx_pick_sets_value(search_select_page):
    """Clicking an htmx result button sets the hidden input value."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(search_select_page, 3)
    search_select_page.wait_for_timeout(200)
    with _search_response(search_select_page):
        _focus_search(search_select_page, 3)
    _type_search(search_select_page, 3, "Lon")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    sel.locator("ul button", has_text="London").click()
    search_select_page.wait_for_timeout(200)
    assert hidden.input_value() == "ldn"


@pytest.mark.e2e
def test_search_select_htmx_no_results_message(search_select_page):
    """A 'No results' item appears when the htmx search finds nothing."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    _open_dropdown(search_select_page, 3)
    search_select_page.wait_for_timeout(200)
    with _search_response(search_select_page):
        _focus_search(search_select_page, 3)
    expect(sel.locator("ul button")).to_have_count(4, timeout=10000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        htmx.ajax('GET', search.getAttribute('hx-get') + '?q=zzzzz&type=search_select', {
            target: search.getAttribute('hx-target'),
            swap: 'innerHTML',
        });
    }""")
    no_results = sel.locator("li", has_text="No results")
    expect(no_results).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_many_open_loads_all(search_select_page):
    """Opening the htmx-many dropdown (nth=4) loads all 24 results."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    _open_dropdown(search_select_page, 4)
    buttons = sel.locator("ul button")
    expect(buttons).to_have_count(24, timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_many_search_input_shown_above_threshold(search_select_page):
    """Search input is visible after htmx loads because total (24) >= threshold (20)."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    _open_dropdown(search_select_page, 4)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_many_filters_via_htmx(search_select_page):
    """Htmx-many: typing a search term filters down to matching options."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    with _search_response(search_select_page):
        _open_dropdown(search_select_page, 4)
    _type_search(search_select_page, 4, "Ber")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    assert "Berlin" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_search_select_htmx_icons_renders(search_select_page):
    """Htmx-icons dropdown (nth=5) renders visibly."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_htmx_icons_loads_results(search_select_page):
    """Htmx-icons: opening loads all 31 country results."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    _open_dropdown(search_select_page, 5)
    buttons = sel.locator("ul button")
    expect(buttons).to_have_count(31, timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_icons_search_input_shown(search_select_page):
    """Htmx-icons: search input is visible because total >= search_threshold."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    _open_dropdown(search_select_page, 5)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_search_select_htmx_icons_results_have_icons(search_select_page):
    """Htmx-icons: each option button has an icon span."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    _open_dropdown(search_select_page, 5)
    first_button = sel.locator("ul button").first
    expect(first_button).to_be_visible(timeout=10000)
    icon_span = first_button.locator("span.shrink-0").first
    assert icon_span.text_content().strip() != ""


@pytest.mark.e2e
def test_search_select_htmx_icons_results_have_descriptions(search_select_page):
    """Htmx-icons: each option button has a description span."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    _open_dropdown(search_select_page, 5)
    descs = sel.locator("ul button span.text-xs")
    expect(descs.first).to_be_visible(timeout=10000)
    assert descs.first.text_content().strip() != ""


@pytest.mark.e2e
def test_search_select_htmx_icons_filters(search_select_page):
    """Htmx-icons: search term filters down to one matching country."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    with _search_response(search_select_page):
        _open_dropdown(search_select_page, 5)
    _type_search(search_select_page, 5, "Jap")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    assert "Japan" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_search_select_htmx_icons_pick_sets_value(search_select_page):
    """Htmx-icons: picking an option sets the correct hidden input value."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    hidden = sel.locator('input[type="hidden"][name]')
    with _search_response(search_select_page):
        _open_dropdown(search_select_page, 5)
    sel.locator("ul button", has_text="France").click()
    search_select_page.wait_for_timeout(200)
    assert hidden.input_value() == "fr"


# ─── Level 5b: E2e, grouped (optgroup) SearchSelect ─────────────────────
#
# city_grouped is the 7th SearchSelect on the page (nth(6)).


@pytest.mark.e2e
def test_search_select_grouped_shows_headers(search_select_page):
    """Open the grouped SearchSelect; all three group headers are visible."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(6)
    _open_dropdown(search_select_page, 6)
    search_select_page.wait_for_timeout(200)

    headers = sel.locator("li.menu-title")
    assert headers.count() == 3
    visible_texts = [h.inner_text().strip() for h in headers.all() if h.is_visible()]
    assert visible_texts == ["Europe", "Asia", "Americas"]


@pytest.mark.e2e
def test_search_select_grouped_search_hides_empty_groups(search_select_page):
    """Typing 'lon' hides Asia and Americas headers (no children match)."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(6)
    _open_dropdown(search_select_page, 6)
    search_select_page.wait_for_timeout(200)

    _type_search(search_select_page, 6, "lon")
    search_select_page.wait_for_timeout(200)

    visible_headers = [h.inner_text().strip() for h in sel.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Europe"]


# ─── Level 5c: E2e, search auto-focus ───────────────────────────────────
#
# The second SearchSelect (city_many) has 21 choices, above the default
# search threshold of 20, so it shows a search input.


@pytest.mark.e2e
def test_search_select_search_auto_focus_on_open(search_select_page):
    """Opening a SearchSelect with a search box auto-focuses the input."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    sel.locator("summary").click()
    search_select_page.wait_for_timeout(100)
    search = sel.locator('.dropdown-content input[type="text"]')
    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_search_select_search_refocus_on_reopen(search_select_page):
    """Closing then reopening a search-enabled SearchSelect re-focuses the input."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    sel.locator("summary").click()
    search_select_page.wait_for_timeout(100)
    sel.locator("summary").click()  # close
    search_select_page.wait_for_timeout(100)
    sel.locator("summary").click()  # reopen
    search_select_page.wait_for_timeout(100)
    search = sel.locator('.dropdown-content input[type="text"]')
    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_search_select_no_search_no_focus_error(search_select_page):
    """Opening a search-less SearchSelect does not raise any console error."""
    errors: list[str] = []
    search_select_page.on("pageerror", lambda e: errors.append(str(e)))

    sel = search_select_page.locator("details.dropdown.search-select").first
    sel.locator("summary").click()
    search_select_page.wait_for_timeout(150)
    assert errors == []


# ─── Level 5d: E2e, keyboard navigation ─────────────────────────────────
#
# Uses the grouped SearchSelect (nth(6)) which has 9 fixed-size options
# in 3 groups and a search input.  Keyboard handlers are on the <details>
# root; the search input is auto-focused on open so events bubble up.


@pytest.mark.e2e
def test_search_select_keyboard_arrowdown_highlights_first(search_select_page):
    """ArrowDown highlights the first visible option."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.press("ArrowDown")
    search_select_page.wait_for_timeout(50)
    highlighted = sel.locator("[data-value].highlighted")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_search_select_keyboard_arrowdown_navigates(search_select_page):
    """Each ArrowDown moves to the next option, skipping group headers."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    for _ in range(3):  # ldn, par, ber
        search.press("ArrowDown")
    search.press("ArrowDown")  # tyo (next group)
    search_select_page.wait_for_timeout(50)
    assert sel.locator("[data-value].highlighted").first.get_attribute("data-value") == "tyo"


@pytest.mark.e2e
def test_search_select_keyboard_arrowdown_wraps_to_first(search_select_page):
    """ArrowDown past the last option wraps to the first."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    for _ in range(10):  # 9 + 1 wrap
        search.press("ArrowDown")
    search_select_page.wait_for_timeout(50)
    assert sel.locator("[data-value].highlighted").first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_search_select_keyboard_arrowup_wraps_to_last(search_select_page):
    """ArrowUp from no highlight goes to the last visible option."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.press("ArrowUp")
    search_select_page.wait_for_timeout(50)
    assert sel.locator("[data-value].highlighted").first.get_attribute("data-value") == "mex"


@pytest.mark.e2e
def test_search_select_keyboard_filter_skips_hidden_options(search_select_page):
    """After filtering, ArrowDown only highlights visible (matching) options."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.fill("lon")  # Matches only "London"
    search_select_page.wait_for_timeout(150)
    search.press("ArrowDown")
    search.press("ArrowDown")  # Wrap around (only one visible)
    search_select_page.wait_for_timeout(50)
    highlighted = sel.locator("[data-value].highlighted")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_search_select_keyboard_enter_picks_and_closes(search_select_page):
    """Enter on highlighted option sets value and closes the dropdown."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.press("ArrowDown")  # ldn
    search.press("ArrowDown")  # par
    search.press("Enter")
    search_select_page.wait_for_timeout(150)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "par"
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_search_select_keyboard_enter_no_highlight_picks_first(search_select_page):
    """With no highlight, Enter picks the first visible option."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.fill("tok")
    search_select_page.wait_for_timeout(150)
    search.press("Enter")
    search_select_page.wait_for_timeout(150)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "tyo"


@pytest.mark.e2e
def test_search_select_keyboard_close_clears_highlight(search_select_page):
    """Closing the dropdown via summary click clears ``.highlighted``."""
    sel = open_dropdown(search_select_page, "search-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.press("ArrowDown")
    search_select_page.wait_for_timeout(50)
    assert sel.locator("[data-value].highlighted").count() == 1
    sel.locator("summary").click()
    search_select_page.wait_for_timeout(150)
    assert sel.locator("[data-value].highlighted").count() == 0


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Gap: /search-select/ has only required=False fields, so an e2e error-flow
# test needs a page with a required SearchSelect, which does not exist yet.


# ─── Level 6b: E2e, server-side search loading + failure UX ─────────────
#
# Skeleton placeholders show on first full page load before the first
# focus-triggered htmx request swaps in real options.  When the search
# endpoint fails, an error alert replaces the listbox while the search
# input stays usable so the user can retry.
#
# Indices on /search-select/:  3 = city_htmx (working),
#                              7 = city_failing (slow + always 500).


@pytest.mark.e2e
def test_search_select_prerenders_options_on_initial_load(search_select_page):
    """Real options render in every htmx-mode SearchSelect on first page load, before any user
    interaction, with no skeleton flicker. The dropdown at index 3 wires up
    ``search_choices_city_htmx`` against ``E2E_CITIES`` (4 cities), so all 4 options are baked in."""
    htmx_dropdown = search_select_page.locator("details.dropdown.search-select").nth(3)
    items = htmx_dropdown.locator("ul[role='listbox'] > li[role='option']")
    assert items.count() == 4


@pytest.mark.e2e
def test_search_select_options_refresh_on_first_focus(search_select_page):
    """First focus fires htmx; the swap replaces pre-rendered options with
    the fresh response: same count, same listbox."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    _open_dropdown(search_select_page, 3)
    expect(sel.locator("ul button")).to_have_count(4, timeout=10000)


@pytest.mark.e2e
def test_search_select_failing_search_shows_error_alert(search_select_page):
    """When the search endpoint returns 500, the error alert appears in
    place of the listbox and the alert carries the failure message."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(7)
    _open_dropdown(search_select_page, 7)
    search_select_page.wait_for_timeout(200)
    _focus_search(search_select_page, 7)
    alert = sel.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    assert "Search failed" in alert.text_content()
    expect(sel.locator("ul[role='listbox']")).to_be_hidden()


@pytest.mark.e2e
def test_search_select_search_input_works_after_error(search_select_page):
    """The search input remains usable after a failure; typing fires a new
    request and the value lands in the input."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(7)
    requests: list[str] = []
    search_select_page.on("request", lambda r: requests.append(r.url) if "search/" in r.url else None)
    _open_dropdown(search_select_page, 7)
    alert = sel.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    initial_count = len(requests)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[7].querySelector('.dropdown-content input[type="text"]');
        search.focus();
        search.value = 'x';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    # 300ms input-changed debounce + buffer for the request to fire.
    search_select_page.wait_for_timeout(500)
    assert len(requests) > initial_count, "expected typing to fire a new search request"
    val = search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        return dds[7].querySelector('.dropdown-content input[type="text"]').value;
    }""")
    assert val == "x"


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_search_select_morph_preserves_value(search_select_page):
    """Selected value survives an htmx form morph."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    search_select_page.evaluate("""
        document.querySelector('details.dropdown.search-select').open = true;
    """)
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    search_select_page.wait_for_timeout(200)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "ldn"
    submit(search_select_page)
    hidden = search_select_page.locator(
        "details.dropdown.search-select input[type='hidden']",
    ).first
    assert hidden.input_value() == "ldn"
    summary = search_select_page.locator(
        "details.dropdown.search-select summary",
    ).first
    assert "London" in summary.text_content()


@pytest.mark.e2e
def test_search_select_morph_preserves_dropdown_closed(search_select_page):
    """Closed dropdown stays closed after a morph."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    search_select_page.evaluate("""
        document.querySelector('details.dropdown.search-select').open = true;
    """)
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Tokyo").click()
    search_select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None
    submit(search_select_page)
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_search_select_morph_preserves_dropdown_open(search_select_page):
    """Open dropdown stays open after a morph."""
    search_select_page.evaluate("""
        document.querySelector('details.dropdown.search-select').open = true;
    """)
    search_select_page.wait_for_timeout(200)
    search_select_page.evaluate("""
        document.querySelector('form[hx-post]').noValidate = true;
        document.querySelector('form[hx-post] button[type="submit"]').click();
    """)
    search_select_page.wait_for_timeout(500)
    sel = search_select_page.locator("details.dropdown.search-select").first
    assert sel.get_attribute("open") is not None


@pytest.mark.e2e
def test_search_select_toggle_class_survives_noop_morph(search_select_page):
    """Alpine-applied trigger classes survive a no-op morph.

    A re-render of already-saved state changes no data attributes, so nothing
    re-evaluates the :class binding; the morph itself must keep the classes.
    """
    sel = search_select_page.locator("details.dropdown.search-select").nth(8)
    summary = sel.locator("summary")
    summary.click()
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    search_select_page.wait_for_timeout(100)
    assert "select-error" in (summary.get_attribute("class") or "")
    submit(search_select_page)
    assert "select-error" in (summary.get_attribute("class") or "")
    submit(search_select_page)
    classes = (summary.get_attribute("class") or "").split()
    assert "select-error" in classes
    assert "false" not in classes


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_search_select_screenshot_default(search_select_page, assert_screenshot):
    """Visual snapshot: SearchSelect in default (closed) state."""
    wrapper = search_select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-default.png")


@pytest.mark.screenshot
def test_search_select_screenshot_open(search_select_page, assert_screenshot):
    """Visual snapshot: SearchSelect with dropdown open."""
    search_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.search-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    wrapper = search_select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_search_select_screenshot_selected(search_select_page, assert_screenshot):
    """Visual snapshot: SearchSelect with an option selected."""
    search_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.search-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_select_page.locator("details.dropdown.search-select").first.locator("button", has_text="London").click()
    search_select_page.wait_for_timeout(100)
    wrapper = search_select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-selected.png")


@pytest.mark.screenshot
def test_search_select_screenshot_selected_toggle_class(search_select_page, assert_screenshot):
    """Visual snapshot: priority SearchSelect trigger recolored by the picked option."""
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        // The top-layer panel tracks its trigger; Playwright can't scroll
        // a fixed element into view, so the trigger must be visible first.
        dds[8].scrollIntoView({block: 'center'});
        dds[8].open = true;
        dds[8].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    sel = search_select_page.locator("details.dropdown.search-select").nth(8)
    sel.locator("button", has_text="High").click()
    search_select_page.wait_for_timeout(100)
    wrapper = search_select_page.locator("#id_priority_field")
    assert_screenshot(wrapper, "search-select-selected-toggle-class.png")


@pytest.mark.screenshot
def test_search_select_screenshot_grouped_open(search_select_page, assert_screenshot):
    """Visual snapshot: grouped SearchSelect with dropdown open showing optgroup headers."""
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[6].open = true;
        dds[6].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    wrapper = search_select_page.locator("#id_city_grouped_field")
    assert_screenshot(wrapper, "search-select-grouped-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_search_select_screenshot_keyboard_highlighted(search_select_page, assert_screenshot):
    """Visual snapshot: SearchSelect with an option highlighted via keyboard."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(6)
    sel.locator("summary").click()
    search_select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="text"]')
    search.press("ArrowDown")  # Highlight ldn
    search_select_page.wait_for_timeout(50)
    wrapper = search_select_page.locator("#id_city_grouped_field")
    assert_screenshot(wrapper, "search-select-keyboard-highlighted.png", capture_dropdown=True)
