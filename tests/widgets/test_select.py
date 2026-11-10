"""Select tests, ordered unit, integration, e2e, screenshot; filter levels with -m."""

from __future__ import annotations

import re

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork import ChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.search import SEARCH_PAGE_SIZE
from django_formwork.widgets import ComboBox, Select

from .conftest import open_dropdown, render_form, render_widget, server_widget, submit


class SelectForm(FormworkForm):
    """Local form fixture for Select integration tests."""

    city = forms.ChoiceField(
        widget=Select(choices=[("nyc", "New York"), ("ldn", "London")]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_select_default_choices_empty():
    """Select can be instantiated with no choices."""
    widget = Select()
    assert list(widget.choices) == []


@pytest.mark.unit
def test_select_accepts_choices():
    """Choices passed to constructor are stored on the widget."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    vals = [v for v, _label in widget.choices]
    assert "a" in vals
    assert "b" in vals


@pytest.mark.unit
def test_select_show_search_default_none():
    """show_search defaults to None (auto-detect from threshold)."""
    widget = Select(choices=[("a", "Alpha")])
    assert widget.show_search is None


@pytest.mark.unit
def test_select_show_search_explicit_true():
    """Explicit show_search=True is stored on the widget."""
    widget = Select(choices=[("a", "Alpha")], show_search=True)
    assert widget.show_search is True


@pytest.mark.unit
def test_select_show_search_explicit_false():
    """Explicit show_search=False is stored on the widget."""
    widget = Select(choices=[("a", "Alpha")], show_search=False)
    assert widget.show_search is False


@pytest.mark.unit
def test_select_get_context_selected_label():
    """get_context returns the label for the selected value."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", "a", {})
    assert ctx["widget"]["selected_label"] == "Alpha"


@pytest.mark.unit
def test_select_get_context_selected_label_empty_when_no_value():
    """selected_label is empty string when value is the empty option."""
    widget = Select(choices=[("", ""), ("a", "Alpha")])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["selected_label"] == ""


@pytest.mark.unit
def test_select_get_context_search_url_set_past_one_page():
    """A registered search with more choices than one page names its endpoint."""
    widget = server_widget(Select)
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"].startswith("/__formwork__/search/")


@pytest.mark.unit
def test_select_registered_search_that_fits_one_page_filters_in_the_browser():
    """A registered search whose choices fit one page renders every row and no endpoint."""
    widget = server_widget(Select, count=SEARCH_PAGE_SIZE)
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None
    assert len(ctx["widget"]["options"]) == SEARCH_PAGE_SIZE


@pytest.mark.unit
def test_select_get_context_search_url_none_when_unregistered():
    """search_url in context is None when no registry entry is attached."""
    widget = Select(choices=[("a", "Alpha")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_select_get_context_show_search_false_at_threshold():
    """show_search is False when choice count equals search_threshold (10)."""
    widget = Select(choices=[(str(i), f"Option {i}") for i in range(10)])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is False


@pytest.mark.unit
def test_select_get_context_show_search_true_past_threshold():
    """show_search is True when choice count > search_threshold (10)."""
    choices = [(str(i), f"Option {i}") for i in range(11)]
    widget = Select(choices=choices)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_select_get_context_show_search_explicit_overrides():
    """Explicit show_search=True overrides the threshold check."""
    widget = Select(choices=[("a", "Alpha")], show_search=True)
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_select_get_context_optgroups_with_icons():
    """Icons from ChoiceLabel are injected into optgroups."""
    widget = Select(
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
def test_select_value_from_datadict_present():
    """value_from_datadict returns the submitted value from POST data."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    data = QueryDict("city=b")
    result = widget.value_from_datadict(data, {}, "city")
    assert result == "b"


@pytest.mark.unit
def test_select_value_from_datadict_missing():
    """value_from_datadict returns None when the key is absent."""
    widget = Select(choices=[("a", "Alpha")])
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "city")
    assert result is None


@pytest.mark.unit
def test_select_no_icons_kwarg():
    """Select takes icons from ChoiceLabel, not an icons kwarg."""
    with pytest.raises(TypeError):
        Select(choices=[("a", "Alpha")], icons={"a": "icon"})


@pytest.mark.unit
def test_select_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = Select(choices=[("a", "A")])
    ctx = widget.get_context("field", None, {"id": "id_field"})
    assert ctx["widget"]["name"] == "field"


@pytest.mark.unit
def test_select_renders_without_id():
    """Widget renders without an id attribute."""
    widget = Select(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="field", attrs={})
    details = soup.find("details")
    assert details is not None


@pytest.mark.unit
def test_select_optgroup_rendering():
    """Grouped choices render all options from all groups."""
    choices = [
        ("Europe", [("ldn", "London"), ("par", "Paris")]),
        ("Asia", [("tyo", "Tokyo")]),
    ]
    widget = Select(choices=choices)
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    buttons = soup.find_all("button")
    text = " ".join(btn.get_text() for btn in buttons)
    assert "London" in text
    assert "Paris" in text
    assert "Tokyo" in text


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_select_renders_details_dropdown():
    """Widget renders a <details class='dropdown'> wrapper."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", class_="dropdown")
    assert wrapper is not None


@pytest.mark.unit
def test_select_class_on_wrapper():
    """Widget wrapper also has the 'formwork-select' class."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", class_="formwork-select")
    assert wrapper is not None


@pytest.mark.unit
def test_select_renders_summary_trigger():
    """The trigger is a <summary> with text-left class (DaisyUI .select via @apply)."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    summary = soup.find("summary")
    assert summary is not None
    assert "text-left" in summary.get("class", [])


@pytest.mark.unit
def test_select_renders_hidden_value_input():
    """Widget renders a hidden <input> that submits the selected value."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden is not None
    assert hidden["name"] == "test"


@pytest.mark.unit
def test_select_hidden_input_has_id():
    """The summary takes the widget id; the hidden input gets ``{id}_value``."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_city"})
    hidden = soup.find("input", {"type": "hidden"})
    assert hidden["id"] == "id_city_value"
    assert soup.find("summary")["id"] == "id_city"


@pytest.mark.unit
def test_select_renders_dropdown_content():
    """Widget renders a <div class='dropdown-content'>."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    assert dropdown is not None


@pytest.mark.unit
def test_select_options_as_buttons():
    """Each non-empty choice is rendered as a <button type='button'>."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    buttons = soup.select("button[type=button][data-value]")
    assert len(buttons) == 2


@pytest.mark.unit
def test_select_option_labels_rendered():
    """Option button labels appear in the rendered HTML."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_select_empty_option_excluded():
    """The empty option (value='') is excluded from the dropdown button list."""
    widget = Select(choices=[("", "Select..."), ("a", "Alpha")])
    soup = render_widget(widget, name="test")
    buttons = soup.select("button[type=button][data-value]")
    assert len(buttons) == 1


@pytest.mark.unit
def test_select_alpine_x_data():
    """The wrapper <details> binds to the formworkSelect Alpine.data component."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", attrs={"x-data": "formworkSelect"})
    assert wrapper is not None


