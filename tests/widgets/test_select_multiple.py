"""SelectMultiple tests, including server-side search loading and failure UX (level 6b)."""

from __future__ import annotations

import json

import pytest
from django import forms
from django.http import QueryDict
from django.utils import translation
from django.utils.safestring import mark_safe

from django_formwork import ChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.search import SEARCH_PAGE_SIZE
from django_formwork.widgets import SelectMultiple

from .conftest import open_dropdown, render_form, render_widget, server_widget, submit


class SelectMultipleForm(FormworkForm):
    """Form fixture for SelectMultiple integration tests."""

    tags = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B"), ("c", "C")],
        widget=SelectMultiple(choices=[("a", "A"), ("b", "B"), ("c", "C")]),
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_select_multiple_choices_stored():
    """Choices passed to constructor are available via widget.choices."""
    widget = SelectMultiple(choices=[("py", "Python"), ("js", "JavaScript")])
    assert list(widget.choices) == [("py", "Python"), ("js", "JavaScript")]


@pytest.mark.unit
def test_select_multiple_get_context_search_url_set_past_one_page():
    """A registered search with more choices than one page names its endpoint."""
    widget = server_widget(SelectMultiple)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["search_url"].startswith("/__formwork__/search/")


@pytest.mark.unit
def test_select_multiple_get_context_search_url_none_when_unregistered():
    """get_context() leaves search_url None when no registry entry is attached."""
    widget = SelectMultiple(choices=[("a", "A")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None


@pytest.mark.unit
def test_select_multiple_get_context_show_search_false_for_few():
    """show_search is False when choices < search_threshold and no search_url."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is False


@pytest.mark.unit
def test_select_multiple_get_context_show_search_true_for_many():
    """show_search is True when choices > search_threshold (10)."""
    choices = [(str(i), f"Option {i}") for i in range(11)]
    widget = SelectMultiple(choices=choices)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_select_multiple_get_context_show_search_true_in_server_mode():
    """show_search opens up-front when the list is past one page."""
    widget = server_widget(SelectMultiple)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is True


@pytest.mark.unit
def test_select_multiple_get_context_show_search_false_when_registered_count_below_threshold():
    """A registered search with few choices keeps the search input closed."""
    widget = server_widget(SelectMultiple, count=5)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["show_search"] is False


@pytest.mark.unit
def test_select_multiple_get_context_optgroups_have_icon():
    """Each option in get_context() optgroups has an 'icon' key."""
    widget = SelectMultiple(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", [], {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            assert "icon" in option


@pytest.mark.unit
def test_select_multiple_get_context_icon_populated():
    """ChoiceLabel icons are reflected in option['icon']."""
    widget = SelectMultiple(
        choices=[
            ("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>"))),
            ("b", "Beta"),
        ],
    )
    ctx = widget.get_context("test", [], {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["icon"] == "<svg>icon</svg>"
            else:
                assert option["icon"] == ""


@pytest.mark.unit
def test_select_multiple_selected_json_empty_list():
    """selected_json is '[]' when search_url set but no values selected."""
    widget = server_widget(SelectMultiple)
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert json.loads(ctx["widget"]["selected_json"]) == []


@pytest.mark.unit
def test_select_multiple_selected_json_with_value():
    """selected_json pairs each selected value with what the toggle shows for it."""
    widget = server_widget(SelectMultiple)
    ctx = widget.get_context("test", ["1", "22"], {"id": "id_test"})
    assert json.loads(ctx["widget"]["selected_json"]) == [["1", "Item 1"], ["22", "Item 22"]]


@pytest.mark.unit
def test_select_multiple_value_from_datadict_returns_list():
    """value_from_datadict returns a list of selected values."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    data = QueryDict("field=a&field=c")
    result = widget.value_from_datadict(data, {}, "field")
    assert result == ["a", "c"]


@pytest.mark.unit
def test_select_multiple_value_from_datadict_empty():
    """value_from_datadict returns empty list when no values submitted."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "field")
    assert result == []


@pytest.mark.unit
def test_select_multiple_value_from_datadict_single():
    """value_from_datadict returns a single-item list when one value submitted."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    data = QueryDict("field=b")
    result = widget.value_from_datadict(data, {}, "field")
    assert result == ["b"]


@pytest.mark.unit
def test_select_multiple_search_threshold_default():
    """search_threshold is 10 by default, shared with Select."""
    widget = SelectMultiple(choices=[])
    assert widget.search_threshold == 10


@pytest.mark.unit
def test_select_multiple_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = SelectMultiple(choices=[("a", "A")])
    ctx = widget.get_context("field", None, {"id": "id_field"})
    assert ctx["widget"]["name"] == "field"


@pytest.mark.unit
def test_select_multiple_renders_without_id():
    """Widget renders without an id attribute."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="field", attrs={})
    details = soup.find("details")
    assert details is not None


@pytest.mark.unit
def test_select_multiple_optgroup_rendering():
    """Grouped choices render all options from all groups."""
    choices = [
        ("Fruits", [("apple", "Apple"), ("banana", "Banana")]),
        ("Vegs", [("carrot", "Carrot")]),
    ]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="food", attrs={"id": "id_food"})
    checkboxes = soup.find_all("input", attrs={"type": "checkbox"})
    values = {cb["value"] for cb in checkboxes}
    assert values == {"apple", "banana", "carrot"}


# ─── Level 1c: Grouped rendering (optgroup headers + filter scaffolding) ─


@pytest.mark.unit
def test_select_multiple_grouped_renders_group_headers():
    """Grouped choices render a ``<li class='menu-title'>`` for each group."""
    choices = [
        ("Fruits", [("apple", "Apple"), ("banana", "Banana")]),
        ("Vegs", [("carrot", "Carrot")]),
    ]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="food", attrs={"id": "id_food"})
    headers = soup.find_all("li", class_="menu-title")
    assert [h.text.strip() for h in headers] == ["Fruits", "Vegs"]


@pytest.mark.unit
def test_select_multiple_no_group_headers_for_flat_choices():
    """Flat choices produce no ``menu-title`` headers."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    headers = soup.find_all("li", class_="menu-title")
    assert headers == []


@pytest.mark.unit
def test_select_multiple_group_header_precedes_its_rows():
    """A group heading is filtered by the rows after it, so its labels stay in the DOM."""
    choices = [("Group", [("a", "Alpha"), ("b", "Beta")])]
    widget = SelectMultiple(choices=choices, show_search=True)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    header = soup.find("li", class_="menu-title")
    assert header["x-show"] == "matches($el)"
    assert header.has_attr("data-group")
    assert [li["data-label"] for li in header.find_next_siblings("li")] == ["Alpha", "Beta"]


@pytest.mark.unit
def test_select_multiple_grouped_options_keep_icons():
    """Icons from ChoiceLabel render inside grouped option labels."""
    choices = [
        (
            "Group",
            [
                ("a", ChoiceLabel("Alpha", icon=mark_safe("<svg>a</svg>"))),
                ("b", "Beta"),
            ],
        ),
    ]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="test")
    a_label = soup.find("input", value="a").parent
    assert "<svg>a</svg>" in str(a_label)


# ─── Level 1d: Keyboard navigation scaffolding ───────────────────────────


@pytest.mark.unit
def test_select_multiple_keydown_handlers_on_wrapper():
    """The ``<details>`` wrapper has @keydown handlers for arrows and enter."""
    widget = SelectMultiple(choices=[("a", "A")])
    html = widget.render("test", [])
    assert "@keydown.arrow-down" in html
    assert "@keydown.arrow-up" in html
    assert "@keydown.enter" in html


@pytest.mark.unit
def test_select_multiple_keydown_invokes_nav_methods():
    """Keydown handlers call the component's nav and enter methods."""
    widget = SelectMultiple(choices=[("a", "A")])
    html = widget.render("test", [])
    assert "onNav($event, 1)" in html
    assert "onNav($event, -1)" in html
    assert "onEnter($event)" in html


@pytest.mark.unit
def test_select_multiple_xdata_binds_alpine_component():
    """Both client- and htmx-mode templates bind to the formworkSelectMultiple component."""
    plain = SelectMultiple(choices=[("a", "A")]).render("test", [])
    htmx_mode = server_widget(SelectMultiple).render("test", [])
    assert 'x-data="formworkSelectMultiple"' in plain
    assert 'x-data="formworkSelectMultiple"' in htmx_mode


@pytest.mark.unit
def test_select_multiple_options_have_data_value():
    """Each option label carries ``data-value`` so nav can target it."""
    widget = SelectMultiple(choices=[("py", "Python"), ("js", "JS")])
    soup = render_widget(widget, name="test")
    labels = soup.find_all(attrs={"data-value": True})
    values = {lbl["data-value"] for lbl in labels}
    assert values == {"py", "js"}


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_select_multiple_renders_details_dropdown():
    """Rendered HTML has a <details class='dropdown'> wrapper."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="dropdown")
    assert details is not None


@pytest.mark.unit
def test_select_multiple_renders_widget_class_on_details():
    """The <details> wrapper has the 'formwork-select-multiple' class."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="formwork-select-multiple")
    assert details is not None


@pytest.mark.unit
def test_select_multiple_renders_summary_trigger():
    """Rendered HTML has a <summary> element with 'text-left' class."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    summary = soup.find("summary")
    assert summary is not None
    # DaisyUI .select is applied via CSS @apply, not directly in HTML
    assert "text-left" in summary.get("class", [])


@pytest.mark.unit
def test_select_multiple_open_icon_replaces_the_caret():
    """The toggle keeps DaisyUI's caret unless open_icon names an icon to show in its place."""
    default = render_widget(SelectMultiple(choices=[("a", "A")]), name="test").find("summary")
    custom = render_widget(SelectMultiple(choices=[("a", "A")], open_icon="filter"), name="test").find("summary")
    assert default.select("i.icon") == []
    assert "bg-none" not in default["class"]
    assert custom.select_one("i.icon-filter") is not None
    assert "bg-none" in custom["class"]


@pytest.mark.unit
def test_select_multiple_renders_dropdown_content():
    """A <div class='dropdown-content'> is present."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    dropdown = soup.find("div", class_="dropdown-content")
    assert dropdown is not None


@pytest.mark.unit
def test_select_multiple_options_in_list_items():
    """Options render as <li> elements inside a <ul>."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    items = soup.find("div", class_="dropdown-content").find("ul").find_all("li")
    assert len(items) == 2


@pytest.mark.unit
def test_select_multiple_renders_hidden_checkboxes():
    """Each option renders as an <input type='checkbox'> with class 'hidden'."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    soup = render_widget(widget, name="test")
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    assert len(checkboxes) == 3
    for cb in checkboxes:
        assert "hidden" in cb.get("class", [])


@pytest.mark.unit
def test_select_multiple_checkbox_values():
    """Checkboxes have correct values matching the choices."""
    widget = SelectMultiple(choices=[("py", "Python"), ("js", "JS")])
    soup = render_widget(widget, name="lang")
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    values = [cb["value"] for cb in checkboxes]
    assert values == ["py", "js"]


@pytest.mark.unit
def test_select_multiple_checkbox_name():
    """Checkboxes use the widget's field name."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="field")
    cb = soup.find("input", {"type": "checkbox"})
    assert cb["name"] == "field"


@pytest.mark.unit
def test_select_multiple_selected_values_checked():
    """Pre-selected values render as checked checkboxes."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B"), ("c", "C")])
    soup = render_widget(widget, name="test", value=["a", "c"])
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    checked = [cb["value"] for cb in checkboxes if cb.has_attr("checked")]
    assert checked == ["a", "c"]


@pytest.mark.unit
def test_select_multiple_checkmark_present():
    """Each option has a <span class='formwork-check opacity-0'> checkmark indicator."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    check = soup.find("span", class_="formwork-check")
    assert check is not None
    assert "opacity-0" in check.get("class", [])


@pytest.mark.unit
def test_select_multiple_checkmark_after_label_text():
    """Label structure is: input, text span, trailing checkmark span."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    label = soup.find("label")
    children = [c for c in label.children if getattr(c, "name", None)]
    assert [c.name for c in children] == ["input", "span", "span"]
    assert "formwork-check" in children[-1].get("class", [])
    assert "formwork-check" not in children[1].get("class", [])


@pytest.mark.unit
def test_select_multiple_alpine_x_data():
    """The <details> wrapper binds to the formworkSelectMultiple Alpine.data component."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("details", attrs={"x-data": "formworkSelectMultiple"})
    assert wrapper is not None


@pytest.mark.unit
def test_select_multiple_option_labels():
    """Choice labels are rendered as text spans inside list items."""
    widget = SelectMultiple(choices=[("a", "Alpha"), ("b", "Beta")])
    soup = render_widget(widget, name="test")
    spans = soup.find_all("span", class_="select-none")
    texts = [s.get_text(strip=True) for s in spans]
    assert "Alpha" in texts
    assert "Beta" in texts


@pytest.mark.unit
def test_select_multiple_search_hidden_for_few_choices():
    """Search input is absent when choices < search_threshold."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    search = soup.find("input", {"type": "text", "x-model": "search"})
    assert search is None


@pytest.mark.unit
def test_select_multiple_search_shown_for_many_choices():
    """The search box shows after the choices pass search_threshold."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="test")
    assert soup.find("input", {"type": "search", "x-model": "search"}) is not None
    assert soup.find("details")["data-show-search"] == "true"


@pytest.mark.unit
def test_select_multiple_no_results_alert_for_many_choices():
    """A DaisyUI alert-info alert-soft is rendered when show_search is active."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="test")
    alert = soup.find("div", attrs={"x-show": "noResults"}).find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert" in alert["class"]
    assert "alert-info" in alert["class"]


@pytest.mark.unit
def test_select_multiple_summary_static_placeholder_class_tracks_selection():
    """The placeholder class is server-rendered only while nothing is selected."""
    widget = SelectMultiple(choices=[("a", "A"), ("b", "B")])
    soup = render_widget(widget, name="test")
    assert "formwork-placeholder" in soup.find("summary")["class"]
    soup = render_widget(widget, name="test", value=["a"])
    assert "formwork-placeholder" not in soup.find("summary")["class"]


@pytest.mark.unit
def test_select_multiple_summary_server_renders_selected_labels():
    """Selected labels appear in the summary at first paint, before Alpine."""
    widget = SelectMultiple(choices=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")])
    soup = render_widget(widget, name="test", value=["a", "b"])
    span = soup.select_one("summary [x-html]")
    assert span.get_text(strip=True) == "Alpha, Beta"


@pytest.mark.unit
def test_select_multiple_summary_server_escapes_label_text():
    """HTML in labels is escaped in the server-rendered summary."""
    widget = SelectMultiple(choices=[("a", "<b>Bold</b>")])
    soup = render_widget(widget, name="test", value=["a"])
    span = soup.select_one("summary [x-html]")
    assert span.find("b") is None
    assert span.get_text(strip=True) == "<b>Bold</b>"


@pytest.mark.unit
def test_select_multiple_summary_server_renders_count_above_cutoff():
    """More than three selections collapse to 'N selected' server-side too."""
    choices = [(str(i), f"Option {i}") for i in range(5)]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="test", value=["0", "1", "2", "3"])
    span = soup.select_one("summary [x-html]")
    assert span.get_text(strip=True) == "4 selected"


@pytest.mark.unit
@pytest.mark.usefixtures("pseudo_catalog")
def test_select_multiple_count_is_translated_on_server_and_client():
    """The server count and the plural forms the component counts with share the active language."""
    widget = SelectMultiple(choices=[(str(i), f"Option {i}") for i in range(5)])
    with translation.override("de"):
        soup = render_widget(widget, name="test", value=["0", "1", "2", "3"])
    assert soup.select_one("summary [x-html]").get_text(strip=True) == "⟦4 selected⟧"
    assert json.loads(soup.select_one("details")["data-count-text"]) == {"other": "⟦%(count)s selected⟧"}


@pytest.mark.unit
def test_select_multiple_summary_server_renders_selection_in_search_mode():
    """htmx-mode widgets derive the summary from the initial selected pairs."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", value=["1"], attrs={"id": "id_test"})
    span = soup.select_one("summary [x-html]")
    assert span.get_text(strip=True) == "Item 1"


