"""ComboBox tests, including server-side search loading and failure UX (level 6b)."""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.http import QueryDict
from django.utils.safestring import mark_safe

from django_formwork import ChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.widgets import ComboBox, ComboBoxMultiple

from .conftest import open_combo_box, render_form, render_widget, server_widget, submit


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
    """ComboBoxMultiple is the comma-separated variant."""
    widget = ComboBoxMultiple(suggestions=["A"])
    assert widget.multiple is True


@pytest.mark.unit
def test_combo_box_get_context_suggestions_as_options():
    """Each suggestion becomes an option row; a pick fills the input with its label."""
    widget = ComboBox(suggestions=[ChoiceLabel("A", icon=mark_safe("<svg/>")), "B"])
    ctx = widget.get_context("test", "", {})
    a, b = ctx["widget"]["options"]
    assert (a["value"], a["label"], a["icon"], a["group"]) == ("A", "A", "<svg/>", "")
    assert (b["value"], b["label"], b["icon"], b["description"]) == ("B", "B", "", "")


@pytest.mark.unit
def test_combo_box_get_context_multiple_mode():
    """ComboBoxMultiple sets multiple in the widget context."""
    widget = ComboBoxMultiple(suggestions=["A", "B"])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is True


@pytest.mark.unit
def test_combo_box_get_context_single_mode():
    """get_context() defaults to multiple=False."""
    widget = ComboBox(suggestions=["A", "B"])
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["multiple"] is False


@pytest.mark.unit
def test_combo_box_get_context_search_url_set_by_search_key():
    """A registered search names its endpoint."""
    widget = server_widget(ComboBox)
    ctx = widget.get_context("test", "", {"id": "id_test"})
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
    """value_from_datadict returns None when nothing submitted."""
    widget = ComboBox(suggestions=["Alpha"])
    data = QueryDict("")
    val = widget.value_from_datadict(data, {}, "test")
    assert val is None


@pytest.mark.unit
def test_combo_box_empty_suggestions_get_context():
    """ComboBox with no suggestions has no option rows."""
    widget = ComboBox()
    ctx = widget.get_context("test", "", {})
    assert ctx["widget"]["options"] == []


@pytest.mark.unit
def test_combo_box_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = ComboBox(suggestions=["a"])
    ctx = widget.get_context("field", None, {"id": "id_field"})
    assert ctx["widget"]["name"] == "field"


# ─── Level 1b: Grouped suggestions (Python API) ──────────────────────────


@pytest.mark.unit
def test_combo_box_flat_suggestions_have_no_group():
    """A flat list of strings yields rows without a group heading."""
    widget = ComboBox(suggestions=["A", "B"])
    options = widget.get_context("test", "", {})["widget"]["options"]
    assert [(o["group"], o["label"]) for o in options] == [("", "A"), ("", "B")]


@pytest.mark.unit
def test_combo_box_rejects_value_label_pairs():
    """A Django-style ``(value, label)`` pair fails at once instead of turning into a group of letters."""
    with pytest.raises(ImproperlyConfigured, match="not \\(value, label\\) pairs"):
        ComboBox(suggestions=[("py", "Python")])


@pytest.mark.unit
def test_combo_box_grouped_suggestions_keep_their_group():
    """Grouped suggestions ``[(name, [items])]`` keep their order and group name."""
    widget = ComboBox(suggestions=[("Italian", ["Pizza", "Pasta"]), ("Asian", ["Sushi"])])
    options = widget.get_context("test", "", {})["widget"]["options"]
    assert [(o["group"], o["label"]) for o in options] == [
        ("Italian", "Pizza"),
        ("Italian", "Pasta"),
        ("Asian", "Sushi"),
    ]