@pytest.mark.unit
def test_select_show_search_false_in_data_attr():
    """data-show-search is 'false' on the wrapper when below threshold."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    details = soup.find("details")
    assert details.get("data-show-search") == "false"


@pytest.mark.unit
def test_select_selected_label_in_data_attr():
    """Selected option label appears in data-label when value is pre-set."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test", value="b")
    wrapper = soup.find("details", attrs={"x-data": "formworkSelect"})
    assert wrapper["data-label"] == "Beta"
    assert wrapper["data-value"] == "b"


@pytest.mark.unit
def test_select_listbox_role():
    """The option list uses role='listbox' for accessibility."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert listbox is not None


@pytest.mark.unit
def test_select_ul_has_click_handler():
    """The listbox ul has an Alpine @click event handler for delegation."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    listbox = soup.find("ul", {"role": "listbox"})
    assert "@click" in str(listbox)


@pytest.mark.unit
def test_select_event_delegation_data_attrs():
    """Buttons carry data-value and data-label for event delegation."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    btn = soup.select_one("button[type=button][data-value]")
    assert btn["data-value"] == "a"
    assert btn["data-label"] == "Alpha"


@pytest.mark.unit
def test_select_no_results_alert():
    """A DaisyUI alert-info alert-soft is rendered under x-show='noResults'."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    alert = soup.find("div", attrs={"x-show": "noResults"}).find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert" in alert["class"]
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


# ─── Level 2b: Keyboard navigation scaffolding ───────────────────────────


@pytest.mark.unit
def test_select_keydown_handlers_on_wrapper():
    """The ``<details>`` wrapper has @keydown handlers for arrows and enter."""
    widget = Select(choices=[("a", "Alpha")])
    html = widget.render("test", "")
    assert "@keydown.arrow-down" in html
    assert "@keydown.arrow-up" in html
    assert "@keydown.enter" in html


@pytest.mark.unit
def test_select_xdata_binds_alpine_component():
    """Both client- and htmx-mode templates bind to the formworkSelect component."""
    plain = Select(choices=[("a", "A")]).render("test", "")
    htmx_mode = server_widget(Select).render("test", "")
    for html in (plain, htmx_mode):
        assert 'x-data="formworkSelect"' in html


@pytest.mark.unit
def test_select_keydown_invokes_nav_methods():
    """Keydown handlers call the component's nav and enter methods."""
    widget = Select(choices=[("a", "A")])
    html = widget.render("test", "")
    assert "onNav($event, 1)" in html
    assert "onNav($event, -1)" in html
    assert "onEnter($event)" in html


@pytest.mark.unit
def test_select_aria_invalid_on_summary():
    """aria-invalid='true' propagates to the summary trigger element."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    summary = soup.find("summary")
    assert summary["aria-invalid"] == "true"


@pytest.mark.unit
def test_select_no_aria_invalid_when_valid():
    """summary does not have aria-invalid when the widget has no errors."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-invalid")


@pytest.mark.unit
def test_select_aria_describedby_on_summary():
    """aria-describedby propagates to the summary trigger element."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-describedby": "id_test_helptext"})
    summary = soup.find("summary")
    assert summary["aria-describedby"] == "id_test_helptext"


@pytest.mark.unit
def test_select_no_aria_describedby_by_default():
    """summary does not have aria-describedby without help text or errors."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-describedby")


@pytest.mark.unit
def test_select_wrapper_has_stable_id():
    """details wrapper id is derived from the widget id."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select")
    assert details["id"] == "id_test_wrapper"


@pytest.mark.unit
def test_select_no_wrapper_id_without_attrs_id():
    """details wrapper has no id when no widget id is supplied."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="formwork-select")
    assert not details.has_attr("id")


@pytest.mark.unit
def test_select_htmx_wrapper_id():
    """details wrapper id is present even when search_url is set."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select")
    assert details["id"] == "id_test_wrapper"


@pytest.mark.unit
def test_select_search_input_inside_dropdown():
    """Search text input is rendered inside dropdown-content when show_search=True."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")], show_search=True)
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "search"})
    assert search is not None


@pytest.mark.unit
def test_select_htmx_attrs_when_registered():
    """Search input carries htmx attrs when the widget is attached to the registry."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "search"})
    assert search["hx-get"].startswith("/__formwork__/search/")
    assert search["hx-trigger"] == "input changed delay:300ms"
    assert search["hx-target"] == "next ul"
    assert search["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_select_no_htmx_attrs_without_search_url():
    """Search input does NOT have hx-get when no search_url is set."""
    widget = Select(choices=[("a", "Alpha")], show_search=True)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "search"})
    assert not search.has_attr("hx-get")


@pytest.mark.unit
def test_select_renders_no_results_alert_when_initial_options_empty():
    """An empty list still communicates state. The listbox carries
    the same ``role=status`` alert that the htmx response would render."""
    widget = Select(choices=[])
    soup = render_widget(widget, attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    alert = listbox.find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


@pytest.mark.unit
def test_select_no_alpine_no_results_when_search_url():
    """No 'No results' paragraph when search_url is set (server handles no results)."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_select_server_mode_renders_one_page_and_a_load_more_button():
    """Past one page the listbox holds the first page; "Load more" fetches the next."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    options = listbox.find_all("li", attrs={"role": "option"})
    assert [li.find("button")["data-value"] for li in options] == [str(i) for i in range(SEARCH_PAGE_SIZE)]
    more = listbox.select_one('[role="status"] button[hx-get]')
    assert f"offset={SEARCH_PAGE_SIZE}" in more["hx-get"]


@pytest.mark.unit
def test_select_server_mode_options_include_icons():
    """Server-mode rows keep the icon of their ChoiceLabel."""
    widget = server_widget(Select, icons=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"}).find("button")
    assert first.has_attr("data-icon")
    assert "📍0" in first.get_text()


@pytest.mark.unit
def test_select_server_mode_options_include_descriptions():
    """Server-mode rows keep the description of their ChoiceLabel."""
    widget = server_widget(Select, descriptions=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"})
    desc = first.find("span", class_="text-xs")
    assert desc is not None
    assert "desc 0" in desc.get_text()


@pytest.mark.unit
def test_select_client_mode_renders_every_choice():
    """Without server search the browser filters, so every choice is an option."""
    widget = Select(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None
    assert [o["value"] for o in ctx["widget"]["options"]] == ["a", "b"]


@pytest.mark.unit
def test_select_renders_error_alert_when_search_url():
    """The error alert is rendered as a plain DaisyUI alert, hidden by
    default via x-show='hasError'."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert is not None
    assert alert.get("x-show") == "hasError"
    assert "alert" in alert["class"]
    assert "alert-error" in alert["class"]
    assert "Search failed" in alert.get_text()


