"""Tests for the MultiSelect widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_multi_select.py                 # everything
    uv run pytest tests/widgets/ -m unit                             # all widgets, unit only
    uv run pytest tests/widgets/test_multi_select.py -m "not e2e"   # skip browser tests

Levels:
    1. unit        — widget object: instantiation, choices, search_url, get_context
    2. unit        — widget rendering: HTML structure, attributes, htmx attrs
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: open, check, search filter
    6. e2e         — error flow: (SKIP — MultiSelect is required=False by default on
                     the /multi-select/ page; no dedicated error page exists yet)
    7. e2e         — morph resilience: checked options and dropdown state preserved
    8. screenshot  — visual states: default (closed), open, options selected
"""

from __future__ import annotations

import json

import pytest
from django import forms
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork.forms import FormworkForm
from django_formwork.widgets import MultiSelect

from .conftest import assert_html_equivalent, render_form, render_widget


class MultiSelectForm(FormworkForm):
    """Form fixture for MultiSelect integration tests."""

    tags = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B"), ("c", "C")],
        widget=MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_multi_select_default_search_url_is_none():
    """MultiSelect has no search_url by default."""
    widget = MultiSelect(choices=[("a", "A")])
    assert widget.search_url is None


@pytest.mark.unit
def test_multi_select_search_url_stored():
    """search_url passed to constructor is accessible on the widget."""
    widget = MultiSelect(search_url="/api/search/", choices=[("a", "A")])
    assert widget.search_url == "/api/search/"


@pytest.mark.unit
def test_multi_select_choices_stored():
    """Choices passed to constructor are available via widget.choices."""
    widget = MultiSelect(choices=[("py", "Python"), ("js", "JavaScript")])
    assert list(widget.choices) == [("py", "Python"), ("js", "JavaScript")]


@pytest.mark.unit
def test_multi_select_get_context_has_search_url():
    """get_context() exposes search_url in widget context."""
    widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["search_url"] == "/search/"


