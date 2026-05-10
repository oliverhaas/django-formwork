"""SearchSelect widget tests: unit → integration → e2e → screenshot.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_search_select.py                   # everything
    uv run pytest tests/widgets/test_search_select.py -m unit           # fast only
    uv run pytest tests/widgets/test_search_select.py -m "not e2e"      # skip browser

Levels:
    1. unit        — widget object: instantiation, choices, search_url, show_search,
                     get_context, value_from_datadict, edge cases
    2. unit        — widget rendering: HTML structure, attributes, icons, htmx attrs
    3. integration — form integration: fieldset, error state, prefix
    4. integration — Jinja2/DTL parity
    5. e2e         — user interaction: opening, selecting, search filtering
    6. e2e         — error flow (no dedicated error page yet — see comment)
    7. e2e         — morph resilience: dropdown state, selected value preserved
    8. screenshot  — visual states: closed, open, selected
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork.fields import FormworkChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchSelect

from .conftest import assert_html_equivalent, render_form, render_widget


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
def test_search_select_default_search_url_is_none():
    """search_url defaults to None when not specified."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    assert widget.search_url is None


@pytest.mark.unit
def test_search_select_search_url_stored():
    """Explicitly passed search_url is stored on the widget."""
    widget = SearchSelect(search_url="/search/", choices=[("a", "Alpha")])
    assert widget.search_url == "/search/"


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
def test_search_select_get_context_search_url():
    """get_context returns the search_url that was passed at construction."""
    widget = SearchSelect(search_url="/search/", choices=[("a", "Alpha")])
    ctx = widget.get_context("test", "", {"id": "id_test"})
    assert ctx["widget"]["search_url"] == "/search/"


@pytest.mark.unit
def test_search_select_get_context_search_url_none_by_default():
    """search_url in context is None when not specified."""
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
    """Icons from FormworkChoiceLabel are injected into optgroups."""
    widget = SearchSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>"))),
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
    """The wrapper <details> element has an x-data attribute."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", attrs={"x-data": True})
    assert wrapper is not None


@pytest.mark.unit
def test_search_select_show_search_false_in_x_data():
    """x-data contains showSearch: false when below threshold."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    details = soup.find("details")
    assert "showSearch: false" in details.get("x-data", "")