@pytest.mark.unit
def test_select_error_alert_hidden_until_a_search_fails():
    """The error alert waits on ``hasError``, which only a failed search sets."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert["x-show"] == "hasError"
    assert alert.has_attr("x-cloak")


@pytest.mark.unit
def test_select_root_wires_error_handlers():
    """The root hears both the search and "Load more"; only the search box sets the query.

    ``hasError`` follows the response only; resetting it on request would flash the old list.
    """
    widget = server_widget(Select)
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    root = soup.find("details", id="id_city_wrapper")
    assert "@htmx:before:request" not in root.attrs
    assert root["@htmx:before:swap"] == "onSearchBeforeSwap($event)"
    assert root["@htmx:response:error"] == "onSearchError()"
    assert root["@htmx:error"] == "onSearchError()"
    search = root.find("input", {"type": "search"})
    assert search["@htmx:config:request"] == "onSearchConfig($event)"
    assert "@htmx:before:swap" not in search.attrs


@pytest.mark.unit
def test_select_listbox_hidden_only_on_error():
    """The listbox stays visible at all times except when an error occurs;
    the spinner indicates loading without blanking the listbox."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", id="id_test_listbox")
    assert listbox.get("x-show") == "!hasError"


@pytest.mark.unit
def test_select_has_search_url_flag_when_search_url():
    """data-has-search-url is 'true' when server search is wired."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select")
    assert details["data-has-search-url"] == "true"


@pytest.mark.unit
def test_select_show_search_visible_from_first_render_in_server_mode():
    """A list past one page shows the search input from first paint."""
    widget = server_widget(Select)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select")
    assert details["data-show-search"] == "true"


@pytest.mark.unit
def test_select_show_search_hidden_when_count_below_threshold():
    """A registered search with few choices keeps the search input hidden."""
    widget = server_widget(Select, count=5)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select")
    assert details["data-show-search"] == "false"


@pytest.mark.unit
def test_select_icon_rendered_in_option():
    """ChoiceLabel icons appear in the rendered option buttons."""
    widget = Select(
        choices=[
            ("a", ChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_select_no_icon_element_when_not_provided():
    """No <img> elements rendered when no ChoiceLabel icons."""
    widget = Select(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


@pytest.mark.unit
def test_select_option_data_icon_attribute_escaped():
    """Icon HTML with quotes must not break the option's data-icon attribute.

    The button carries data-icon so the JS can restore the icon on select.
    Without escaping, the icon's quotes close the attribute early; the parsed
    value must round-trip to the full icon string.
    """
    icon = '<img src="a.svg">'
    widget = Select(choices=[("a", ChoiceLabel("Alpha", icon=mark_safe(icon)))])  # noqa: S308
    soup = render_widget(widget, name="test")
    button = soup.find("button", attrs={"data-value": "a"})
    assert button is not None
    assert button["data-icon"] == icon


# ─── Level 2c: selected_toggle_class (trigger recolor) ───────────────────


@pytest.mark.unit
def test_select_get_context_optgroups_with_selected_toggle_class():
    """selected_toggle_class from ChoiceLabel is injected into optgroups."""
    widget = Select(
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
def test_select_widget_selected_toggle_class_seeded_from_selection():
    """The preselected option's class is exposed at widget level so JS init seeds it."""
    widget = Select(
        choices=[
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
            ("b", ChoiceLabel("Beta", selected_toggle_class="select-success")),
        ],
    )
    ctx = widget.get_context("test", "b", {})
    assert ctx["widget"]["selected_toggle_class"] == "select-success"


@pytest.mark.unit
def test_select_widget_selected_toggle_class_empty_without_selection():
    """No selection → the widget-level class seed is empty."""
    widget = Select(choices=[("a", ChoiceLabel("Alpha", selected_toggle_class="select-error"))])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["selected_toggle_class"] == ""


@pytest.mark.unit
def test_select_option_data_selected_toggle_class_attribute():
    """Option buttons carry data-selected-toggle-class; the attribute is absent when empty."""
    widget = Select(
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
def test_select_root_data_selected_toggle_class_from_preselected():
    """The root <details> carries the selected option's class for JS init."""
    widget = Select(
        choices=[
            ("", ""),
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
        ],
    )
    soup = render_widget(widget, name="test", value="a", attrs={"id": "id_test"})
    details = soup.find("details")
    assert details["data-selected-toggle-class"] == "select-error"


@pytest.mark.unit
def test_select_summary_static_class_includes_selected_toggle_class():
    """A preselected option's toggle class is server-rendered on the summary, before Alpine runs."""
    widget = Select(
        choices=[
            ("", ""),
            ("a", ChoiceLabel("Alpha", selected_toggle_class="select-error")),
        ],
    )
    soup = render_widget(widget, name="test", value="a")
    assert "select-error" in soup.find("summary")["class"]


@pytest.mark.unit
def test_select_summary_static_placeholder_class_tracks_selection():
    """Without a selection the summary is server-rendered with formwork-placeholder; with one it is not."""
    widget = Select(choices=[("", ""), ("a", "Alpha")])
    empty = render_widget(widget, name="test")
    selected = render_widget(widget, name="test", value="a")
    assert "formwork-placeholder" in empty.find("summary")["class"]
    assert "formwork-placeholder" not in selected.find("summary")["class"]


@pytest.mark.unit
def test_select_selected_icon_server_rendered_without_cloak():
    """A preselected option's icon is server-rendered inside the trigger span, not x-cloaked."""
    widget = Select(
        choices=[("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>")))],
    )
    soup = render_widget(widget, name="test", value="a")
    span = soup.find("summary").find("span", attrs={"x-show": "icon"})
    assert span.find("svg") is not None
    assert not span.has_attr("x-cloak")


@pytest.mark.unit
def test_select_icon_span_cloaked_without_selection():
    """No selected icon → the trigger icon span stays empty and x-cloaked until Alpine decides."""
    widget = Select(
        choices=[("", ""), ("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>")))],
    )
    soup = render_widget(widget, name="test")
    span = soup.find("summary").find("span", attrs={"x-show": "icon"})
    assert span.has_attr("x-cloak")
    assert span.find("svg") is None