@pytest.mark.unit
def test_combo_box_grouped_choice_labels_keep_icons_and_descriptions():
    """A ChoiceLabel inside a group carries its icon and description to the row."""
    widget = ComboBox(
        suggestions=[
            ("G1", [ChoiceLabel("A", icon=mark_safe("<svg/>"), description="alpha")]),
            ("G2", [ChoiceLabel("B", icon=mark_safe("<svg2/>"), description="beta")]),
        ],
    )
    a, b = widget.get_context("test", "", {})["widget"]["options"]
    assert (a["icon"], a["description"]) == ("<svg/>", "alpha")
    assert (b["icon"], b["description"]) == ("<svg2/>", "beta")


@pytest.mark.unit
def test_combo_box_get_context_grouped_icons_json_includes_all_groups():
    """``icons_json`` contains icons for items spread across multiple groups."""
    import json as _json

    widget = ComboBox(
        suggestions=[("G1", [ChoiceLabel("A", icon="🍕")]), ("G2", [ChoiceLabel("B", icon="🍣")])],
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
    div = soup.find("div", class_="formwork-combobox")
    assert div is not None


@pytest.mark.unit
def test_combo_box_input_points_at_the_highlighted_option():
    """The input keeps focus during arrow keys, so it names the highlighted row through aria-activedescendant."""
    soup = render_widget(ComboBox(suggestions=["Go", "Zig"]), name="language", attrs={"id": "id_language"})
    inp = soup.select_one("input[role=combobox]")
    assert inp["aria-controls"] == "id_language_listbox"
    assert inp[":aria-activedescendant"] == "activeOption"


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
    """render() produces a div with class 'formwork-combobox'."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="formwork-combobox")
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
    alert = soup.find("div", attrs={"x-show": "noResults"}).find("div", attrs={"role": "status"})
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
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
    trigger = soup.find("input", class_="combobox-input")
    assert trigger["hx-get"].startswith("/__formwork__/search/")
    assert trigger["hx-trigger"] == "input changed delay:300ms, focus"
    assert trigger["hx-target"] == "next ul"
    assert trigger["hx-swap"] == "innerHTML"


@pytest.mark.unit
def test_combo_box_no_htmx_attrs_without_search_url():
    """Without search_url, no htmx attributes are added."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    trigger = soup.find("input", class_="combobox-input")
    assert not trigger.has_attr("hx-get")


@pytest.mark.unit
def test_combo_box_server_mode_starts_empty():
    """The endpoint fills the list on first focus, so the render holds no rows."""
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    assert listbox.find_all("li") == []


@pytest.mark.unit
def test_combo_box_no_alpine_no_results_when_search_url():
    """When search_url is set, 'No results' element is not rendered."""
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    no_results = soup.find("p", string="No results")
    assert no_results is None


@pytest.mark.unit
def test_combo_box_client_mode_renders_every_suggestion():
    """Without server search the browser filters, so every suggestion is a row."""
    widget = ComboBox(suggestions=["Alpha", "Beta"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", attrs={"id": "id_test_listbox"})
    assert [li["data-label"] for li in listbox.find_all("li", attrs={"role": "option"})] == ["Alpha", "Beta"]


@pytest.mark.unit
def test_combo_box_renders_error_alert_when_search_url():
    """The error alert is rendered as a plain DaisyUI alert, hidden by
    default via x-show='hasError'."""
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert is not None
    assert alert.get("x-show") == "hasError"
    assert "alert" in alert["class"]
    assert "alert-error" in alert["class"]
    assert "Search failed" in alert.get_text()


@pytest.mark.unit
def test_combo_box_error_alert_hidden_until_a_search_fails():
    """The error alert waits on ``hasError``, which only a failed search sets."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    alert = soup.find("div", attrs={"role": "alert"})
    assert alert["x-show"] == "hasError"
    assert alert.has_attr("x-cloak")


@pytest.mark.unit
def test_combo_box_root_wires_error_handlers():
    """The root hears both the search and "Load more"; only the input sets the query.

    ``hasError`` follows the response only; resetting it on request would flash the old list.
    """
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
    root = soup.find("div", id="id_tags_wrapper")
    assert "@htmx:before:request" not in root.attrs
    assert root["@htmx:before:swap"] == "onSearchBeforeSwap($event)"
    assert root["@htmx:response:error"] == "onSearchError()"
    assert root["@htmx:error"] == "onSearchError()"
    trigger = root.find("input", class_="combobox-input")
    assert trigger["@htmx:config:request"] == "onSearchConfig($event)"
    assert "@htmx:before:swap" not in trigger.attrs


@pytest.mark.unit
def test_combo_box_listbox_hidden_only_on_error():
    """The listbox stays visible at all times except when an error occurs."""
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    listbox = soup.find("ul", id="id_test_listbox")
    assert listbox.get("x-show") == "!hasError"


@pytest.mark.unit
def test_combo_box_binds_alpine_component_when_search_url():
    """The wrapper binds to the formworkComboBox component regardless of search_url;
    hasError state lives in the component, not the markup."""
    widget = server_widget(ComboBox)
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    wrapper = soup.find("div", class_="formwork-combobox")
    assert wrapper["x-data"] == "formworkComboBox"


@pytest.mark.unit
def test_combo_box_icon_rendering():
    """Icons are rendered inline in suggestion buttons."""
    widget = ComboBox(suggestions=[ChoiceLabel("Python", icon=mark_safe('<img src="py.svg">')), "Go"])
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "py.svg"})
    assert icon is not None


@pytest.mark.unit
def test_combo_box_no_icon_when_not_provided():
    """No icon elements appear for plain suggestions."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0


@pytest.mark.unit
def test_combo_box_event_delegation_data_attrs():
    """Suggestion buttons carry data-value and data-label for event delegation."""
    widget = ComboBox(suggestions=["Alpha"])
    soup = render_widget(widget, name="test")
    btn = soup.find("button", {"type": "button"})
    assert btn["data-value"] == "Alpha"
    assert btn["data-label"] == "Alpha"


@pytest.mark.unit
def test_combo_box_wrapper_has_id():
    """Combobox wrapper div gets an id derived from the field id."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test", attrs={"id": "id_test"})
    wrapper = soup.find("div", class_="formwork-combobox")
    assert wrapper["id"] == "id_test_wrapper"


@pytest.mark.unit
def test_combo_box_no_wrapper_id_without_id():
    """Combobox wrapper div has no id when no field id is provided."""
    widget = ComboBox(suggestions=["A"])
    soup = render_widget(widget, name="test")
    wrapper = soup.find("div", class_="formwork-combobox")
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
        suggestions=[
            ("G1", [ChoiceLabel("Pizza", icon=mark_safe("<svg>p</svg>"))]),
            ("G2", [ChoiceLabel("Sushi", icon=mark_safe("<svg>s</svg>"))]),
        ],
    )
    soup = render_widget(widget, name="food")
    buttons = soup.find_all("button", {"data-label": True})
    assert {b["data-label"] for b in buttons} == {"Pizza", "Sushi"}
    assert {b.get("data-icon", "") for b in buttons} == {"<svg>p</svg>", "<svg>s</svg>"}


@pytest.mark.unit
def test_combo_box_group_header_precedes_its_rows():
    """A group heading is filtered by the rows after it, so its labels stay in the DOM."""
    widget = ComboBox(suggestions=[("Italian", ["Pizza", "Pasta"])])
    soup = render_widget(widget, name="food")
    header = soup.find("li", class_="menu-title")
    assert header["x-show"] == "matches($el)"
    assert header.has_attr("data-group")
    assert [li["data-label"] for li in header.find_next_siblings("li")] == ["Pizza", "Pasta"]


@pytest.mark.unit
def test_combo_box_grouped_renders_all_suggestion_buttons():
    """All items across all groups render as suggestion buttons."""
    widget = ComboBox(
        suggestions=[("G1", ["A", "B"]), ("G2", ["C"])],
    )
    soup = render_widget(widget, name="test")
    buttons = soup.find_all("button", {"data-label": True})
    assert {b["data-label"] for b in buttons} == {"A", "B", "C"}


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
    """Keydown handlers call the component's nav and enter methods."""
    widget = ComboBox(suggestions=["A"])
    html = widget.render("test", "")
    assert "onNav($event, 1)" in html
    assert "onNav($event, -1)" in html
    assert "onEnter($event)" in html


@pytest.mark.unit
def test_combo_box_xdata_binds_alpine_component():
    """Wrapper binds to the formworkComboBox component (state including
    the highlight is defined in the JS module)."""
    widget = ComboBox(suggestions=["A"])
    html = widget.render("test", "")
    assert 'x-data="formworkComboBox"' in html


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_combo_box_renders_via_form(renderer):
    """Field renders as a text input named after the form field."""
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
    tooltip = soup.find(id="id_tag_error", class_="tooltip-content")
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


# ─── Level 4: Escaping regressions ──────────────────────────────────────


@pytest.mark.integration
def test_combo_box_data_label_round_trips_raw(renderer):
    """Regression: escapejs on the suggestion displayed O'Brien & Sons as O\\u0027Brien \\u0026 Sons."""

    class SupplierForm(FormworkForm):
        supplier = forms.CharField(widget=ComboBox(suggestions=["O'Brien & Sons"]), required=False)

    soup = render_form(SupplierForm(), renderer=renderer)
    btn = soup.find("button", attrs={"data-label": True})
    assert btn["data-label"] == "O'Brien & Sons"
    assert btn["data-value"] == "O'Brien & Sons"


@pytest.mark.integration
def test_combo_box_data_icon_escapes_safe_markup(renderer):
    """A mark_safe icon stays escaped inside the data-icon attribute."""
    icon = '<img src="py.svg">'

    class IconComboBoxForm(FormworkForm):
        lang = forms.CharField(
            widget=ComboBox(suggestions=[ChoiceLabel("Python", icon=mark_safe(icon))]),  # noqa: S308
            required=False,
        )

    soup = render_form(IconComboBoxForm(), renderer=renderer)
    btn = soup.find("button", attrs={"data-label": "Python"})
    assert btn["data-icon"] == icon


@pytest.mark.integration
def test_combo_box_multiple_has_no_inline_init(renderer):
    """Regression: an inline x-init re-ran on every swap and stacked formdata listeners on the form."""

    class TagsForm(FormworkForm):
        tags = forms.CharField(widget=ComboBoxMultiple(suggestions=["a"]), required=False)

    soup = render_form(TagsForm(), renderer=renderer)
    assert soup.find("div", class_="formwork-combobox")["data-multiple"] == "true"
    assert soup.find(attrs={"x-init": True}) is None


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_combo_box_renders_on_page(combobox_page):
    """ComboBox is visible on the /combobox/ page."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").first
    assert combo.is_visible()


@pytest.mark.e2e
def test_combo_box_typing_shows_filtered_suggestions(combobox_page):
    """Typing in the input filters suggestions to matching entries."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.formwork-combobox").first
    assert combo.locator("button", has_text="Python").is_visible()
    assert not combo.locator("button", has_text="Go").is_visible()


@pytest.mark.e2e
def test_combo_box_pick_suggestion(combobox_page):
    """Clicking a suggestion populates the input with that value."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Ru")
    combobox_page.wait_for_timeout(150)
    combo = combobox_page.locator(".dropdown.formwork-combobox").first
    combo.locator("button", has_text="Rust").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Rust"


@pytest.mark.e2e
def test_combo_box_single_pick_dispatches_change_event(combobox_page):
    """Picking a suggestion in single mode fires a bubbling change event and keeps the dropdown closed."""
    # change, not input: the input handler reopens the dropdown (dirty tracking listens to both).
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Ru")
    combobox_page.wait_for_timeout(150)
    combobox_page.evaluate("""() => {
        window._comboChangeEvents = 0;
        document.querySelector('input[name="language_single"]').closest('form')
            .addEventListener('change', (e) => {
                if (e.target.name === 'language_single') window._comboChangeEvents++;
            });
    }""")
    combo = combobox_page.locator(".dropdown.formwork-combobox").first
    combo.locator("button", has_text="Rust").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Rust"
    assert combobox_page.evaluate("() => window._comboChangeEvents") >= 1
    assert (
        combobox_page.evaluate(
            "() => Alpine.$data(document.querySelector('.dropdown.formwork-combobox')).open",
        )
        is False
    )


@pytest.mark.e2e
@pytest.mark.parametrize("name", ["language_single", "language_htmx"])
def test_combo_box_pick_does_not_reopen_the_panel(combobox_page, name):
    """The panel stays closed past the search delay, and typing opens it again.

    A pick fires change, which neither the input handler nor the search trigger hears.
    """
    from playwright.sync_api import expect

    combo = combobox_page.locator(f"#id_{name}_wrapper")
    panel = combo.locator("[x-ref=panel]")
    inp = combobox_page.locator(f'input[name="{name}"]')
    inp.click()
    inp.fill("Ru")
    rust = combo.locator("button[data-value]", has_text="Rust")
    expect(rust).to_be_visible(timeout=10000)
    rust.click()
    expect(inp).to_have_value("Rust")
    combobox_page.wait_for_timeout(500)
    expect(panel).to_be_hidden()
    assert not panel.evaluate("el => el.matches(':popover-open')")
    assert combo.evaluate("el => Alpine.$data(el).open") is False
    inp.fill("Py")
    expect(panel).to_be_visible()


@pytest.mark.e2e
def test_combo_box_free_text_allowed(combobox_page):
    """Arbitrary text can be typed (ComboBox is free text, not constrained)."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combo_box_multiple_pick_adds_value(combobox_page):
    """In multiple mode, clicking a suggestion appends it."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(1)
    inp = combobox_page.locator('input[name="toppings_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button", has_text="Pizza").click()
    combobox_page.wait_for_timeout(100)
    assert "Pizza" in inp.input_value()


@pytest.mark.e2e
def test_combo_box_multiple_pick_second_appends(combobox_page):
    """In multiple mode, a second pick appends to the comma-separated list."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(1)
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
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(1)
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
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    headers = [h.inner_text().strip() for h in combo.locator("li.menu-title").all() if h.is_visible()]
    assert headers == ["Italian", "Japanese", "Mexican"]


@pytest.mark.e2e
def test_combo_box_grouped_filter_hides_empty_groups(combobox_page):
    """Typing 'pi' (matches only 'Pizza') hides Japanese and Mexican headers."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    inp.fill("pi")
    combobox_page.wait_for_timeout(150)
    visible_headers = [h.inner_text().strip() for h in combo.locator("li.menu-title").all() if h.is_visible()]
    assert visible_headers == ["Italian"]


@pytest.mark.e2e
def test_combo_box_grouped_pick_from_group(combobox_page):
    """Picking a suggestion inside a group sets the input value."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(7)
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    combo.locator("button[data-label='Sushi']").click()
    combobox_page.wait_for_timeout(100)
    assert inp.input_value() == "Sushi"


# ─── Level 5c: E2e, keyboard navigation ──────────────────────────────────
#
# Keyboard handlers live on the wrapper ``<div class='dropdown combobox'>``,
# so the input must be focused (dropdown open) for events to bubble up.


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_highlights_first(combobox_page):
    """ArrowDown highlights the first visible suggestion."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(100)
    highlighted = combobox_page.locator(".dropdown.formwork-combobox").first.locator("li.highlighted > [data-value]")
    assert highlighted.count() == 1
    assert highlighted.first.get_attribute("data-label") == "Python"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_navigates(combobox_page):
    """Each ArrowDown moves to the next suggestion."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.formwork-combobox").first.locator("li.highlighted > [data-value]")
    assert highlighted.first.get_attribute("data-label") == "JavaScript"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowdown_wraps_to_first(combobox_page):
    """ArrowDown past the last suggestion wraps back to the first."""
    inp = open_combo_box(combobox_page, "language_single")
    # 6 options: Python, JavaScript, Go, Rust, TypeScript, Ruby
    for _ in range(7):
        inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.formwork-combobox").first.locator("li.highlighted > [data-value]")
    assert highlighted.first.get_attribute("data-label") == "Python"


@pytest.mark.e2e
def test_combo_box_keyboard_arrowup_wraps_to_last(combobox_page):
    """ArrowUp from no highlight goes to the last visible suggestion."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("ArrowUp")
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.formwork-combobox").first.locator("li.highlighted > [data-value]")
    assert highlighted.first.get_attribute("data-label") == "Ruby"


@pytest.mark.e2e
def test_combo_box_keyboard_filter_skips_hidden_options(combobox_page):
    """After filtering, ArrowDown only highlights visible (matching) options."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.fill("Ru")  # Matches Rust + Ruby
    combobox_page.wait_for_timeout(150)
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    inp.press("ArrowDown")  # Should wrap back to Rust
    combobox_page.wait_for_timeout(50)
    highlighted = combobox_page.locator(".dropdown.formwork-combobox").first.locator("li.highlighted > [data-value]")
    val = highlighted.first.get_attribute("data-label")
    assert val == "Rust"


@pytest.mark.e2e
def test_combo_box_single_keyboard_enter_picks_and_closes(combobox_page):
    """Single-mode: Enter on highlighted option sets value and closes dropdown."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    inp.press("ArrowDown")  # JavaScript
    combobox_page.wait_for_timeout(50)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    assert inp.input_value() == "JavaScript"
    # Dropdown should be closed (open=false)
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.formwork-combobox')[0]).open",
    )
    assert is_open is False


@pytest.mark.e2e
def test_combo_box_single_keyboard_enter_no_highlight_picks_first(combobox_page):
    """With no highlight, Enter picks the first visible suggestion."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.fill("Go")
    combobox_page.wait_for_timeout(150)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    assert inp.input_value() == "Go"


@pytest.mark.e2e
def test_combo_box_multiple_keyboard_enter_toggles_keeps_open(combobox_page):
    """Multi-mode: Enter on highlighted toggles into the comma list, dropdown stays open."""
    inp = open_combo_box(combobox_page, "toppings_multi")
    inp.press("ArrowDown")  # Pizza
    combobox_page.wait_for_timeout(50)
    inp.press("Enter")
    combobox_page.wait_for_timeout(150)
    val = inp.input_value()
    assert "Pizza" in val
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.formwork-combobox')[1]).open",
    )
    assert is_open is True