@pytest.mark.unit
def test_select_multiple_aria_invalid_on_summary():
    """aria-invalid='true' is forwarded to the <summary> trigger."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
    summary = soup.find("summary")
    assert summary["aria-invalid"] == "true"


@pytest.mark.unit
def test_select_multiple_no_aria_invalid_when_valid():
    """aria-invalid is absent on <summary> when no error."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-invalid")


@pytest.mark.unit
def test_select_multiple_aria_describedby_on_summary():
    """aria-describedby is forwarded to the <summary> trigger."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-describedby": "id_test_helptext"})
    summary = soup.find("summary")
    assert summary["aria-describedby"] == "id_test_helptext"


@pytest.mark.unit
def test_select_multiple_no_aria_describedby_by_default():
    """aria-describedby is absent on <summary> without help text or errors."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    summary = soup.find("summary")
    assert not summary.has_attr("aria-describedby")


@pytest.mark.unit
def test_select_multiple_wrapper_has_id():
    """<details> gets id='{id}_wrapper' when attrs contain an id."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select-multiple")
    assert details["id"] == "id_test_wrapper"


@pytest.mark.unit
def test_select_multiple_no_wrapper_id_without_id():
    """<details> has no id when no id attr is passed."""
    widget = SelectMultiple(choices=[("a", "A")])
    soup = render_widget(widget, name="test")
    details = soup.find("details", class_="formwork-select-multiple")
    assert not details.has_attr("id")


@pytest.mark.unit
def test_select_multiple_htmx_attrs_when_registered():
    """Search input gets hx-get, hx-trigger, hx-target, hx-swap when registered."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="lang", attrs={"id": "id_lang"})
    search_input = soup.find("input", {"type": "search"})
    assert search_input is not None
    assert search_input["hx-get"].startswith("/__formwork__/search/")
    assert search_input["hx-trigger"] == "input changed delay:300ms"
    assert search_input["hx-target"] == "next ul"
    assert search_input["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_select_multiple_no_htmx_attrs_without_search_url():
    """Search input has no htmx attributes when search_url is absent."""
    choices = [(str(i), f"Option {i}") for i in range(21)]
    widget = SelectMultiple(choices=choices)
    soup = render_widget(widget, name="test")
    search_input = soup.find("input", {"type": "search"})
    assert not search_input.has_attr("hx-get")


@pytest.mark.unit
def test_select_multiple_renders_no_results_alert_when_initial_options_empty():
    """An empty list still communicates state: the listbox carries
    the same ``role=status`` alert that the htmx response would render."""
    widget = SelectMultiple(choices=[])
    soup = render_widget(widget, attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    alert = listbox.find("div", attrs={"role": "status"})
    assert alert is not None
    assert "alert-info" in alert["class"]
    assert "No results" in alert.get_text()


@pytest.mark.unit
def test_select_multiple_htmx_mode_passes_selected_json():
    """Server mode puts the selected value/label pairs on ``data-selected`` for the component."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details")
    assert details["x-data"] == "formworkSelectMultiple"
    assert details["data-has-search-url"] == "true"
    assert json.loads(details["data-selected"]) == []


@pytest.mark.unit
def test_select_multiple_htmx_mode_posts_selection_from_hidden_inputs():
    """A searched list holds one page, so server mode posts the selection from hidden inputs."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", value=["0", "1"], attrs={"id": "id_test"})
    values = soup.find("div", attrs={"x-ref": "values"})
    assert values["data-name"] == "test"
    assert [i["value"] for i in values.find_all("input", {"type": "hidden", "name": "test"})] == ["0", "1"]
    assert all(not cb.has_attr("name") for cb in soup.find_all("input", {"type": "checkbox"}))


@pytest.mark.unit
def test_select_multiple_htmx_wrapper_has_id():
    """htmx mode also derives the <details> id from the widget id."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select-multiple")
    assert details["id"] == "id_test_wrapper"


@pytest.mark.unit
def test_select_multiple_server_mode_renders_one_page_and_a_load_more_button():
    """Past one page the listbox holds the first page; "Load more" fetches the next."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    values = [label["data-value"] for label in listbox.find_all("label", attrs={"data-value": True})]
    assert values == [str(i) for i in range(SEARCH_PAGE_SIZE)]
    more = listbox.select_one('[role="status"] button[hx-get]')
    assert f"offset={SEARCH_PAGE_SIZE}" in more["hx-get"]


@pytest.mark.unit
def test_select_multiple_server_mode_options_include_icons():
    """Server-mode rows keep the icon of their ChoiceLabel."""
    widget = server_widget(SelectMultiple, icons=True)
    soup = render_widget(widget, attrs={"id": "id_x"})
    first = soup.find("li").find("label")
    assert "📍0" in first.get_text()


@pytest.mark.unit
def test_select_multiple_client_mode_renders_every_choice():
    """Without server search the browser filters, so every choice is an option."""
    widget = SelectMultiple(choices=[("a", "Alpha"), ("b", "Beta")])
    ctx = widget.get_context("test", [], {"id": "id_test"})
    assert ctx["widget"]["search_url"] is None
    assert [o["value"] for o in ctx["widget"]["options"]] == ["a", "b"]


@pytest.mark.unit
def test_select_multiple_renders_error_alert_when_search_url():
    """The error alert is rendered as a plain DaisyUI alert, hidden by
    default via x-show='hasError'."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert is not None
    assert alert.get("x-show") == "hasError"
    assert "alert" in alert["class"]
    assert "alert-error" in alert["class"]
    assert "Search failed" in alert.get_text()


@pytest.mark.unit
def test_select_multiple_error_alert_hidden_until_a_search_fails():
    """The error alert waits on ``hasError``, which only a failed search sets."""
    widget = SelectMultiple(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert["x-show"] == "hasError"
    assert alert.has_attr("x-cloak")


@pytest.mark.unit
def test_select_multiple_root_wires_htmx_handlers():
    """The root hears both the search and "Load more"; only the search box sets the query.

    ``hasError`` follows the response only; resetting it on request would flash the old list.
    Swapped-in rows render unchecked, so every swap re-checks them from the selection.
    """
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="lang", attrs={"id": "id_lang"})
    root = soup.find("details", id="id_lang_wrapper")
    assert "@htmx:before:request" not in root.attrs
    assert root["@htmx:before:swap"] == "onSearchBeforeSwap($event)"
    assert root["@htmx:after:swap"] == "syncChecked()"
    assert root["@htmx:response:error"] == "onSearchError()"
    assert root["@htmx:error"] == "onSearchError()"
    search = root.find("input", {"type": "search"})
    assert search["@htmx:config:request"] == "onSearchConfig($event)"
    assert "@htmx:before:swap" not in search.attrs


@pytest.mark.unit
def test_select_multiple_listbox_hidden_only_on_error():
    """The listbox stays visible at all times except when an error occurs."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", id="id_test_listbox")
    assert listbox.get("x-show") == "!hasError"