@pytest.mark.unit
def test_search_select_selected_label_in_x_data():
    """Selected option label appears in x-data when value is pre-set."""
    widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test", value="b")
    wrapper = soup.find("details", attrs={"x-data": True})
    x_data = wrapper["x-data"]
    assert "label: 'Beta'" in x_data


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
def test_search_select_no_results_element():
    """A 'No results' paragraph is rendered with x-show='noResults'."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    no_results = soup.find("p", string="No results")
    assert no_results is not None
    assert no_results.get("x-show") == "noResults"


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
    widget = SearchSelect(search_url="/search/", choices=[])
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
def test_search_select_htmx_attrs_when_search_url():
    """Search input carries htmx attrs when search_url is set."""
    widget = SearchSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="city", attrs={"id": "id_city"})
    dropdown = soup.find("div", class_="dropdown-content")
    search = dropdown.find("input", {"type": "text"})
    assert search["hx-get"] == "/search/"
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
def test_search_select_no_client_options_when_search_url():
    """No option buttons are rendered when search_url is set (server-side only)."""
    widget = SearchSelect(search_url="/search/", choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    buttons = soup.find_all("button", {"type": "button"})
    assert len(buttons) == 0


@pytest.mark.unit
def test_search_select_no_alpine_no_results_when_search_url():
    """No 'No results' paragraph when search_url is set (server handles no results)."""
    widget = SearchSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_search_select_icon_rendered_in_option():
    """FormworkChoiceLabel icons appear in the rendered option buttons."""
    widget = SearchSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_search_select_no_icon_element_when_not_provided():
    """No <img> elements rendered when no FormworkChoiceLabel icons."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


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
    """FormworkChoiceLabel icons/descriptions render inside grouped options."""
    widget = SearchSelect(
        choices=[
            ("", ""),
            (
                "Europe",
                [
                    (
                        "ldn",
                        FormworkChoiceLabel("London", icon="\U0001f1ec\U0001f1e7", description="UK capital"),
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
    """SearchSelect renders correctly when used inside a FormworkForm."""
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
def test_search_select_form_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = SearchSelectForm(data={})
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


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_search_select_renders_on_page(search_select_page):
    """SearchSelect is visible on the /search-select/ page."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_open_close_dropdown(search_select_page):
    """User can open the dropdown by clicking the summary trigger."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    summary = sel.locator("summary")
    summary.click()
    search_select_page.wait_for_timeout(200)
    assert sel.get_attribute("open") is not None
    summary.click()
    search_select_page.wait_for_timeout(200)


@pytest.mark.e2e
def test_search_select_no_search_input_with_few_options(search_select_page):
    """Search input is hidden when option count is below threshold."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    search_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.search-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_wrapper = sel.locator(".dropdown-content > div").first
    assert not search_wrapper.is_visible()


@pytest.mark.e2e
def test_search_select_pick_option_sets_value(search_select_page):
    """Clicking an option sets the hidden input value."""
    sel = search_select_page.locator("details.dropdown.search-select").first
    hidden = sel.locator('input[type="hidden"][name]')
    search_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.search-select');
        dd.open = true;
        dd.dispatchEvent(new Event('toggle'));
    }""")
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
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[1].open = true;
        dds[1].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search = sel.locator('.dropdown-content input[type="text"]')
    assert search.count() == 1


@pytest.mark.e2e
def test_search_select_many_filters_options(search_select_page):
    """Typing in the search input filters the visible options."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(1)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[1].open = true;
        dds[1].dispatchEvent(new Event('toggle'));
    }""")
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
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[1].open = true;
        dds[1].dispatchEvent(new Event('toggle'));
    }""")
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
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[2].open = true;
        dds[2].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    sel.locator("button", has_text="New York").click()
    search_select_page.wait_for_timeout(100)
    assert "New York" in summary.text_content()


@pytest.mark.e2e
def test_search_select_htmx_renders(search_select_page):
    """SearchSelect with htmx search (fourth dropdown) renders visibly."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    assert sel.is_visible()


@pytest.mark.e2e
def test_search_select_htmx_open_loads_results(search_select_page):
    """Opening the htmx search dropdown loads results from the server."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[3].open = true;
        dds[3].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.focus();
        search.dispatchEvent(new Event('focus'));
    }""")
    search_select_page.wait_for_timeout(1000)
    buttons = sel.locator("ul button")
    assert buttons.count() >= 1


@pytest.mark.e2e
def test_search_select_htmx_filters_via_htmx(search_select_page):
    """Typing in the htmx search input triggers a server request and filters results."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[3].open = true;
        dds[3].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.focus();
        search.dispatchEvent(new Event('focus'));
    }""")
    search_select_page.wait_for_timeout(1000)
    expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.value = 'Tok';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
    assert "Tokyo" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_search_select_htmx_pick_sets_value(search_select_page):
    """Clicking an htmx result button sets the hidden input value."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    hidden = sel.locator('input[type="hidden"][name]')
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[3].open = true;
        dds[3].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.focus();
        search.dispatchEvent(new Event('focus'));
    }""")
    search_select_page.wait_for_timeout(1000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.value = 'Lon';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    search_select_page.wait_for_timeout(1000)
    sel.locator("ul button", has_text="London").click()
    search_select_page.wait_for_timeout(200)
    assert hidden.input_value() == "ldn"


@pytest.mark.e2e
def test_search_select_htmx_no_results_message(search_select_page):
    """A 'No results' item appears when the htmx search finds nothing."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(3)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[3].open = true;
        dds[3].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        search.focus();
        search.dispatchEvent(new Event('focus'));
    }""")
    search_select_page.wait_for_timeout(1000)
    expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[3].querySelector('.dropdown-content input[type="text"]');
        htmx.ajax('GET', search.getAttribute('hx-get') + '?q=zzzzz&type=search_select', {
            target: search.getAttribute('hx-target'),
            swap: 'innerHTML',
        });
    }""")
    no_results = sel.locator("li", has_text="No results")
    expect(no_results).to_be_visible(timeout=3000)


@pytest.mark.e2e
def test_search_select_htmx_many_open_loads_all(search_select_page):
    """Opening the htmx-many dropdown (nth=4) loads all 24 results."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[4].open = true;
        dds[4].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    buttons = sel.locator("ul button")
    expect(buttons).to_have_count(24, timeout=3000)