@pytest.mark.e2e
def test_select_trigger_takes_the_picked_option_class(select_page):
    """The closed trigger wears the picked option's class and drops the placeholder style."""
    import re

    from playwright.sync_api import expect

    trigger = select_page.locator("#id_priority")
    expect(trigger).to_have_class(re.compile(r"\bformwork-placeholder\b"))
    trigger.click()
    select_page.locator("#id_priority_listbox button[data-value='high']").click()
    expect(trigger).to_have_class(re.compile(r"\bselect-error\b"))
    expect(trigger).not_to_have_class(re.compile(r"\bformwork-placeholder\b"))
    trigger.click()
    select_page.locator("#id_priority_listbox button[data-value='low']").click()
    expect(trigger).to_have_class(re.compile(r"\bselect-success\b"))
    expect(trigger).not_to_have_class(re.compile(r"\bselect-error\b"))


@pytest.mark.unit
def test_select_option_data_selected_toggle_class_escaped():
    """A class string with a quote must not break the data attribute (plain autoescape suffices)."""
    widget = Select(choices=[("a", ChoiceLabel("Alpha", selected_toggle_class='c" x'))])
    soup = render_widget(widget, name="test")
    button = soup.find("button", attrs={"data-value": "a"})
    assert button["data-selected-toggle-class"] == 'c" x'