@pytest.mark.e2e
def test_combo_box_multiple_keyboard_enter_toggles_off(combobox_page):
    """Multi-mode: pressing Enter again on the same value removes it."""
    inp = open_combo_box(combobox_page, "toppings_multi")
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
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("ArrowDown")
    combobox_page.wait_for_timeout(50)
    combo = combobox_page.locator(".dropdown.formwork-combobox").first
    assert combo.locator("li.highlighted > [data-value]").count() == 1
    inp.press("Escape")
    combobox_page.wait_for_timeout(150)
    assert combo.locator("li.highlighted > [data-value]").count() == 0


@pytest.mark.e2e
def test_combo_box_keyboard_escape_closes_dropdown(combobox_page):
    """Escape closes the dropdown (open=false)."""
    inp = open_combo_box(combobox_page, "language_single")
    inp.press("Escape")
    combobox_page.wait_for_timeout(150)
    is_open = combobox_page.evaluate(
        "() => Alpine.$data(document.querySelectorAll('.dropdown.formwork-combobox')[0]).open",
    )
    assert is_open is False


@pytest.mark.e2e
def test_combo_box_escape_in_a_dialog_closes_the_list_first(combobox_page):
    """The first Escape closes the list; the next one reaches the modal dialog around it."""
    from playwright.sync_api import expect

    combobox_page.evaluate("""() => {
        const dialog = document.createElement("dialog");
        dialog.id = "e2e_dialog";
        document.body.append(dialog);
        dialog.append(document.getElementById("id_language_single_field"));
        dialog.showModal();
    }""")
    inp = combobox_page.locator("#id_language_single")
    inp.click()
    listbox = combobox_page.locator("#id_language_single_listbox")
    expect(listbox).to_be_visible()
    inp.press("Escape")
    expect(listbox).to_be_hidden()
    expect(combobox_page.locator("#e2e_dialog[open]")).to_have_count(1)
    inp.press("Escape")
    expect(combobox_page.locator("#e2e_dialog[open]")).to_have_count(0)