@pytest.mark.unit
def test_select_multiple_has_search_url_flag_when_search_url():
    """data-has-search-url='true' selects the Map-tracked branch of the component."""
    widget = server_widget(SelectMultiple)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    details = soup.find("details", class_="formwork-select-multiple")
    assert details["data-has-search-url"] == "true"


@pytest.mark.unit
def test_select_multiple_icons_rendered():
    """ChoiceLabel icons appear in the rendered HTML."""
    widget = SelectMultiple(
        choices=[
            ("a", ChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_select_multiple_no_icon_when_not_provided():
    """No <img> elements rendered when no ChoiceLabel icons."""
    widget = SelectMultiple(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_select_multiple_renders_via_form(renderer):
    """Field renders the <details class="formwork-select-multiple"> dropdown."""
    form = SelectMultipleForm()
    soup = render_form(form, renderer=renderer)
    details = soup.find("details", class_="formwork-select-multiple")
    assert details is not None


@pytest.mark.integration
def test_select_multiple_option_data_value_round_trips_raw_value(renderer):
    """Regression: escapejs on the option data-value mangled a hyphenated value."""

    class HyphenForm(FormworkForm):
        tags = forms.MultipleChoiceField(
            choices=[("uuid-1234", "Ticket")],
            widget=SelectMultiple(choices=[("uuid-1234", "Ticket")]),
        )

    soup = render_form(HyphenForm(), renderer=renderer)
    label = soup.find("label", attrs={"data-value": True})
    assert label is not None
    assert label["data-value"] == "uuid-1234"


@pytest.mark.integration
def test_select_multiple_form_wraps_in_fieldset(renderer):
    """Field template wraps the SelectMultiple in a fieldset with a stable id."""
    form = SelectMultipleForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_tags_field")
    assert fieldset is not None


@pytest.mark.integration
def test_select_multiple_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the summary trigger."""
    form = SelectMultipleForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary.get("aria-invalid") == "true"


@pytest.mark.integration
def test_select_multiple_error_state_aria_describedby(renderer):
    """Django's auto aria-describedby (→ the error container) reaches the summary."""
    form = SelectMultipleForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    summary = soup.find("summary")
    assert summary.get("aria-describedby") == "id_tags_error"


@pytest.mark.integration
def test_select_multiple_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = SelectMultipleForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_tags_error", class_="tooltip-content")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_select_multiple_form_prefix_handling(renderer):
    """Form prefix propagates to widget id and wrapper id."""
    form = SelectMultipleForm(prefix="cfg")
    soup = render_form(form, renderer=renderer)
    details = soup.find("details", class_="formwork-select-multiple")
    assert details is not None
    assert details.get("id") == "id_cfg-tags_wrapper"


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_select_multiple_renders_on_page(select_multiple_page):
    """SelectMultiple dropdown is visible on the /select-multiple/ page."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    expect(multi).to_be_visible()


@pytest.mark.e2e
def test_select_multiple_open_shows_checkboxes(select_multiple_page):
    """Opening the dropdown reveals checkbox inputs."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    summary = multi.locator("summary")
    summary.click()
    select_multiple_page.wait_for_timeout(100)
    checkboxes = multi.locator('input[type="checkbox"]')
    assert checkboxes.count() >= 2


@pytest.mark.e2e
def test_select_multiple_select_multiple(select_multiple_page):
    """User can check multiple options via JS dispatch."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    select_multiple_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.formwork-select-multiple');
        ['py', 'go'].forEach(v => {
            const cb = dd.querySelector(`input[value="${v}"]`);
            cb.checked = true;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        });
    }""")
    select_multiple_page.wait_for_timeout(100)
    assert multi.locator('input[value="py"]').is_checked()
    assert multi.locator('input[value="go"]').is_checked()


@pytest.mark.e2e
def test_select_multiple_summary_shows_selection(select_multiple_page):
    """After selecting an option the summary reflects the selection."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    summary = multi.locator("summary")
    summary.click()
    select_multiple_page.wait_for_timeout(100)
    select_multiple_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.formwork-select-multiple');
        const cb = dd.querySelector('input[value="py"]');
        cb.checked = true;
        cb.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    select_multiple_page.wait_for_timeout(100)
    summary_text = summary.text_content()
    assert "Python" in summary_text or "1" in summary_text


@pytest.mark.e2e
def test_select_multiple_summary_shows_picked_icons_and_escapes_labels(select_multiple_page):
    """Each pick shows its icon in the closed toggle, and its label stays text."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("#id_countries_icons_wrapper")
    toggle = multi.locator("summary [x-html]")
    multi.locator("summary").click()
    multi.locator('input[value="ar"]').dispatch_event("click")
    multi.locator('input[value="br"]').dispatch_event("click")
    expect(toggle).to_have_text("\U0001f1e6\U0001f1f7 Argentina, \U0001f1e7\U0001f1f7 Brazil")

    canada = multi.locator('input[value="ca"]')
    canada.evaluate("cb => { cb.dataset.label = '<b>Canada</b>'; }")
    canada.dispatch_event("click")
    expect(toggle).to_contain_text("\U0001f1e8\U0001f1e6 <b>Canada</b>")
    expect(toggle.locator("b")).to_have_count(0)


@pytest.mark.e2e
def test_select_multiple_no_search_bar_for_plain(select_multiple_page):
    """Plain SelectMultiple with 4 choices hides its search input (below threshold)."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    expect(multi.locator('input[type="search"]')).to_be_hidden()


@pytest.mark.e2e
def test_select_multiple_icons_has_search_bar(select_multiple_page):
    """Icons SelectMultiple with 31 countries shows a search bar (above threshold)."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(1)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    search = multi.locator('input[type="search"]')
    assert search.count() == 1


@pytest.mark.e2e
def test_select_multiple_icons_has_many_checkboxes(select_multiple_page):
    """Icons SelectMultiple has 31 country checkboxes."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(1)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    checkboxes = multi.locator('input[type="checkbox"]')
    assert checkboxes.count() == 31


@pytest.mark.e2e
def test_select_multiple_htmx_renders(select_multiple_page):
    """htmx SelectMultiple is visible on the page."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    expect(multi).to_be_visible()


@pytest.mark.e2e
def test_select_multiple_htmx_search_replaces_the_rows(select_multiple_page):
    """The listbox opens on one page of 25 languages; a search swaps in the server's matches."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    multi.locator("summary").click()
    checkboxes = multi.locator('input[type="checkbox"]')
    expect(checkboxes).to_have_count(20)
    expect(multi.get_by_role("button", name="Load more")).to_be_attached()
    _type_search(select_multiple_page, 2, "Zig")
    expect(checkboxes).to_have_count(1, timeout=10000)
    assert checkboxes.get_attribute("value") == "zig"


@pytest.mark.e2e
def test_select_multiple_htmx_selection_stays_checked_when_load_more_brings_it_back(select_multiple_page):
    """A row picked from a search is checked again when "Load more" renders it after the search clears."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    multi.locator("summary").click()
    _type_search(select_multiple_page, 2, "Zig")
    zig = multi.locator('input[type="checkbox"][value="zig"]')
    expect(multi.locator('input[type="checkbox"]')).to_have_count(1, timeout=10000)
    zig.dispatch_event("click")
    expect(zig).to_be_checked()
    _type_search(select_multiple_page, 2, "")
    expect(multi.locator('input[type="checkbox"]')).to_have_count(20, timeout=10000)
    multi.get_by_role("button", name="Load more").click()
    expect(multi.locator('input[type="checkbox"]')).to_have_count(25, timeout=10000)
    expect(zig).to_be_checked()


@pytest.mark.e2e
def test_select_multiple_htmx_select_creates_hidden_inputs(select_multiple_page):
    """Selecting items in htmx mode creates hidden inputs for form submission."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(200)
    select_multiple_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select-multiple');
        const cbs = dds[2].querySelectorAll('input[type="checkbox"]');
        if (cbs.length >= 2) {
            cbs[0].checked = true;
            cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
            cbs[1].checked = true;
            cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
        }
    }""")
    select_multiple_page.wait_for_timeout(300)
    hidden = multi.locator('input[type="hidden"][name="languages_htmx"]')
    assert hidden.count() >= 2


_ECHO = """async (selected) => {
    const dd = document.querySelectorAll('details.dropdown.formwork-select-multiple')[2];
    const echo = dd.cloneNode(true);
    echo.dataset.selected = JSON.stringify(selected);
    const values = selected.map(([v]) => v);
    for (const cb of echo.querySelectorAll('input[type="checkbox"]')) cb.toggleAttribute('checked', values.includes(cb.value));
    const holder = echo.querySelector('[x-ref="values"]');
    holder.replaceChildren(...values.map((value) => Object.assign(document.createElement('input'),
        {type: 'hidden', name: holder.dataset.name, value})));
    await htmx.swap({text: echo.outerHTML, target: dd, swap: 'outerMorph'});
}"""


@pytest.mark.e2e
def test_select_multiple_htmx_stale_echo_keeps_local_state(select_multiple_page):
    """A stale morph keeps the newer local selection; a confirming morph re-arms server updates.

    Checkboxes and hidden inputs keep tracking the local selection, so the next submit carries all of it.
    """
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    multi.locator("summary").click()
    from playwright.sync_api import expect

    expect(multi.locator('input[type="checkbox"]').first).to_be_attached(timeout=10000)
    values = select_multiple_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select-multiple');
        const cbs = dds[2].querySelectorAll('input[type="checkbox"]');
        [cbs[0], cbs[1]].forEach(cb => {
            cb.checked = true;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        });
        return [cbs[0].value, cbs[1].value];
    }""")

    state = """() => {
        const dd = document.querySelectorAll('details.dropdown.formwork-select-multiple')[2];
        const data = Alpine.$data(dd);
        return {
            map: Object.keys(data.selected).sort(),
            hidden: [...dd.querySelectorAll('input[type="hidden"][name="languages_htmx"]')]
                .map(i => i.value).filter(Boolean).sort(),
            checked: [...dd.querySelectorAll('input[type="checkbox"]')].filter(b => b.checked).map(b => b.value).sort(),
        };
    }"""
    both = sorted(values)
    assert select_multiple_page.evaluate(state)["map"] == both

    select_multiple_page.evaluate(_ECHO, [[values[0], "Stale"]])
    result = select_multiple_page.evaluate(state)
    assert result == {"map": both, "hidden": both, "checked": both}, "stale echo clobbered pending local selections"

    select_multiple_page.evaluate(_ECHO, [[v, "Confirmed"] for v in values])
    assert select_multiple_page.evaluate(state) == {"map": both, "hidden": both, "checked": both}

    select_multiple_page.evaluate(_ECHO, [[values[0], "Server"]])
    result = select_multiple_page.evaluate(state)
    assert result == {"map": [values[0]], "hidden": [values[0]], "checked": [values[0]]}


@pytest.mark.e2e
def test_select_multiple_wrapper_has_id_e2e(select_multiple_page):
    """The <details> wrapper has an id ending in '_wrapper'."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    wrapper_id = multi.get_attribute("id")
    assert wrapper_id is not None
    assert wrapper_id.endswith("_wrapper")


@pytest.mark.e2e
def test_select_multiple_popover_survives_morph_attribute_strip(select_multiple_page):
    """Morph swaps (htmx 4) sync attributes back to the server HTML, which
    carries no popover attribute or inline anchor styles; the widget must
    re-assert them and keep an open panel in the top layer."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    panel = multi.locator(".dropdown-content")
    multi.locator("summary").click()
    select_multiple_page.wait_for_function("""() => document.querySelector(
        'details.dropdown.formwork-select-multiple > .dropdown-content').matches(':popover-open')""")

    # Strip the client-added plumbing exactly like a morph: one batch of
    # attribute mutations restoring the server-rendered state.
    select_multiple_page.evaluate("""() => {
        const root = document.querySelector('details.dropdown.formwork-select-multiple');
        const panel = root.querySelector(':scope > .dropdown-content');
        panel.removeAttribute('popover');
        root.removeAttribute('style');
        panel.removeAttribute('style');
    }""")

    expect(panel).to_have_attribute("popover", "manual")
    assert select_multiple_page.evaluate("""() => {
        const root = document.querySelector('details.dropdown.formwork-select-multiple');
        const panel = root.querySelector(':scope > .dropdown-content');
        const anchored = !CSS.supports('anchor-name: --a') ||
            (root.style.anchorName !== '' &&
             panel.style.positionAnchor === root.style.anchorName);
        return panel.matches(':popover-open') && anchored;
    }""")


# ─── Level 5b: E2e, grouped SelectMultiple ─────────────────────────────────
#
# cities_grouped is the 4th SelectMultiple on the page (nth(3)).


@pytest.mark.e2e
def test_select_multiple_grouped_shows_headers(select_multiple_page):
    """Open the grouped SelectMultiple; all three group headers are visible."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(150)
    headers = [h.inner_text().strip() for h in multi.locator("li.menu-title").all() if h.is_visible()]
    assert headers == ["Europe", "Asia", "Americas"]


@pytest.mark.e2e
def test_select_multiple_grouped_filter_hides_empty_groups(select_multiple_page):
    """Typing 'lon' (matches only London in Europe) hides Asia and Americas headers."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(150)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.fill("lon")
    select_multiple_page.wait_for_timeout(100)
    visible_headers = [h.inner_text().strip() for h in multi.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Europe"]


@pytest.mark.e2e
def test_select_multiple_grouped_pick_via_click(select_multiple_page):
    """Clicking a checkbox label inside a group toggles its checked state."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    multi.locator('label[data-value="ldn"]').click()
    expect(multi.locator('input[value="ldn"]')).to_be_checked()
    expect(multi.locator("summary")).to_contain_text("London")


# ─── Level 5c: E2e, search auto-focus ───────────────────────────────────


@pytest.mark.e2e
def test_select_multiple_search_auto_focus_on_open(select_multiple_page):
    """Opening a SelectMultiple with a search box auto-focuses the search input."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    search = multi.locator('.dropdown-content input[type="search"]')
    from playwright.sync_api import expect

    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_select_multiple_search_refocus_on_reopen(select_multiple_page):
    """Closing then reopening re-focuses the search input."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    # Close
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    # Reopen
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    search = multi.locator('.dropdown-content input[type="search"]')
    expect(search).to_be_focused(timeout=2000)


@pytest.mark.e2e
def test_select_multiple_no_search_no_focus_error(select_multiple_page):
    """Opening a search-less SelectMultiple does not raise any console error."""
    errors: list[str] = []
    select_multiple_page.on("pageerror", lambda e: errors.append(str(e)))

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(150)
    assert errors == []


# ─── Level 5d: E2e, keyboard navigation ─────────────────────────────────
#
# Uses the grouped SelectMultiple (nth(3)) which is fixed-size and searchable.
# Keyboard handlers are on the <details> root; the search input naturally
# has focus once the dropdown is open, so events bubble to the handlers.


@pytest.mark.e2e
def test_select_multiple_keyboard_arrowdown_highlights_first(select_multiple_page):
    """ArrowDown from no highlight goes to the first visible option."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    select_multiple_page.wait_for_timeout(50)
    highlighted = multi.locator("li.highlighted > [data-value]")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_multiple_keyboard_arrowdown_navigates(select_multiple_page):
    """Each ArrowDown moves to the next option, skipping group headers."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")  # ldn
    search.press("ArrowDown")  # par
    select_multiple_page.wait_for_timeout(50)
    highlighted = multi.locator("li.highlighted > [data-value]")
    assert highlighted.first.get_attribute("data-value") == "par"
    # Continue: ber, then tyo (skips group header)
    search.press("ArrowDown")
    search.press("ArrowDown")
    select_multiple_page.wait_for_timeout(50)
    assert multi.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "tyo"