@pytest.mark.e2e
def test_search_select_htmx_many_search_input_shown_above_threshold(search_select_page):
    """Search input is visible after htmx loads because total (24) >= threshold (20)."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[4].open = true;
        dds[4].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=3000)


@pytest.mark.e2e
def test_search_select_htmx_many_filters_via_htmx(search_select_page):
    """Htmx-many: typing a search term filters down to matching options."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(4)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[4].open = true;
        dds[4].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[4].querySelector('.dropdown-content input[type="text"]');
        search.value = 'Ber';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
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
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    buttons = sel.locator("ul button")
    expect(buttons).to_have_count(31, timeout=3000)


@pytest.mark.e2e
def test_search_select_htmx_icons_search_input_shown(search_select_page):
    """Htmx-icons: search input is visible because total >= search_threshold."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    search_wrapper = sel.locator(".dropdown-content > div").first
    expect(search_wrapper).to_be_visible(timeout=3000)


@pytest.mark.e2e
def test_search_select_htmx_icons_results_have_icons(search_select_page):
    """Htmx-icons: each option button has an icon span."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    first_button = sel.locator("ul button").first
    icon_span = first_button.locator("span.shrink-0").first
    assert icon_span.text_content().strip() != ""


@pytest.mark.e2e
def test_search_select_htmx_icons_results_have_descriptions(search_select_page):
    """Htmx-icons: each option button has a description span."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    descs = sel.locator("ul button span.text-xs")
    assert descs.count() >= 1
    assert descs.first.text_content().strip() != ""


@pytest.mark.e2e
def test_search_select_htmx_icons_filters(search_select_page):
    """Htmx-icons: search term filters down to one matching country."""
    from playwright.sync_api import expect

    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[5].querySelector('.dropdown-content input[type="text"]');
        search.value = 'Jap';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
    assert "Japan" in sel.locator("ul button").first.text_content()


@pytest.mark.e2e
def test_search_select_htmx_icons_pick_sets_value(search_select_page):
    """Htmx-icons: picking an option sets the correct hidden input value."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(5)
    hidden = sel.locator('input[type="hidden"][name]')
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[5].open = true;
        dds[5].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(2000)
    sel.locator("ul button", has_text="France").click()
    search_select_page.wait_for_timeout(200)
    assert hidden.input_value() == "fr"


# ─── Level 5b: E2e — grouped (optgroup) SearchSelect ─────────────────────
#
# city_grouped is the 7th SearchSelect on the page (nth(6)).


@pytest.mark.e2e
def test_search_select_grouped_shows_headers(search_select_page):
    """Open the grouped SearchSelect; all three group headers are visible."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(6)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[6].open = true;
        dds[6].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)

    headers = sel.locator("li.menu-title")
    assert headers.count() == 3
    visible_texts = [h.inner_text().strip() for h in headers.all() if h.is_visible()]
    assert visible_texts == ["Europe", "Asia", "Americas"]


@pytest.mark.e2e
def test_search_select_grouped_search_hides_empty_groups(search_select_page):
    """Typing 'lon' hides Asia and Americas headers (no children match)."""
    sel = search_select_page.locator("details.dropdown.search-select").nth(6)
    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        dds[6].open = true;
        dds[6].dispatchEvent(new Event('toggle'));
    }""")
    search_select_page.wait_for_timeout(200)

    search_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.search-select');
        const search = dds[6].querySelector('.dropdown-content input[type="text"]');
        search.value = 'lon';
        search.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    search_select_page.wait_for_timeout(200)

    visible_headers = [h.inner_text().strip() for h in sel.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Europe"]


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# The /search-select/ page marks all fields as required=False, so no
# validation errors are triggered on empty submit.  A dedicated page with
# a required SearchSelect would be needed for a proper error-flow test.
# Skipped until that page exists — tracked as part of the broader error-
# state test work.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_search_select_morph_preserves_value(search_select_page):
    """Selected value survives an htmx form morph."""
    from tests.e2e.conftest import submit

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
    from tests.e2e.conftest import submit

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


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — PNG artifacts land in test-results/ for manual review.
# True baseline comparison requires a visual-regression plugin (see #26).


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