@pytest.mark.e2e
def test_combo_box_focus_leaving_the_widget_closes_the_list(combobox_page):
    """Tabbing to another control closes the list."""
    from playwright.sync_api import expect

    combobox_page.locator("#id_language_single").click()
    listbox = combobox_page.locator("#id_language_single_listbox")
    expect(listbox).to_be_visible()
    combobox_page.locator("#id_toppings_multi").focus()
    expect(listbox).to_be_hidden()


@pytest.mark.e2e
def test_combo_box_icon_overlay_covers_the_input_while_unfocused(combobox_page):
    """With focus elsewhere the overlay lists the picks with their icons; focus brings the text back."""
    import re

    from playwright.sync_api import expect

    inp = combobox_page.locator("#id_language_icons_multi")
    overlay = combobox_page.locator("#id_language_icons_multi_wrapper .combobox-display")
    listbox = combobox_page.locator("#id_language_icons_multi_listbox")
    inp.click()
    listbox.locator("button[data-value='Python']").click()
    listbox.locator("button[data-value='Go']").click()
    combobox_page.locator("#id_language_single").focus()
    expect(overlay).to_be_visible()
    expect(overlay.locator(":scope > span:nth-of-type(1) > span:first-child")).to_be_hidden()
    expect(overlay.locator(":scope > span:nth-of-type(2) > span:first-child")).to_be_visible()
    expect(inp).to_have_class(re.compile(r"\btext-transparent\b"))
    inp.focus()
    expect(overlay).to_be_hidden()
    expect(inp).not_to_have_class(re.compile(r"\btext-transparent\b"))


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Needs a page with a required ComboBox; /combobox/ has none.