@pytest.mark.unit
def test_select_server_mode_options_include_selected_toggle_class():
    """Server-mode rows keep the selected_toggle_class of their ChoiceLabel."""
    widget = server_widget(Select, selected_toggle_classes=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li", attrs={"role": "option"}).find("button")
    assert first["data-selected-toggle-class"] == "select-error"


# ─── Level 2b: Optgroup rendering ────────────────────────────────────────


@pytest.mark.unit
def test_select_renders_group_headers():
    """Grouped choices produce <li class='menu-title'> headers per non-empty group."""
    widget = Select(
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
def test_select_no_group_headers_for_flat_choices():
    """Flat choices produce no menu-title headers."""
    widget = Select(choices=[("", ""), ("nyc", "New York"), ("ldn", "London")])
    soup = render_widget(widget, attrs={"id": "id_city"})
    assert soup.find_all("li", class_="menu-title") == []


@pytest.mark.unit
def test_select_group_header_precedes_its_rows():
    """A group heading is filtered by the rows after it, so its labels stay in the DOM."""
    widget = Select(
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
    assert europe["x-show"] == "matches($el)"
    assert europe.has_attr("data-group")
    rows = []
    for row in europe.find_next_siblings("li"):
        if row.has_attr("data-group"):
            break
        rows.append(row["data-label"])
    assert rows == ["London", "Paris", "Berlin"]


@pytest.mark.unit
def test_select_grouped_options_keep_icons_and_descriptions():
    """ChoiceLabel icons/descriptions render inside grouped options."""
    widget = Select(
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
def test_select_renders_via_form(renderer):
    """A FormworkForm field renders the Select hidden value input."""
    form = SelectForm()
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "city"})
    assert hidden is not None


@pytest.mark.integration
def test_select_form_wraps_in_fieldset(renderer):
    """Field template wraps the Select in a fieldset with a stable id."""
    form = SelectForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_city_field")
    assert fieldset is not None


@pytest.mark.integration
def test_select_form_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the summary."""
    form = SelectForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary is not None
    assert summary.get("aria-invalid") == "true"


@pytest.mark.integration
def test_select_form_error_state_aria_describedby(renderer):
    """Django's auto aria-describedby (→ the error container) reaches the summary."""
    form = SelectForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary.get("aria-describedby") == "id_city_error"


@pytest.mark.integration
def test_select_form_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = SelectForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_city_error", class_="tooltip-content")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.unit
def test_select_caller_attrs_reach_the_trigger_and_the_value():
    """Focus and naming attrs land on the trigger; data and htmx attrs on the input that posts and fires change."""
    attrs = {
        "autofocus": True,
        "title": "Pick one",
        "aria-roledescription": "picker",
        "data-row": "3",
        "hx-post": "/s/",
    }
    widget = Select(choices=[("a", "A")], attrs=attrs)
    soup = render_widget(widget, value="a", attrs={"id": "id_test"})
    summary = soup.select_one("summary")
    assert (summary["autofocus"], summary["title"], summary["aria-roledescription"]) == ("", "Pick one", "picker")
    hidden = soup.select_one("input[type=hidden]")
    assert (hidden["data-row"], hidden["hx-post"]) == ("3", "/s/")
    assert not summary.has_attr("hx-post")
    assert not hidden.has_attr("title")


@pytest.mark.unit
def test_select_disabled_trigger_keeps_out_of_the_tab_order():
    """A caller tabindex doesn't put a disabled trigger back in the tab order."""
    widget = Select(choices=[("a", "A")], attrs={"disabled": True, "tabindex": "3"})
    html = str(render_widget(widget, value="a"))
    assert html.count("tabindex=") == 1
    assert 'tabindex="-1"' in html


@pytest.mark.integration
def test_select_bound_value_no_option_holds_posts_blank(renderer):
    """A posted value the choices lack shows the placeholder, so it does not post again."""

    class CityForm(FormworkForm):
        city = forms.ChoiceField(choices=[("nyc", "New York"), ("ldn", "London")], widget=Select, required=False)

    form = CityForm(data={"city": "par"})
    assert not form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", {"type": "hidden", "name": "city"})["value"] == ""
    assert soup.find("details", class_="formwork-select")["data-value"] == ""


@pytest.mark.integration
def test_select_form_prefix_handling(renderer):
    """Form prefix propagates to the hidden input name and widget id."""
    form = SelectForm(prefix="loc")
    soup = render_form(form, renderer=renderer)
    hidden = soup.find("input", {"type": "hidden", "name": "loc-city"})
    assert hidden is not None
    assert hidden["id"] == "id_loc-city_value"


# ─── Level 4: Escaping regressions ──────────────────────────────────────


class RoundTripSelectForm(FormworkForm):
    """Form whose choice value and label contain characters escapejs mangles."""

    supplier = forms.ChoiceField(
        choices=[("uuid-1234", "O'Brien & Sons")],
        widget=Select,
        required=False,
    )


@pytest.mark.integration
def test_select_option_data_attrs_round_trip_raw(renderer):
    """Regression: escapejs on data-value/data-label mangled values the JS reads raw via dataset."""
    soup = render_form(RoundTripSelectForm(), renderer=renderer)
    btn = soup.find("button", attrs={"data-value": "uuid-1234"})
    assert btn is not None
    assert btn["data-label"] == "O'Brien & Sons"


@pytest.mark.unit
@pytest.mark.parametrize(
    "widget",
    [Select(choices=[("go", "Go"), ("zig", "Zig")]), ComboBox(suggestions=["Go", "Zig"])],
    ids=["select", "combo"],
)
def test_listbox_aria_selected_sits_on_the_option(widget):
    """Screen readers read aria-selected from the role=option element, not from a button inside it."""
    soup = render_widget(widget, name="language")
    options = soup.select("[role=option]")
    assert len(options) == 2
    assert all(li[":aria-selected"] == "isSelected($el)" for li in options)
    assert all("group/option" in li["class"] for li in options)
    assert not soup.select("button[\\:aria-selected]")


@pytest.mark.integration
def test_select_data_icon_escapes_safe_markup(renderer):
    """A mark_safe icon stays escaped inside the data-icon attribute."""
    icon = '<img src="a.svg">'

    class IconForm(FormworkForm):
        lang = forms.ChoiceField(
            choices=[("a", ChoiceLabel("Alpha", icon=mark_safe(icon)))],  # noqa: S308
            widget=Select,
            required=False,
        )

    soup = render_form(IconForm({"lang": "a"}), renderer=renderer)
    details = soup.find("details", class_="formwork-select")
    assert details["data-icon"] == icon
    btn = soup.find("button", attrs={"data-value": "a"})
    assert btn["data-icon"] == icon


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


def _open_dropdown(page, index):
    """Open the nth Select on the page like a summary click (open + toggle event)."""
    page.evaluate(
        """(i) => {
            const dd = document.querySelectorAll('details.dropdown.formwork-select')[i];
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""",
        index,
    )


def _type_search(page, index, text):
    """Set the nth Select's search input value, firing its input handlers."""
    page.evaluate(
        """([i, text]) => {
            const search = document.querySelectorAll('details.dropdown.formwork-select')[i]
                .querySelector('.dropdown-content input[type="search"]');
            search.value = text;
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""",
        [index, text],
    )


@pytest.mark.e2e
def test_select_renders_on_page(select_page):
    """Select is visible on the /select/ page."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    assert sel.is_visible()


@pytest.mark.e2e
def test_select_open_close_dropdown(select_page):
    """Clicking the summary trigger opens the dropdown; clicking again closes it."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    summary = sel.locator("summary")
    summary.click()
    select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is not None
    summary.click()
    select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None


def _click_summary(page, index):
    """Fire a genuine summary click whose event target is the summary, so
    @click.outside on the other dropdowns sees a real outside click.  A
    positional click can be blocked by an open panel overlapping a stacked
    neighbour, which is irrelevant to the open/close logic under test."""
    page.locator("details.dropdown.formwork-select").nth(index).locator("summary").evaluate("el => el.click()")
    page.wait_for_timeout(150)


@pytest.mark.e2e
def test_select_opening_another_closes_the_open_one(select_page):
    """Only one dropdown stays open at a time: opening a second closes the
    first, in both directions (regression: manual popovers used to leave both
    open)."""
    selects = select_page.locator("details.dropdown.formwork-select")
    _click_summary(select_page, 0)
    _click_summary(select_page, 1)
    assert selects.nth(0).get_attribute("open") is None
    assert selects.nth(1).get_attribute("open") is not None

    select_page.mouse.click(2, 2)
    select_page.wait_for_timeout(150)
    _click_summary(select_page, 1)
    _click_summary(select_page, 0)
    assert selects.nth(0).get_attribute("open") is not None
    assert selects.nth(1).get_attribute("open") is None


@pytest.mark.e2e
def test_select_click_outside_closes(select_page):
    """A click anywhere outside the dropdown closes it; a click inside its
    panel leaves it open."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    _click_summary(select_page, 1)
    assert sel.get_attribute("open") is not None

    sel.locator(".dropdown-content").evaluate("el => el.click()")
    select_page.wait_for_timeout(150)
    assert sel.get_attribute("open") is not None

    select_page.mouse.click(2, 2)
    select_page.wait_for_timeout(150)
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_select_no_search_input_with_few_options(select_page):
    """Search input is hidden when option count is below threshold."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    _open_dropdown(select_page, 0)
    select_page.wait_for_timeout(200)
    search_wrapper = sel.locator(".dropdown-content > div").first
    assert not search_wrapper.is_visible()


@pytest.mark.e2e
def test_select_pick_option_sets_value(select_page):
    """Clicking an option sets the hidden input value."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(select_page, 0)
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    select_page.wait_for_timeout(100)
    assert hidden.input_value() == "ldn"


@pytest.mark.e2e
def test_select_pick_closes_dropdown(select_page):
    """Picking an option closes the dropdown and updates the summary label."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    summary = sel.locator("summary")
    summary.click()
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None
    assert "London" in summary.text_content()


@pytest.mark.e2e
def test_select_wrapper_has_id(select_page):
    """The details wrapper element has a stable id ending in '_wrapper'."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    el_id = sel.get_attribute("id")
    assert el_id is not None
    assert el_id.endswith("_wrapper")


@pytest.mark.e2e
def test_select_many_search_input_shown(select_page):
    """Search input is visible when option count is at or above threshold."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    _open_dropdown(select_page, 1)
    select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="search"]')
    assert search.count() == 1


@pytest.mark.e2e
def test_select_many_filters_options(select_page):
    """Typing in the search input filters the visible options."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    _open_dropdown(select_page, 1)
    select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.fill("Jap")
    select_page.wait_for_timeout(100)
    assert sel.locator("button", has_text="Japan").is_visible()
    assert not sel.locator("button", has_text="Brazil").is_visible()


@pytest.mark.e2e
def test_select_search_clears_from_the_keyboard(select_page):
    """Enter on the clear button empties the search and brings the options back."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    _open_dropdown(select_page, 1)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.fill("Jap")
    expect(sel.locator("button", has_text="Brazil")).to_be_hidden()
    sel.get_by_role("button", name="Clear search").press("Enter")
    expect(search).to_have_value("")
    expect(sel.locator("button", has_text="Brazil")).to_be_visible()


@pytest.mark.e2e
def test_select_many_pick_option_sets_value(select_page):
    """Picking an option from the many-options list sets the correct value."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(select_page, 1)
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Germany").click()
    select_page.wait_for_timeout(100)
    assert hidden.input_value() == "de"


@pytest.mark.e2e
def test_select_icons_renders(select_page):
    """Select with icons (third dropdown) renders visibly."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(2)
    assert sel.is_visible()


@pytest.mark.e2e
def test_select_icons_pick_shows_label_in_summary(select_page):
    """After picking an icon-option, the label appears in the summary."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(2)
    summary = sel.locator("summary")
    _open_dropdown(select_page, 2)
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="New York").click()
    select_page.wait_for_timeout(100)
    assert "New York" in summary.text_content()


@pytest.mark.e2e
def test_select_selected_toggle_class_applied_on_pick(select_page):
    """Picking a priority option moves its class onto the closed trigger, no round-trip.

    The priority dropdown is the 9th Select on the page (nth(8)); it is
    appended last precisely so it does not shift the other dropdowns' indices.
    """
    sel = select_page.locator("details.dropdown.formwork-select").nth(8)
    summary = sel.locator("summary")
    # Nothing selected yet: the trigger carries none of the priority classes.
    assert "select-error" not in (summary.get_attribute("class") or "")
    summary.click()
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    select_page.wait_for_timeout(100)
    assert sel.get_attribute("open") is None
    assert "High" in summary.text_content()
    classes = (summary.get_attribute("class") or "").split()
    assert "select-error" in classes
    assert "false" not in classes, "falsy :class array entry stringified into a literal token"


@pytest.mark.e2e
def test_select_selected_toggle_class_swaps_between_options(select_page):
    """Re-picking swaps the trigger class: the previous option's class is removed."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(8)
    summary = sel.locator("summary")
    summary.click()
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    select_page.wait_for_timeout(100)
    assert "select-error" in (summary.get_attribute("class") or "")
    summary.click()
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Low").click()
    select_page.wait_for_timeout(100)
    cls = summary.get_attribute("class") or ""
    assert "select-success" in cls
    assert "select-error" not in cls


@pytest.mark.e2e
def test_select_htmx_renders(select_page):
    """Select with a server search that fits one page (fourth dropdown) renders visibly."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(3)
    assert sel.is_visible()


@pytest.mark.e2e
def test_select_htmx_open_loads_results(select_page):
    """The htmx search dropdown opens on the server-rendered first page."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(3)
    _open_dropdown(select_page, 3)
    select_page.wait_for_timeout(200)
    expect(sel.locator("ul button")).to_have_count(4, timeout=10000)


@pytest.mark.e2e
def test_select_short_server_list_filters_in_the_browser(select_page):
    """A server search that fits one page filters its rows without a request."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(3)
    requests: list[str] = []
    select_page.on("request", lambda r: requests.append(r.url) if "search/" in r.url else None)
    _open_dropdown(select_page, 3)
    expect(sel.locator("ul button:visible")).to_have_count(4, timeout=10000)
    _type_search(select_page, 3, "Tok")
    expect(sel.locator("ul button:visible")).to_have_count(1, timeout=10000)
    assert "Tokyo" in sel.locator("ul button:visible").text_content()
    select_page.wait_for_timeout(500)
    assert requests == []


@pytest.mark.e2e
def test_select_htmx_pick_sets_value(select_page):
    """Clicking a filtered row sets the hidden input to the row's code."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(3)
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(select_page, 3)
    select_page.wait_for_timeout(200)
    _type_search(select_page, 3, "Lon")
    expect(sel.locator("ul button:visible")).to_have_count(1, timeout=10000)
    sel.locator("ul button", has_text="London").click()
    select_page.wait_for_timeout(200)
    assert hidden.input_value() == "ldn"


@pytest.mark.e2e
def test_select_htmx_no_results_message(select_page):
    """A 'No results' row appears when the server search finds nothing."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(4)
    _open_dropdown(select_page, 4)
    expect(sel.locator("ul button[data-value]")).to_have_count(20, timeout=10000)
    _type_search(select_page, 4, "zzzzz")
    expect(sel.locator("li", has_text="No results")).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_select_htmx_many_load_more_appends_the_next_page(select_page):
    """The htmx-many dropdown (nth=4) opens on one page of 24 cities; "Load more" appends the rest."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(4)
    _open_dropdown(select_page, 4)
    buttons = sel.locator("ul button[data-value]")
    expect(buttons).to_have_count(20, timeout=10000)
    sel.get_by_role("button", name="Load more").click()
    expect(buttons).to_have_count(24, timeout=10000)
    expect(sel.get_by_role("button", name="Load more")).to_have_count(0)


@pytest.mark.e2e
def test_select_htmx_many_search_input_shown_above_threshold(select_page):
    """Search input is visible because the list is longer than one page."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(4)
    _open_dropdown(select_page, 4)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_select_htmx_many_filters_via_htmx(select_page):
    """Htmx-many: typing a search term filters down to matching options."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(4)
    _open_dropdown(select_page, 4)
    _type_search(select_page, 4, "Ber")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    assert "Berlin" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_select_htmx_icons_renders(select_page):
    """Htmx-icons dropdown (nth=5) renders visibly."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    assert sel.is_visible()


@pytest.mark.e2e
def test_select_htmx_icons_loads_results(select_page):
    """Htmx-icons: opening shows the first page of the 31 countries."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    _open_dropdown(select_page, 5)
    buttons = sel.locator("ul button[data-value]")
    expect(buttons).to_have_count(20, timeout=10000)


@pytest.mark.e2e
def test_select_htmx_icons_search_input_shown(select_page):
    """Htmx-icons: search input is visible because total >= search_threshold."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    _open_dropdown(select_page, 5)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_select_htmx_icons_results_have_icons(select_page):
    """Htmx-icons: each option button has an icon span."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    _open_dropdown(select_page, 5)
    first_button = sel.locator("ul button").first
    expect(first_button).to_be_visible(timeout=10000)
    icon_span = first_button.locator("span.shrink-0").first
    assert icon_span.text_content().strip() != ""


@pytest.mark.e2e
def test_select_htmx_icons_results_have_descriptions(select_page):
    """Htmx-icons: each option button has a description span."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    _open_dropdown(select_page, 5)
    descs = sel.locator("ul button span.text-xs")
    expect(descs.first).to_be_visible(timeout=10000)
    assert descs.first.text_content().strip() != ""


@pytest.mark.e2e
def test_select_htmx_icons_filters(select_page):
    """Htmx-icons: search term filters down to one matching country."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    _open_dropdown(select_page, 5)
    _type_search(select_page, 5, "Jap")
    expect(sel.locator("ul button")).to_have_count(1, timeout=10000)
    assert "Japan" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_select_htmx_icons_pick_sets_value(select_page):
    """Htmx-icons: picking an option sets the correct hidden input value."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(5)
    hidden = sel.locator('input[type="hidden"][name]')
    _open_dropdown(select_page, 5)
    sel.locator("ul button", has_text="France").click()
    select_page.wait_for_timeout(200)
    assert hidden.input_value() == "fr"


# ─── Level 5b: E2e, grouped (optgroup) Select ─────────────────────
#
# city_grouped is the 7th Select on the page (nth(6)).


@pytest.mark.e2e
def test_select_grouped_shows_headers(select_page):
    """Open the grouped Select; all three group headers are visible."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(6)
    _open_dropdown(select_page, 6)
    select_page.wait_for_timeout(200)

    headers = sel.locator("li.menu-title")
    assert headers.count() == 3
    visible_texts = [h.inner_text().strip() for h in headers.all() if h.is_visible()]
    assert visible_texts == ["Europe", "Asia", "Americas"]


@pytest.mark.e2e
def test_select_grouped_search_hides_empty_groups(select_page):
    """Typing 'lon' hides Asia and Americas headers (no children match)."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(6)
    _open_dropdown(select_page, 6)
    select_page.wait_for_timeout(200)

    _type_search(select_page, 6, "lon")
    select_page.wait_for_timeout(200)

    visible_headers = [h.inner_text().strip() for h in sel.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Europe"]


# ─── Level 5c: E2e, search auto-focus ───────────────────────────────────
#
# The second Select (city_many) has 21 choices, above the default
# search threshold of 10, so it shows a search input.


@pytest.mark.e2e
def test_select_search_auto_focus_on_open(select_page):
    """Opening a Select with a search box auto-focuses the input."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    sel.locator("summary").click()
    select_page.wait_for_timeout(100)
    search = sel.locator('.dropdown-content input[type="search"]')
    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_select_search_refocus_on_reopen(select_page):
    """Closing then reopening a search-enabled Select re-focuses the input."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(1)
    sel.locator("summary").click()
    select_page.wait_for_timeout(100)
    sel.locator("summary").click()  # close
    select_page.wait_for_timeout(100)
    sel.locator("summary").click()  # reopen
    select_page.wait_for_timeout(100)
    search = sel.locator('.dropdown-content input[type="search"]')
    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_select_no_search_no_focus_error(select_page):
    """Opening a search-less Select does not raise any console error."""
    errors: list[str] = []
    select_page.on("pageerror", lambda e: errors.append(str(e)))

    sel = select_page.locator("details.dropdown.formwork-select").first
    sel.locator("summary").click()
    select_page.wait_for_timeout(150)
    assert errors == []


# ─── Level 5d: E2e, keyboard navigation ─────────────────────────────────
#
# Uses the grouped Select (nth(6)) which has 9 fixed-size options
# in 3 groups and a search input.  Keyboard handlers are on the <details>
# root; the search input is auto-focused on open so events bubble up.


@pytest.mark.e2e
def test_select_keyboard_arrowdown_highlights_first(select_page):
    """ArrowDown highlights the first visible option."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    select_page.wait_for_timeout(50)
    highlighted = sel.locator("li.highlighted > [data-value]")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_keyboard_arrowdown_navigates(select_page):
    """Each ArrowDown moves to the next option, skipping group headers."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    for _ in range(3):  # ldn, par, ber
        search.press("ArrowDown")
    search.press("ArrowDown")  # tyo (next group)
    select_page.wait_for_timeout(50)
    assert sel.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "tyo"


@pytest.mark.e2e
def test_select_search_box_names_the_highlighted_option(select_page):
    """Focus stays in the search box, so aria-activedescendant tells screen readers which row the arrows reached."""
    from playwright.sync_api import expect

    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    search.press("ArrowDown")
    active = sel.locator("li.highlighted")
    expect(active).to_have_attribute("role", "option")
    expect(search).to_have_attribute("aria-activedescendant", active.get_attribute("id"))
    expect(select_page.locator("[role=option][id]")).to_have_count(1)
    search.press("Escape")
    expect(search).not_to_have_attribute("aria-activedescendant", re.compile("."))


@pytest.mark.e2e
def test_select_keyboard_arrowdown_wraps_to_first(select_page):
    """ArrowDown past the last option wraps to the first."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    for _ in range(10):  # 9 + 1 wrap
        search.press("ArrowDown")
    select_page.wait_for_timeout(50)
    assert sel.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_keyboard_arrowup_wraps_to_last(select_page):
    """ArrowUp from no highlight goes to the last visible option."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowUp")
    select_page.wait_for_timeout(50)
    assert sel.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "mex"


@pytest.mark.e2e
def test_select_keyboard_filter_skips_hidden_options(select_page):
    """After filtering, ArrowDown only highlights visible (matching) options."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.fill("lon")  # Matches only "London"
    select_page.wait_for_timeout(150)
    search.press("ArrowDown")
    search.press("ArrowDown")  # Wrap around (only one visible)
    select_page.wait_for_timeout(50)
    highlighted = sel.locator("li.highlighted > [data-value]")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_keyboard_enter_picks_and_closes(select_page):
    """Enter on highlighted option sets value and closes the dropdown."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")  # ldn
    search.press("ArrowDown")  # par
    search.press("Enter")
    select_page.wait_for_timeout(150)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "par"
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_select_keyboard_enter_no_highlight_picks_first(select_page):
    """With no highlight, Enter picks the first visible option."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.fill("tok")
    select_page.wait_for_timeout(150)
    search.press("Enter")
    select_page.wait_for_timeout(150)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "tyo"


@pytest.mark.e2e
def test_select_keyboard_close_clears_highlight(select_page):
    """Closing the dropdown via summary click clears ``.highlighted``."""
    sel = open_dropdown(select_page, "formwork-select", 6, settle_ms=200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    select_page.wait_for_timeout(50)
    assert sel.locator("li.highlighted > [data-value]").count() == 1
    sel.locator("summary").click()
    select_page.wait_for_timeout(150)
    assert sel.locator("li.highlighted > [data-value]").count() == 0


@pytest.mark.e2e
def test_select_escape_in_a_dialog_closes_only_the_panel(select_page):
    """Escape shuts the open panel, keeps the modal dialog around it open and refocuses the trigger."""
    from playwright.sync_api import expect

    select_page.evaluate("""() => {
        const dialog = document.createElement("dialog");
        dialog.id = "e2e_dialog";
        document.body.append(dialog);
        dialog.append(document.getElementById("id_city_grouped_field"));
        dialog.showModal();
    }""")
    select_page.locator("#id_city_grouped").click()
    search = select_page.locator("#id_city_grouped_wrapper input[type=search]")
    expect(search).to_be_focused()
    search.fill("par")
    search.press("Escape")
    expect(select_page.locator("#id_city_grouped_wrapper[open]")).to_have_count(0)
    expect(select_page.locator("#e2e_dialog[open]")).to_have_count(1)
    expect(select_page.locator("#id_city_grouped")).to_be_focused()
    expect(search).to_have_value("")
    select_page.keyboard.press("Escape")
    expect(select_page.locator("#e2e_dialog[open]")).to_have_count(0)


@pytest.mark.e2e
def test_select_focus_leaving_the_widget_closes_the_panel(select_page):
    """Tabbing to another control closes the panel, as a click elsewhere does."""
    from playwright.sync_api import expect

    select_page.locator("#id_city_plain").click()
    expect(select_page.locator("#id_city_plain_wrapper[open]")).to_have_count(1)
    select_page.locator("#id_city_icons").focus()
    expect(select_page.locator("#id_city_plain_wrapper[open]")).to_have_count(0)


@pytest.mark.e2e
def test_select_outside_click_leaves_other_details_alone(select_page):
    """Only formwork dropdowns close on an outside click; a page's own <details> keeps its state."""
    from playwright.sync_api import expect

    select_page.evaluate("""() => document.body.insertAdjacentHTML(
        "afterbegin", '<details class="dropdown" id="e2e_menu" open><summary>Menu</summary></details>',
    )""")
    select_page.locator("#id_city_plain").click()
    select_page.mouse.click(2, 300)
    expect(select_page.locator("#id_city_plain_wrapper[open]")).to_have_count(0)
    expect(select_page.locator("#e2e_menu[open]")).to_have_count(1)


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Gap: /select/ has only required=False fields, so an e2e error-flow
# test needs a page with a required Select, which does not exist yet.


@pytest.mark.e2e
def test_select_failing_search_shows_error_alert(select_page):
    """When the search endpoint returns 500, the error alert appears in
    place of the listbox and the alert carries the failure message."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(7)
    _open_dropdown(select_page, 7)
    select_page.wait_for_timeout(200)
    _type_search(select_page, 7, "x")
    alert = sel.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    assert "Search failed" in alert.text_content()
    expect(sel.locator("ul[role='listbox']")).to_be_hidden()


@pytest.mark.e2e
def test_select_search_input_works_after_error(select_page):
    """The search input remains usable after a failure; typing fires a new
    request and the value lands in the input."""
    from playwright.sync_api import expect

    sel = select_page.locator("details.dropdown.formwork-select").nth(7)
    requests: list[str] = []
    select_page.on("request", lambda r: requests.append(r.url) if "search/" in r.url else None)
    _open_dropdown(select_page, 7)
    _type_search(select_page, 7, "x")
    alert = sel.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    initial_count = len(requests)
    _type_search(select_page, 7, "xy")
    # 300ms input-changed debounce + buffer for the request to fire.
    select_page.wait_for_timeout(500)
    assert len(requests) > initial_count, "expected typing to fire a new search request"
    val = select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select');
        return dds[7].querySelector('.dropdown-content input[type="search"]').value;
    }""")
    assert val == "xy"


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_select_morph_preserves_value(select_page):
    """Selected value survives an htmx form morph."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    select_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select').open = true;
    """)
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="London").click()
    select_page.wait_for_timeout(200)
    hidden = sel.locator('input[type="hidden"][name]')
    assert hidden.input_value() == "ldn"
    submit(select_page)
    hidden = select_page.locator(
        "details.dropdown.formwork-select input[type='hidden']",
    ).first
    assert hidden.input_value() == "ldn"
    summary = select_page.locator(
        "details.dropdown.formwork-select summary",
    ).first
    assert "London" in summary.text_content()