@pytest.mark.e2e
def test_select_multiple_keyboard_arrowdown_wraps_to_first(select_multiple_page):
    """Pressing ArrowDown past the last option wraps to the first."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    # 9 options total; 10 ArrowDowns from no-highlight = 9 to last + 1 wrap
    for _ in range(10):
        search.press("ArrowDown")
    select_multiple_page.wait_for_timeout(50)
    assert multi.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_multiple_keyboard_arrowup_wraps_to_last(select_multiple_page):
    """ArrowUp from no highlight goes to the last visible option."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowUp")
    select_multiple_page.wait_for_timeout(50)
    assert multi.locator("li.highlighted > [data-value]").first.get_attribute("data-value") == "mex"


@pytest.mark.e2e
def test_select_multiple_keyboard_filter_skips_hidden_options(select_multiple_page):
    """After filtering, ArrowDown only highlights visible (matching) options."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.fill("lon")  # Matches only "London"
    select_multiple_page.wait_for_timeout(150)
    search.press("ArrowDown")
    search.press("ArrowDown")  # Should wrap back to ldn (only one visible)
    select_multiple_page.wait_for_timeout(50)
    highlighted = multi.locator("li.highlighted > [data-value]")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_multiple_keyboard_enter_toggles_keeps_open(select_multiple_page):
    """Enter toggles the highlighted checkbox; dropdown stays open."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")  # Highlight ldn
    search.press("Enter")
    select_multiple_page.wait_for_timeout(150)
    # Checkbox toggled
    assert multi.locator('input[type="checkbox"][value="ldn"]').is_checked()
    # Dropdown still open
    assert multi.get_attribute("open") is not None
    # Highlight still there
    highlighted = multi.locator("li.highlighted > [data-value]")
    assert highlighted.first.get_attribute("data-value") == "ldn"