@pytest.mark.e2e
def test_combo_box_server_search_fills_the_list_on_first_focus(combobox_page):
    """The page renders no rows; the first focus fetches one page of the 25 languages."""
    from playwright.sync_api import expect

    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(4)
    rows = combo.locator("ul button[data-value]")
    expect(rows).to_have_count(0)
    combobox_page.locator('input[name="language_htmx"]').click()
    expect(rows).to_have_count(20, timeout=10000)


@pytest.mark.e2e
def test_combo_box_search_query_leaves_out_the_field_name(combobox_page):
    """The typed text goes out as ``q`` only, so a field named like a search param can't override it."""
    from urllib.parse import parse_qs, urlsplit

    inp = combobox_page.locator('input[name="language_htmx"]')
    inp.click()
    with combobox_page.expect_request(lambda request: "q=Ge" in request.url) as request_info:
        inp.press_sequentially("Ge")
    query = parse_qs(urlsplit(request_info.value.url).query)
    assert query["q"] == ["Ge"]
    assert "language_htmx" not in query


@pytest.mark.e2e
def test_combo_box_newest_query_runs_after_a_pending_search(combobox_page):
    """Queries typed while a search is pending end with the newest one, not the first one queued."""
    from urllib.parse import parse_qs, urlsplit

    from playwright.sync_api import expect

    inp = combobox_page.locator('input[name="language_htmx"]')
    rows = combobox_page.locator("#id_language_htmx_listbox button[data-value]")
    inp.click()
    expect(rows).to_have_count(20)
    combobox_page.evaluate(
        """() => {
          window.__fwQueries = [];
          document.addEventListener("htmx:config:request", (e) => window.__fwQueries.push(e.detail.ctx.request.body.get("q")));
        }"""
    )
    held = []

    def hold(route):
        held.append(route)

    combobox_page.route(lambda url: parse_qs(urlsplit(url).query).get("q") == ["G"], hold)
    with combobox_page.expect_request(lambda request: "q=G" in request.url):
        inp.press_sequentially("G")
    inp.press_sequentially("o")
    combobox_page.wait_for_function("q => window.__fwQueries.includes(q)", arg="Go")
    inp.fill("Z")
    combobox_page.wait_for_function("q => window.__fwQueries.includes(q)", arg="Z")
    held[0].continue_()
    expect(rows).to_have_text(["Zig"])