@pytest.mark.e2e
def test_select_morph_preserves_dropdown_closed(select_page):
    """Closed dropdown stays closed after a morph."""
    sel = select_page.locator("details.dropdown.formwork-select").first
    select_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select').open = true;
    """)
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="Tokyo").click()
    select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is None
    submit(select_page)
    assert sel.get_attribute("open") is None


@pytest.mark.e2e
def test_select_morph_preserves_dropdown_open(select_page):
    """Open dropdown stays open after a morph."""
    select_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select').open = true;
    """)
    select_page.wait_for_timeout(200)
    select_page.evaluate("""
        const form = document.querySelector('form[hx-post]');
        form.noValidate = true;
        form.requestSubmit();
    """)
    select_page.wait_for_timeout(500)
    sel = select_page.locator("details.dropdown.formwork-select").first
    assert sel.get_attribute("open") is not None


@pytest.mark.e2e
def test_select_toggle_class_survives_noop_morph(select_page):
    """Alpine-applied trigger classes survive a no-op morph.

    A re-render of already-saved state changes no data attributes, so nothing
    re-evaluates the :class binding; the morph itself must keep the classes.
    """
    sel = select_page.locator("details.dropdown.formwork-select").nth(8)
    summary = sel.locator("summary")
    summary.click()
    select_page.wait_for_timeout(200)
    sel.locator("button", has_text="High").click()
    select_page.wait_for_timeout(100)
    assert "select-error" in (summary.get_attribute("class") or "")
    submit(select_page)
    assert "select-error" in (summary.get_attribute("class") or "")
    submit(select_page)
    classes = (summary.get_attribute("class") or "").split()
    assert "select-error" in classes
    assert "false" not in classes


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_select_screenshot_default(select_page, assert_screenshot):
    """Visual snapshot: Select in default (closed) state."""
    wrapper = select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-default.png")