@pytest.mark.e2e
def test_select_multiple_keyboard_enter_again_toggles_off(select_multiple_page):
    """Pressing Enter twice on the same option toggles it off again."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    search.press("Enter")
    select_multiple_page.wait_for_timeout(100)
    assert multi.locator('input[type="checkbox"][value="ldn"]').is_checked()
    search.press("Enter")
    select_multiple_page.wait_for_timeout(100)
    assert not multi.locator('input[type="checkbox"][value="ldn"]').is_checked()


@pytest.mark.e2e
def test_select_multiple_keyboard_enter_no_highlight_toggles_first(select_multiple_page):
    """With no highlight, Enter toggles the first visible option."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("Enter")
    select_multiple_page.wait_for_timeout(100)
    assert multi.locator('input[type="checkbox"][value="ldn"]').is_checked()


@pytest.mark.e2e
def test_select_multiple_keyboard_close_clears_highlight(select_multiple_page):
    """Closing the dropdown clears the ``.highlighted`` class."""
    multi = open_dropdown(select_multiple_page, "formwork-select-multiple", 3)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")
    select_multiple_page.wait_for_timeout(50)
    assert multi.locator("li.highlighted > [data-value]").count() == 1
    multi.locator("summary").click()  # close
    select_multiple_page.wait_for_timeout(150)
    assert multi.locator("li.highlighted > [data-value]").count() == 0