@pytest.mark.e2e
def test_combo_box_failing_search_shows_error_alert(combobox_page):
    """When the search endpoint returns 500, the error alert replaces the listbox."""
    from playwright.sync_api import expect

    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(8)
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

    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(8)
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
    inp = combobox_page.locator('input[name="language_single"]')
    inp.fill("Haskell")
    submit(combobox_page)
    assert inp.input_value() == "Haskell"


@pytest.mark.e2e
def test_combo_box_morph_preserves_multiple_selected(combobox_page):
    """Comma-separated multiple selections survive an htmx form morph."""
    combo = combobox_page.locator(".dropdown.formwork-combobox").nth(1)
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


@pytest.mark.screenshot
def test_combo_box_screenshot_default(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox in default (empty) state."""
    wrapper = combobox_page.locator(".dropdown.formwork-combobox").first
    assert_screenshot(wrapper, "combobox-default.png")


@pytest.mark.screenshot
def test_combo_box_screenshot_open_dropdown(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox with dropdown open."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("P")
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator(".dropdown.formwork-combobox").first
    assert_screenshot(wrapper, "combobox-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_grouped_open(combobox_page, assert_screenshot):
    """Visual snapshot: grouped ComboBox with dropdown open showing optgroup headers."""
    inp = combobox_page.locator('input[name="food_grouped"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator("#id_food_grouped_wrapper")
    assert_screenshot(wrapper, "combobox-grouped-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_multiple_selected_open(combobox_page, assert_screenshot):
    """Visual snapshot: multiple-mode ComboBox open with a checked suggestion."""
    inp = combobox_page.locator('input[name="language_icons_multi"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    wrapper = combobox_page.locator("#id_language_icons_multi_wrapper")
    wrapper.locator("button", has_text="Python").click()
    combobox_page.wait_for_timeout(100)
    assert_screenshot(wrapper, "combobox-multiple-selected-open.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_keyboard_highlighted(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox with a suggestion highlighted via keyboard."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    combobox_page.wait_for_timeout(150)
    inp.press("ArrowDown")  # Highlight first option
    inp.press("ArrowDown")  # JavaScript
    combobox_page.wait_for_timeout(50)
    wrapper = combobox_page.locator(".dropdown.formwork-combobox").first
    assert_screenshot(wrapper, "combobox-keyboard-highlighted.png", capture_dropdown=True)


@pytest.mark.screenshot
def test_combo_box_screenshot_suggestion_selected(combobox_page, assert_screenshot):
    """Visual snapshot: ComboBox after a suggestion has been selected."""
    inp = combobox_page.locator('input[name="language_single"]')
    inp.click()
    inp.fill("Py")
    combobox_page.wait_for_timeout(150)
    combobox_page.locator(".dropdown.formwork-combobox").first.locator("button", has_text="Python").click()
    combobox_page.wait_for_timeout(100)
    wrapper = combobox_page.locator(".dropdown.formwork-combobox").first
    assert_screenshot(wrapper, "combobox-selected.png")