@pytest.mark.unit
def test_multi_select_get_context_search_url_none_by_default():
    """get_context() has search_url=None when not supplied."""
    widget = MultiSelect(choices=[("a", "A")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_multi_select_get_context_show_search_false_for_few():
    """show_search is False when choices < search_threshold and no search_url."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is False


@pytest.mark.unit
def test_multi_select_get_context_show_search_true_for_many():
    """show_search is True when choices >= search_threshold (20)."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = MultiSelect(choices=choices)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_multi_select_get_context_show_search_true_with_search_url():
    """show_search is always True when search_url is provided."""
    widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_multi_select_get_context_optgroups_have_icon():
    """Each option in get_context() optgroups has an 'icon' key."""
    widget = MultiSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", [], {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            assert "icon" in option


@pytest.mark.unit
def test_multi_select_get_context_icon_populated():
    """Icons dict is reflected in option['icon'] for matching values."""
    widget = MultiSelect(
        choices=[("a", "Alpha"), ("b", "Beta")],
        icons={"a": mark_safe("<svg>icon</svg>")},
    )
    ctx = widget.get_context("test", [], {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["icon"] == "<svg>icon</svg>"
            else:
                assert option["icon"] == ""


@pytest.mark.unit
def test_multi_select_initial_selected_json_empty_without_search_url():
    """initial_selected_json is not present when no search_url."""
    widget = MultiSelect(choices=[("a", "Alpha")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert "initial_selected_json" not in ctx["widget"]


@pytest.mark.unit
def test_multi_select_initial_selected_json_empty_list():
    """initial_selected_json is '[]' when search_url set but no values selected."""
    widget = MultiSelect(search_url="/search/", choices=[("a", "Alpha")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    initial = json.loads(ctx["widget"]["initial_selected_json"])
    assert initial == []


@pytest.mark.unit
def test_multi_select_initial_selected_json_with_value():
    """initial_selected_json encodes selected value with label and icon."""
    widget = MultiSelect(search_url="/search/", choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", ["a"], {"id": "id_test"})
    initial = json.loads(ctx["widget"]["initial_selected_json"])
    assert initial == [["a", ["Alpha", ""]]]


@pytest.mark.unit
def test_multi_select_value_from_datadict_returns_list():
    """value_from_datadict returns a list of selected values."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    data = QueryDict("field=a&field=c")
    result = widget.value_from_datadict(data, {}, "field")
    assert result == ["a", "c"]


@pytest.mark.unit
def test_multi_select_value_from_datadict_empty():
    """value_from_datadict returns empty list when no values submitted."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "field")
    assert result is None or result == []


@pytest.mark.unit
def test_multi_select_value_from_datadict_single():
    """value_from_datadict returns a single-item list when one value submitted."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    data = QueryDict("field=b")
    result = widget.value_from_datadict(data, {}, "field")
    assert result == ["b"]


@pytest.mark.unit
def test_multi_select_search_threshold_default():
    """search_threshold is 20 by default."""
    widget = MultiSelect(choices=[])
    assert widget.search_threshold == 20


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_multi_select_renders_details_dropdown():
    """Rendered HTML has a <details class='dropdown'> wrapper."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="dropdown")
    assert details is not None


@pytest.mark.unit
def test_multi_select_renders_multiselect_class_on_details():
    """The <details> wrapper also has the 'multiselect' class."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="multiselect")
    assert details is not None


@pytest.mark.unit
def test_multi_select_renders_summary_trigger():
    """Rendered HTML has a <summary> element with 'text-left' class."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    summary = soup.find("summary")
    assert summary is not None
    # DaisyUI .select is applied via CSS @apply, not directly in HTML
    assert "text-left" in summary.get("class", [])


@pytest.mark.unit
def test_multi_select_renders_dropdown_content():
    """A <div class='dropdown-content'> is present."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    assert dropdown is not None


@pytest.mark.unit
def test_multi_select_options_in_list_items():
    """Options render as <li> elements inside a <ul>."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    items = soup.find("div", class_="dropdown-content").find("ul").find_all("li")
    assert len(items) == 2


@pytest.mark.unit
def test_multi_select_renders_hidden_checkboxes():
    """Each option renders as an <input type='checkbox'> with class 'hidden'."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    soup = render_widget(widget, name="test")
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    assert len(checkboxes) == 3
    for cb in checkboxes:
        assert "hidden" in cb.get("class", [])


@pytest.mark.unit
def test_multi_select_checkboxes_have_multiselect_class():
    """Each checkbox has the 'multiselect' CSS class."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    for cb in checkboxes:
        assert "multiselect" in cb.get("class", [])


@pytest.mark.unit
def test_multi_select_checkbox_values():
    """Checkboxes have correct values matching the choices."""
    widget = MultiSelect(choices=[("py", "Python"), ("js", "JS")])
    soup = render_widget(widget, name="lang")
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    values = [cb["value"] for cb in checkboxes]
    assert values == ["py", "js"]


@pytest.mark.unit
def test_multi_select_checkbox_name():
    """Checkboxes use the widget's field name."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="field")
    cb = soup.find("input", {"type": "checkbox"})
    assert cb["name"] == "field"


@pytest.mark.unit
def test_multi_select_selected_values_checked():
    """Pre-selected values render as checked checkboxes."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    soup = render_widget(widget, name="test", value=["a", "c"])
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    checked = [cb["value"] for cb in checkboxes if cb.has_attr("checked")]
    assert checked == ["a", "c"]


@pytest.mark.unit
def test_multi_select_checkmark_present():
    """Each option has a <span class='formwork-check opacity-0'> checkmark indicator."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    check = soup.find("span", class_="formwork-check")
    assert check is not None
    assert "opacity-0" in check.get("class", [])


@pytest.mark.unit
def test_multi_select_checkmark_before_label_text():
    """Label structure is: input, checkmark span, text span (in that order)."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    label = soup.find("label")
    children = [c for c in label.children if getattr(c, "name", None)]
    names = [c.name for c in children]
    assert names == ["input", "span", "span"]


@pytest.mark.unit
def test_multi_select_alpine_x_data():
    """The <details> wrapper carries an x-data attribute for Alpine."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", attrs={"x-data": True})
    assert wrapper is not None


@pytest.mark.unit
def test_multi_select_option_labels():
    """Choice labels are rendered as text spans inside list items."""
    widget = MultiSelect(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_multi_select_search_hidden_for_few_choices():
    """Search input is absent when choices < search_threshold."""
    widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    search = soup.find("input", {"type": "text", "x-model": "search"})
    assert search is None


@pytest.mark.unit
def test_multi_select_search_shown_for_many_choices():
    """Search input appears when choices >= search_threshold (20)."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = MultiSelect(choices=choices)
    soup = render_widget(widget, name="test")
    search = soup.find("input", {"type": "text", "x-model": "search"})
    assert search is not None


@pytest.mark.unit
def test_multi_select_no_results_element_for_many_choices():
    """A 'No results' paragraph is rendered when show_search is active."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = MultiSelect(choices=choices)
    soup = render_widget(widget, name="test")
    no_results = soup.find("p", string="No results")
    assert no_results is not None
    assert no_results.get("x-show") == "noResults"


@pytest.mark.unit
def test_multi_select_no_results_hidden_for_few_choices():
    """'No results' element is absent when choices are below the threshold."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_multi_select_aria_invalid_on_summary():
    """aria-invalid='true' is forwarded to the <summary> trigger."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    summary = soup.find("summary")
    assert summary["aria-invalid"] == "true"


@pytest.mark.unit
def test_multi_select_no_aria_invalid_when_valid():
    """aria-invalid is absent on <summary> when no error."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-invalid")


@pytest.mark.unit
def test_multi_select_wrapper_has_id():
    """<details> gets id='{id}_multiselect' when attrs contain an id."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="multiselect")
    assert details["id"] == "id_test_multiselect"


@pytest.mark.unit
def test_multi_select_no_wrapper_id_without_id():
    """<details> has no id when no id attr is passed."""
    widget = MultiSelect(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="multiselect")
    assert not details.has_attr("id")


@pytest.mark.unit
def test_multi_select_htmx_attrs_when_search_url():
    """Search input gets hx-get, hx-trigger, hx-target, hx-swap when search_url set."""
    widget = MultiSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="lang", attrs={"id": "id_lang"})
    search_input = soup.find("input", {"type": "text"})
    assert search_input is not None
    assert search_input["hx-get"] == "/search/"
    assert "input changed delay:300ms" in search_input["hx-trigger"]
    assert search_input["hx-target"] == "#id_lang_options"
    assert search_input["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_multi_select_no_htmx_attrs_without_search_url():
    """Search input has no htmx attributes when search_url is absent."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = MultiSelect(choices=choices)
    soup = render_widget(widget, name="test")
    search_input = soup.find("input", {"type": "text"})
    assert not search_input.has_attr("hx-get")


@pytest.mark.unit
def test_multi_select_no_client_options_when_search_url():
    """No checkboxes are rendered in the DOM when search_url is provided."""
    widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    assert len(checkboxes) == 0


@pytest.mark.unit
def test_multi_select_htmx_mode_uses_alpine_map():
    """htmx mode Alpine x-data uses a Map for selected values tracking."""
    widget = MultiSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details")
    x_data = details["x-data"]
    assert "selected: new Map(" in x_data
    assert "toggle(" in x_data


@pytest.mark.unit
def test_multi_select_htmx_mode_hidden_inputs_template():
    """htmx mode uses an x-for template that renders hidden inputs per selected value."""
    widget = MultiSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    template = soup.find("template", {"x-for": True})
    assert template is not None
    hidden = template.find("input", {"type": "hidden"})
    assert hidden is not None
    assert hidden[":value"] == "val"
    assert hidden["name"] == "test"


@pytest.mark.unit
def test_multi_select_htmx_wrapper_has_id():
    """<details> id is set correctly in htmx mode too."""
    widget = MultiSelect(search_url="/search/", choices=[])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="multiselect")
    assert details["id"] == "id_test_multiselect"


@pytest.mark.unit
def test_multi_select_icons_rendered():
    """Icons dict values appear in the rendered HTML for matching choices."""
    widget = MultiSelect(
        choices=[("a", "Alpha"), ("b", "Beta")],
        icons={"a": mark_safe('<img src="a.svg">')},
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_multi_select_no_icon_when_not_provided():
    """No <img> elements rendered when no icons are configured."""
    widget = MultiSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_multi_select_renders_via_form():
    """MultiSelect renders correctly when used inside a FormworkForm."""
    form = MultiSelectForm()
    soup = render_form(form)
    details = soup.find("details", class_="multiselect")
    assert details is not None


@pytest.mark.integration
def test_multi_select_form_wraps_in_fieldset():
    """Field template wraps the MultiSelect in a fieldset with a stable id."""
    form = MultiSelectForm()
    soup = render_form(form)
    fieldset = soup.find("fieldset", id="id_tags_field")
    assert fieldset is not None


@pytest.mark.integration
def test_multi_select_error_state_aria_invalid():
    """Bound form with errors adds aria-invalid='true' to the summary trigger."""
    form = MultiSelectForm(data={})
    form.is_valid()
    soup = render_form(form)
    summary = soup.find("summary")
    assert summary.get("aria-invalid") == "true"


@pytest.mark.integration
def test_multi_select_error_state_shows_tooltip():
    """Bound form with errors renders a tooltip containing the error text."""
    form = MultiSelectForm(data={})
    form.is_valid()
    soup = render_form(form)
    tooltip = soup.find(id="id_tags_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_multi_select_form_prefix_handling():
    """Form prefix propagates to widget id and wrapper id."""
    form = MultiSelectForm(prefix="cfg")
    soup = render_form(form)
    details = soup.find("details", class_="multiselect")
    assert details is not None
    assert details.get("id") == "id_cfg-tags_multiselect"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_multi_select_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """MultiSelect produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(MultiSelectForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(MultiSelectForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_multi_select_renders_on_page(multi_select_page):
    """MultiSelect dropdown is visible on the /multi-select/ page."""
    from playwright.sync_api import expect

    multi = multi_select_page.locator("details.dropdown.multiselect").first
    expect(multi).to_be_visible()


@pytest.mark.e2e
def test_multi_select_open_shows_checkboxes(multi_select_page):
    """Opening the dropdown reveals checkbox inputs."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    summary = multi.locator("summary")
    summary.click()
    multi_select_page.wait_for_timeout(100)
    checkboxes = multi.locator('input[type="checkbox"]')
    assert checkboxes.count() >= 2


@pytest.mark.e2e
def test_multi_select_select_multiple(multi_select_page):
    """User can check multiple options via JS dispatch."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(100)
    multi_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.multiselect');
        ['py', 'go'].forEach(v => {
            const cb = dd.querySelector(`input[value="${v}"]`);
            cb.checked = true;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        });
    }""")
    multi_select_page.wait_for_timeout(100)
    assert multi.locator('input[value="py"]').is_checked()
    assert multi.locator('input[value="go"]').is_checked()


@pytest.mark.e2e
def test_multi_select_summary_shows_selection(multi_select_page):
    """After selecting an option the summary reflects the selection."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    summary = multi.locator("summary")
    summary.click()
    multi_select_page.wait_for_timeout(100)
    multi_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.multiselect');
        const cb = dd.querySelector('input[value="py"]');
        cb.checked = true;
        cb.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    multi_select_page.wait_for_timeout(100)
    summary_text = summary.text_content()
    assert "Python" in summary_text or "1" in summary_text


@pytest.mark.e2e
def test_multi_select_no_search_bar_for_plain(multi_select_page):
    """Plain MultiSelect with 4 choices has no search input (below threshold)."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(100)
    search = multi.locator('input[type="text"]')
    assert search.count() == 0


@pytest.mark.e2e
def test_multi_select_icons_has_search_bar(multi_select_page):
    """Icons MultiSelect with 31 countries shows a search bar (above threshold)."""
    multi = multi_select_page.locator("details.dropdown.multiselect").nth(1)
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(100)
    search = multi.locator('input[type="text"]')
    assert search.count() == 1


@pytest.mark.e2e
def test_multi_select_icons_has_many_checkboxes(multi_select_page):
    """Icons MultiSelect should have 31 country checkboxes."""
    multi = multi_select_page.locator("details.dropdown.multiselect").nth(1)
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(100)
    checkboxes = multi.locator('input[type="checkbox"]')
    assert checkboxes.count() == 31


@pytest.mark.e2e
def test_multi_select_htmx_renders(multi_select_page):
    """htmx MultiSelect is visible on the page."""
    from playwright.sync_api import expect

    multi = multi_select_page.locator("details.dropdown.multiselect").nth(2)
    expect(multi).to_be_visible()


@pytest.mark.e2e
def test_multi_select_htmx_open_loads_results(multi_select_page):
    """htmx MultiSelect loads results when opened."""
    multi = multi_select_page.locator("details.dropdown.multiselect").nth(2)
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(200)
    multi_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.multiselect');
        const search = dds[2].querySelector('input[type="text"]');
        htmx.ajax('GET', search.getAttribute('hx-get') + '?q=&type=multiselect&name=languages_htmx', {
            target: search.getAttribute('hx-target'),
            swap: 'innerHTML',
        });
    }""")
    from playwright.sync_api import expect

    checkboxes = multi.locator('input[type="checkbox"]')
    expect(checkboxes.first).to_be_attached(timeout=3000)
    assert checkboxes.count() >= 1


@pytest.mark.e2e
def test_multi_select_htmx_select_creates_hidden_inputs(multi_select_page):
    """Selecting items in htmx mode creates hidden inputs for form submission."""
    multi = multi_select_page.locator("details.dropdown.multiselect").nth(2)
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(200)
    multi_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.multiselect');
        const search = dds[2].querySelector('input[type="text"]');
        htmx.ajax('GET', search.getAttribute('hx-get') + '?q=&type=multiselect&name=languages_htmx', {
            target: search.getAttribute('hx-target'),
            swap: 'innerHTML',
        });
    }""")
    from playwright.sync_api import expect

    expect(multi.locator('input[type="checkbox"]').first).to_be_attached(timeout=3000)
    multi_select_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.multiselect');
        const cbs = dds[2].querySelectorAll('input[type="checkbox"]');
        if (cbs.length >= 2) {
            cbs[0].checked = true;
            cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
            cbs[1].checked = true;
            cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
        }
    }""")
    multi_select_page.wait_for_timeout(300)
    hidden = multi.locator('input[type="hidden"][name="languages_htmx"]')
    assert hidden.count() >= 2


@pytest.mark.e2e
def test_multi_select_wrapper_has_id_e2e(multi_select_page):
    """The <details> wrapper has an id containing '_multiselect'."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    wrapper_id = multi.get_attribute("id")
    assert wrapper_id is not None
    assert "_multiselect" in wrapper_id


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# MultiSelect fields on the /multi-select/ page are all required=False, so
# submitting without values does not trigger visible validation errors.
# A dedicated error-flow test would require a page with a required=True
# MultiSelect — that page does not exist yet.  Tracked as a coverage gap.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_multi_select_morph_preserves_values(multi_select_page):
    """Checked options survive an htmx form morph."""
    from tests.e2e.conftest import submit

    multi_select_page.evaluate("""
        document.querySelector('details.dropdown.multiselect').open = true;
    """)
    multi_select_page.wait_for_timeout(200)
    multi_select_page.evaluate("""
        const dd = document.querySelector('details.dropdown.multiselect');
        const cbs = dd.querySelectorAll('input[type="checkbox"]');
        cbs[0].checked = true;
        cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
        cbs[2].checked = true;
        cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
    """)
    multi_select_page.wait_for_timeout(200)
    multi_select_page.evaluate("""
        document.querySelector('details.dropdown.multiselect').open = false;
    """)
    multi_select_page.wait_for_timeout(100)
    submit(multi_select_page)
    checked = multi_select_page.evaluate("""
        [...document.querySelectorAll('details.dropdown.multiselect input[type="checkbox"]:checked')]
            .map(cb => cb.value)
    """)
    assert "py" in checked
    assert "go" in checked


@pytest.mark.e2e
def test_multi_select_morph_preserves_dropdown_open(multi_select_page):
    """An open dropdown stays open after a morph."""
    multi_select_page.evaluate("""
        document.querySelector('details.dropdown.multiselect').open = true;
    """)
    multi_select_page.wait_for_timeout(200)
    multi_select_page.evaluate("""
        document.querySelector('form[hx-post]').noValidate = true;
        document.querySelector('form[hx-post] button[type="submit"]').click();
    """)
    multi_select_page.wait_for_timeout(500)
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    assert multi.get_attribute("open") is not None


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.


@pytest.mark.screenshot
def test_multi_select_screenshot_default(multi_select_page):
    """Visual snapshot: MultiSelect in default (closed) state."""
    wrapper = multi_select_page.locator("details.dropdown.multiselect").first
    wrapper.screenshot(path="test-results/multi-select-default-actual.png")


@pytest.mark.screenshot
def test_multi_select_screenshot_open(multi_select_page):
    """Visual snapshot: MultiSelect with dropdown open."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    multi_select_page.evaluate("""
        document.querySelector('details.dropdown.multiselect').open = true;
    """)
    multi_select_page.wait_for_timeout(100)
    multi.screenshot(path="test-results/multi-select-open-actual.png")


@pytest.mark.screenshot
def test_multi_select_screenshot_selected(multi_select_page):
    """Visual snapshot: MultiSelect with at least 3 options selected."""
    multi = multi_select_page.locator("details.dropdown.multiselect").first
    multi.locator("summary").click()
    multi_select_page.wait_for_timeout(100)
    multi_select_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.multiselect');
        ['py', 'js', 'go'].forEach(v => {
            const cb = dd.querySelector(`input[value="${v}"]`);
            if (cb) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            }
        });
    }""")
    multi_select_page.wait_for_timeout(100)
    multi.screenshot(path="test-results/multi-select-selected-actual.png")