# ─── Level 5e: E2e, dirty tracking ───────────────────────────────────────
#
# The /select-multiple/ page ships formwork-core.js but its form does not opt
# in to dirty tracking, so the tests enable it in place: set the opt-in
# attribute and fire the htmx:after:swap event that initAllDirtyForms
# already listens for.


def _type_search(page, index, text):
    """Set the nth SelectMultiple's search input value, firing its input handlers."""
    page.evaluate(
        """([i, text]) => {
            const search = document.querySelectorAll('details.dropdown.formwork-select-multiple')[i]
                .querySelector('.dropdown-content input[type="search"]');
            search.value = text;
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""",
        [index, text],
    )


def _enable_dirty_tracking(page):
    page.evaluate("""() => {
        document.querySelector('form[hx-post]').setAttribute('data-formwork-dirty', '');
        document.dispatchEvent(new Event('htmx:after:swap'));
    }""")


def _toggle_checkbox(page, dropdown_index, value_selector):
    page.evaluate(
        """([index, selector]) => {
            const dd = document.querySelectorAll('details.dropdown.formwork-select-multiple')[index];
            const cb = dd.querySelector(selector);
            cb.checked = !cb.checked;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        [dropdown_index, value_selector],
    )


@pytest.mark.e2e
def test_select_multiple_htmx_dirty_clears_on_revert(select_multiple_page):
    """htmx-mode: selecting then unselecting an option leaves the fieldset clean."""
    import re

    from playwright.sync_api import expect

    _enable_dirty_tracking(select_multiple_page)
    fieldset = select_multiple_page.locator("#id_languages_htmx_field")
    _toggle_checkbox(select_multiple_page, 2, 'input[type="checkbox"]')
    expect(fieldset).to_have_class(re.compile(r"\bformwork-dirty\b"))
    _toggle_checkbox(select_multiple_page, 2, 'input[type="checkbox"]')
    expect(fieldset).not_to_have_class(re.compile(r"\bformwork-dirty\b"))


@pytest.mark.e2e
def test_select_multiple_client_dirty_clears_on_revert(select_multiple_page):
    """Client-mode: checking then unchecking a box leaves the fieldset clean."""
    import re

    from playwright.sync_api import expect

    _enable_dirty_tracking(select_multiple_page)
    fieldset = select_multiple_page.locator("#id_languages_plain_field")
    _toggle_checkbox(select_multiple_page, 0, 'input[value="py"]')
    expect(fieldset).to_have_class(re.compile(r"\bformwork-dirty\b"))
    _toggle_checkbox(select_multiple_page, 0, 'input[value="py"]')
    expect(fieldset).not_to_have_class(re.compile(r"\bformwork-dirty\b"))


@pytest.mark.e2e
def test_select_multiple_htmx_search_keeps_the_dirty_baseline(select_multiple_page):
    """A search swapping rows into the list is not a new baseline: a toggle made before it still counts."""
    import re

    from playwright.sync_api import expect

    _enable_dirty_tracking(select_multiple_page)
    fieldset = select_multiple_page.locator("#id_languages_htmx_field")
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(2)
    multi.locator("summary").click()
    checkboxes = multi.locator('input[type="checkbox"]')
    expect(checkboxes).to_have_count(20)
    _toggle_checkbox(select_multiple_page, 2, 'input[type="checkbox"]')
    expect(fieldset).to_have_class(re.compile(r"\bformwork-dirty\b"))
    _type_search(select_multiple_page, 2, "Zig")
    expect(checkboxes).to_have_count(1, timeout=10000)
    select_multiple_page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    _toggle_checkbox(select_multiple_page, 2, 'input[type="checkbox"][value="zig"]')
    _toggle_checkbox(select_multiple_page, 2, 'input[type="checkbox"][value="zig"]')
    expect(fieldset).to_have_class(re.compile(r"\bformwork-dirty\b"))


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Needs a page with a required SelectMultiple; all /select-multiple/ fields are optional.


@pytest.mark.e2e
def test_select_multiple_failing_search_shows_error_alert(select_multiple_page):
    """When the search endpoint returns 500, the error alert replaces the listbox."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(4)
    select_multiple_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select-multiple');
        dds[4].open = true;
        dds[4].dispatchEvent(new Event('toggle'));
    }""")
    select_multiple_page.wait_for_timeout(200)
    _type_search(select_multiple_page, 4, "x")
    alert = multi.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    assert "Search failed" in alert.text_content()
    expect(multi.locator("ul[role='listbox']")).to_be_hidden()


@pytest.mark.e2e
def test_select_multiple_search_input_works_after_error(select_multiple_page):
    """The search input remains usable after a failure: typing fires a new
    request and the value lands in the input."""
    from playwright.sync_api import expect

    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(4)
    requests: list[str] = []
    select_multiple_page.on("request", lambda r: requests.append(r.url) if "search/" in r.url else None)
    select_multiple_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select-multiple');
        dds[4].open = true;
        dds[4].dispatchEvent(new Event('toggle'));
    }""")
    _type_search(select_multiple_page, 4, "x")
    alert = multi.locator('[role="alert"].alert-error')
    expect(alert).to_be_visible(timeout=10000)
    initial_count = len(requests)
    _type_search(select_multiple_page, 4, "xy")
    # 300ms input-changed debounce + buffer for the request to fire.
    select_multiple_page.wait_for_timeout(500)
    assert len(requests) > initial_count, "expected typing to fire a new search request"
    val = select_multiple_page.evaluate("""() => {
        const dds = document.querySelectorAll('details.dropdown.formwork-select-multiple');
        return dds[4].querySelector('.dropdown-content input[type="search"]').value;
    }""")
    assert val == "xy"


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_select_multiple_morph_preserves_values(select_multiple_page):
    """Checked options survive an htmx form morph."""
    select_multiple_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select-multiple').open = true;
    """)
    select_multiple_page.wait_for_timeout(200)
    select_multiple_page.evaluate("""
        const dd = document.querySelector('details.dropdown.formwork-select-multiple');
        const cbs = dd.querySelectorAll('input[type="checkbox"]');
        cbs[0].checked = true;
        cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
        cbs[2].checked = true;
        cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
    """)
    select_multiple_page.wait_for_timeout(200)
    select_multiple_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select-multiple').open = false;
    """)
    select_multiple_page.wait_for_timeout(100)
    submit(select_multiple_page)
    checked = select_multiple_page.evaluate("""
        [...document.querySelectorAll('details.dropdown.formwork-select-multiple input[type="checkbox"]:checked')]
            .map(cb => cb.value)
    """)
    assert "py" in checked
    assert "go" in checked