@pytest.mark.screenshot
def test_select_screenshot_open(select_page, assert_screenshot):
    """Visual snapshot: Select with dropdown open."""
    select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.formwork-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
    select_page.wait_for_timeout(200)
    wrapper = select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_select_screenshot_selected(select_page, assert_screenshot):
    """Visual snapshot: Select with an option selected."""
    select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.formwork-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
    select_page.wait_for_timeout(200)
    select_page.locator("details.dropdown.formwork-select").first.locator("button", has_text="London").click()
    select_page.wait_for_timeout(100)
    wrapper = select_page.locator("#id_city_plain_field")
    assert_screenshot(wrapper, "search-select-selected.png")


@pytest.mark.screenshot
def test_select_screenshot_selected_toggle_class(select_page, assert_screenshot):
    """Visual snapshot: priority Select trigger recolored by the picked option."""
    select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select');
        // The top-layer panel tracks its trigger; Playwright can't scroll
        // a fixed element into view, so the trigger must be visible first.
        dds[8].scrollIntoView({block: 'center'});
        dds[8].open = true;
        dds[8].dispatchEvent(new Event('toggle'));
    }""")
    select_page.wait_for_timeout(200)
    sel = select_page.locator("details.dropdown.formwork-select").nth(8)
    sel.locator("button", has_text="High").click()
    select_page.wait_for_timeout(100)
    wrapper = select_page.locator("#id_priority_field")
    assert_screenshot(wrapper, "search-select-selected-toggle-class.png")


@pytest.mark.screenshot
def test_select_screenshot_grouped_open(select_page, assert_screenshot):
    """Visual snapshot: grouped Select with dropdown open showing optgroup headers."""
    select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select');
        dds[6].open = true;
        dds[6].dispatchEvent(new Event('toggle'));
    }""")
    select_page.wait_for_timeout(200)
    wrapper = select_page.locator("#id_city_grouped_field")
    assert_screenshot(wrapper, "search-select-grouped-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_select_screenshot_keyboard_highlighted(select_page, assert_screenshot):
    """Visual snapshot: Select with an option highlighted via keyboard."""
    sel = select_page.locator("details.dropdown.formwork-select").nth(6)
    sel.locator("summary").click()
    select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")  # Highlight ldn
    select_page.wait_for_timeout(50)
    wrapper = select_page.locator("#id_city_grouped_field")
    assert_screenshot(wrapper, "search-select-keyboard-highlighted.png", capture_dropdown=True)