@pytest.mark.e2e
def test_select_multiple_morph_preserves_dropdown_open(select_multiple_page):
    """An open dropdown stays open after a morph."""
    select_multiple_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select-multiple').open = true;
    """)
    select_multiple_page.wait_for_timeout(200)
    select_multiple_page.evaluate("""
        const form = document.querySelector('form[hx-post]');
        form.noValidate = true;
        form.requestSubmit();
    """)
    select_multiple_page.wait_for_timeout(500)
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    assert multi.get_attribute("open") is not None


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_select_multiple_screenshot_default(select_multiple_page, assert_screenshot):
    """Visual snapshot: SelectMultiple in default (closed) state."""
    wrapper = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    assert_screenshot(wrapper, "multi-select-default.png")


@pytest.mark.screenshot
def test_select_multiple_screenshot_open(select_multiple_page, assert_screenshot):
    """Visual snapshot: SelectMultiple with dropdown open."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    select_multiple_page.evaluate("""
        document.querySelector('details.dropdown.formwork-select-multiple').open = true;
    """)
    select_multiple_page.wait_for_timeout(100)
    assert_screenshot(multi, "multi-select-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_select_multiple_screenshot_selected(select_multiple_page, assert_screenshot):
    """Visual snapshot: SelectMultiple with at least 3 options selected."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").first
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(100)
    select_multiple_page.evaluate("""() => {
        const dd = document.querySelector('details.dropdown.formwork-select-multiple');
        ['py', 'js', 'go'].forEach(v => {
            const cb = dd.querySelector(`input[value="${v}"]`);
            if (cb) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            }
        });
    }""")
    select_multiple_page.wait_for_timeout(100)
    assert_screenshot(multi, "multi-select-selected.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_select_multiple_screenshot_grouped_open(select_multiple_page, assert_screenshot):
    """Visual snapshot: grouped SelectMultiple with dropdown open showing optgroup headers."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(150)
    assert_screenshot(multi, "multi-select-grouped-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_select_multiple_screenshot_keyboard_highlighted(select_multiple_page, assert_screenshot):
    """Visual snapshot: SelectMultiple with an option highlighted via keyboard."""
    multi = select_multiple_page.locator("details.dropdown.formwork-select-multiple").nth(3)
    multi.locator("summary").click()
    select_multiple_page.wait_for_timeout(150)
    search = multi.locator('.dropdown-content input[type="search"]')
    search.press("ArrowDown")  # Highlight first (ldn)
    select_multiple_page.wait_for_timeout(50)
    assert_screenshot(multi, "multi-select-keyboard-highlighted.png", capture_dropdown=True)
