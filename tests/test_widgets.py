from bs4 import BeautifulSoup
from django.utils.safestring import mark_safe

from django_formwork.widgets import (
    ComboBox,
    DataList,
    FileDropZone,
    ImageDropZone,
    MultiSelect,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
    Toggle,
    ValidatedTextarea,
)


def render_widget(widget, name="test", value=None, attrs=None):
    """Render a widget and return BeautifulSoup."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


class TestToggle:
    def test_has_toggle_class(self):
        widget = Toggle()
        assert "toggle" in widget.attrs.get("class", "")

    def test_renders_checkbox(self):
        soup = render_widget(Toggle())
        inp = soup.find("input")
        assert inp is not None
        assert inp["type"] == "checkbox"

    def test_toggle_class_in_output(self):
        soup = render_widget(Toggle())
        inp = soup.find("input")
        assert "toggle" in inp.get("class", [])

    def test_preserves_user_attrs(self):
        widget = Toggle(attrs={"class": "my-toggle"})
        cls = widget.attrs.get("class", "")
        assert "toggle" in cls
        assert "my-toggle" in cls


class TestRange:
    def test_renders_range_type(self):
        soup = render_widget(Range())
        inp = soup.find("input")
        assert inp is not None
        assert inp["type"] == "range"

    def test_min_max_attrs(self):
        widget = Range(attrs={"min": "0", "max": "100"})
        soup = render_widget(widget)
        inp = soup.find("input")
        assert inp["min"] == "0"
        assert inp["max"] == "100"


class TestRating:
    def test_renders_rating_wrapper(self):
        widget = Rating()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        rating_div = soup.find("div", class_="rating")
        assert rating_div is not None

    def test_renders_star_inputs(self):
        widget = Rating()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        radios = soup.find_all("input", {"type": "radio"})
        assert len(radios) == 3

    def test_star_class_on_inputs(self):
        widget = Rating()
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        radios = soup.find_all("input", {"type": "radio"})
        for radio in radios:
            assert "mask" in radio.get("class", [])
            assert "mask-star-2" in radio.get("class", [])

    def test_selected_value_checked(self):
        widget = Rating()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        radios = soup.find_all("input", {"type": "radio"})
        checked = [r for r in radios if r.has_attr("checked")]
        assert len(checked) == 1
        assert checked[0]["value"] == "2"

    def test_allow_clear(self):
        widget = Rating(allow_clear=True)
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        hidden = soup.find("input", class_="rating-hidden")
        assert hidden is not None

    def test_custom_star_class(self):
        widget = Rating(star_class="mask-heart")
        widget.choices = [("1", "1 star")]
        soup = render_widget(widget, value="1")
        radio = soup.find("input", {"type": "radio", "class": "mask"})
        assert "mask-heart" in radio.get("class", [])

    def test_choices_helper(self):
        choices = Rating.make_choices(5)
        assert len(choices) == 5
        assert choices[0] == ("1", "1 star")
        assert choices[4] == ("5", "5 stars")

    def test_mask_class_on_star_inputs(self):
        widget = Rating()
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        radios = soup.find_all("input", {"type": "radio"})
        for radio in radios:
            assert "mask" in radio.get("class", [])


class TestPasswordReveal:
    def test_renders_password_input(self):
        soup = render_widget(PasswordReveal())
        inp = soup.find("input")
        assert inp is not None

    def test_renders_toggle_button(self):
        soup = render_widget(PasswordReveal())
        btn = soup.find("button")
        assert btn is not None
        assert btn.get("x-on:click") == "show = !show"

    def test_alpine_x_data(self):
        soup = render_widget(PasswordReveal())
        label = soup.find("label")
        assert label.get("x-data") == "{ show: false }"

    def test_alpine_x_bind_type(self):
        soup = render_widget(PasswordReveal())
        inp = soup.find("input")
        assert inp.get("x-bind:type") == "show ? 'text' : 'password'"

    def test_wrapped_in_label(self):
        soup = render_widget(PasswordReveal())
        label = soup.find("label", class_="password-reveal")
        assert label is not None
        assert label.find("input") is not None

    def test_grow_class_on_input(self):
        soup = render_widget(PasswordReveal())
        inp = soup.find("input")
        assert "grow" in inp.get("class", [])

    def test_input_inside_label_wrapper(self):
        """Input is inside <label class="password-reveal">, not a direct child of fieldset."""
        soup = render_widget(PasswordReveal())
        label = soup.find("label", class_="password-reveal")
        assert label is not None
        inp = label.find("input")
        assert inp is not None

    def test_wrapper_has_id(self):
        soup = render_widget(PasswordReveal(), attrs={"id": "id_pw"})
        label = soup.find("label", class_="password-reveal")
        assert label["id"] == "id_pw_wrapper"

    def test_no_wrapper_id_without_id(self):
        soup = render_widget(PasswordReveal())
        label = soup.find("label", class_="password-reveal")
        assert not label.has_attr("id")


class TestMultiSelect:
    def test_renders_details_dropdown(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        details = soup.find("details", class_="dropdown")
        assert details is not None

    def test_renders_summary_trigger(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        summary = soup.find("summary")
        assert summary is not None
        # DaisyUI .select class is applied via CSS @apply, not in HTML
        assert "text-left" in summary.get("class", [])

    def test_dropdown_content(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        assert dropdown is not None

    def test_options_in_list_items(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        items = soup.find("div", class_="dropdown-content").find("ul").find_all("li")
        assert len(items) == 2

    def test_search_hidden_for_few_choices(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        search = soup.find("input", {"type": "text", "x-model": "search"})
        assert search is None

    def test_search_shown_for_many_choices(self):
        choices = [(str(i), f"Option {i}") for i in range(21)]
        widget = MultiSelect(choices=choices)
        soup = render_widget(widget, name="test")
        search = soup.find("input", {"type": "text", "x-model": "search"})
        assert search is not None

    def test_renders_hidden_checkboxes(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        soup = render_widget(widget, name="test")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 3
        for cb in checkboxes:
            assert "hidden" in cb.get("class", [])

    def test_checkbox_values(self):
        widget = MultiSelect(choices=[("py", "Python"), ("js", "JS")])
        soup = render_widget(widget, name="lang")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        values = [cb["value"] for cb in checkboxes]
        assert values == ["py", "js"]

    def test_checkbox_name(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="field")
        cb = soup.find("input", {"type": "checkbox"})
        assert cb["name"] == "field"

    def test_selected_values_checked(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        soup = render_widget(widget, name="test", value=["a", "c"])
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        checked = [cb["value"] for cb in checkboxes if cb.has_attr("checked")]
        assert checked == ["a", "c"]

    def test_checkmark_present(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        check = soup.find("span", class_="formwork-check")
        assert check is not None
        assert "opacity-0" in check.get("class", [])

    def test_checkmark_before_label_text(self):
        """Checkmark span comes before the text span, like a native select."""
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        label = soup.find("label")
        children = [c for c in label.children if getattr(c, "name", None)]
        names = [c.name for c in children]
        assert names == ["input", "span", "span"]

    def test_alpine_x_data(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", attrs={"x-data": True})
        assert wrapper is not None

    def test_labels_for_options(self):
        widget = MultiSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        spans = soup.find_all("span", class_="select-none")
        texts = [s.get_text(strip=True) for s in spans]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_no_results_element(self):
        choices = [(str(i), f"Option {i}") for i in range(21)]
        widget = MultiSelect(choices=choices)
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is not None
        assert no_results.get("x-show") == "noResults"

    def test_no_results_hidden_for_few_choices(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is None

    def test_aria_invalid_on_summary(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
        summary = soup.find("summary")
        assert summary["aria-invalid"] == "true"

    def test_no_aria_invalid_when_valid(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        summary = soup.find("summary")
        assert not summary.has_attr("aria-invalid")

    def test_multiselect_class_on_checkboxes(self):
        widget = MultiSelect(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        for cb in checkboxes:
            assert "multiselect" in cb.get("class", [])

    def test_search_url_in_context(self):
        widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
        ctx = widget.get_context("test", [], {"id": "id_test"})
        assert ctx["widget"]["search_url"] == "/search/"

    def test_search_url_none_by_default(self):
        widget = MultiSelect(choices=[("a", "A")])
        ctx = widget.get_context("test", [], {"id": "id_test"})
        assert ctx["widget"]["search_url"] is None

    def test_show_search_always_true_with_search_url(self):
        widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
        ctx = widget.get_context("test", [], {"id": "id_test"})
        assert ctx["widget"]["show_search"] is True

    def test_htmx_attrs_when_search_url(self):
        widget = MultiSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="lang", attrs={"id": "id_lang"})
        search_input = soup.find("input", {"type": "text"})
        assert search_input is not None
        assert search_input["hx-get"] == "/search/"
        assert "input changed delay:300ms" in search_input["hx-trigger"]
        assert search_input["hx-target"] == "#id_lang_options"
        assert search_input["hx-swap"] == "innerHTML"

    def test_no_htmx_attrs_without_search_url(self):
        choices = [(str(i), f"Option {i}") for i in range(21)]
        widget = MultiSelect(choices=choices)
        soup = render_widget(widget, name="test")
        search_input = soup.find("input", {"type": "text"})
        assert not search_input.has_attr("hx-get")

    def test_no_client_options_when_search_url(self):
        widget = MultiSelect(search_url="/search/", choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 0

    def test_htmx_mode_uses_alpine_map(self):
        widget = MultiSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        details = soup.find("details")
        x_data = details["x-data"]
        assert "selected: new Map(" in x_data
        assert "toggle(" in x_data

    def test_htmx_mode_hidden_inputs_template(self):
        widget = MultiSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        template = soup.find("template", {"x-for": True})
        assert template is not None
        hidden = template.find("input", {"type": "hidden"})
        assert hidden is not None
        assert hidden[":value"] == "val"
        assert hidden["name"] == "test"

    def test_initial_selected_json_in_context(self):
        widget = MultiSelect(search_url="/search/", choices=[("a", "Alpha"), ("b", "Beta")])
        ctx = widget.get_context("test", ["a"], {"id": "id_test"})
        import json

        initial = json.loads(ctx["widget"]["initial_selected_json"])
        assert initial == [["a", ["Alpha", ""]]]

    def test_initial_selected_json_empty(self):
        widget = MultiSelect(search_url="/search/", choices=[("a", "Alpha")])
        ctx = widget.get_context("test", [], {"id": "id_test"})
        import json

        initial = json.loads(ctx["widget"]["initial_selected_json"])
        assert initial == []

    def test_icons_in_options(self):
        widget = MultiSelect(
            choices=[("a", "Alpha"), ("b", "Beta")],
            icons={"a": mark_safe('<img src="a.svg">')},
        )
        soup = render_widget(widget, name="test")
        icon = soup.find("img", {"src": "a.svg"})
        assert icon is not None

    def test_no_icon_when_not_provided(self):
        widget = MultiSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        icons = soup.find_all("img")
        assert len(icons) == 0

    def test_icon_in_context(self):
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

    def test_wrapper_has_id(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        details = soup.find("details", class_="multiselect")
        assert details["id"] == "id_test_multiselect"

    def test_no_wrapper_id_without_id(self):
        widget = MultiSelect(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        details = soup.find("details", class_="multiselect")
        assert not details.has_attr("id")

    def test_htmx_wrapper_has_id(self):
        widget = MultiSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        details = soup.find("details", class_="multiselect")
        assert details["id"] == "id_test_multiselect"


class TestSearchSelect:
    def test_renders_details_dropdown(self):
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", class_="dropdown")
        assert wrapper is not None

    def test_search_select_class_on_wrapper(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", class_="search-select")
        assert wrapper is not None

    def test_renders_summary_trigger(self):
        """The trigger is a summary element styled as DaisyUI .select via CSS @apply."""
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        summary = soup.find("summary")
        assert summary is not None
        # DaisyUI .select class is applied via CSS @apply, not in HTML
        assert "text-left" in summary.get("class", [])

    def test_search_input_inside_dropdown(self):
        """Search input is inside the dropdown content when show_search is True."""
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")], show_search=True)
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        search = dropdown.find("input", {"type": "text"})
        assert search is not None

    def test_no_search_input_below_threshold(self):
        """Search wrapper has x-show=false when choice count is below threshold."""
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        details = soup.find("details")
        # showSearch Alpine var should be initialized to false
        assert "showSearch: false" in details.get("x-data", "")

    def test_renders_hidden_value_input(self):
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        hidden = soup.find("input", {"type": "hidden"})
        assert hidden is not None
        assert hidden["name"] == "test"

    def test_dropdown_content(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        assert dropdown is not None

    def test_options_as_buttons(self):
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 2

    def test_option_labels(self):
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        spans = soup.find_all("span", class_="select-none")
        texts = [s.get_text(strip=True) for s in spans]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_empty_option_excluded(self):
        """The empty option (value='') is excluded from the dropdown list."""
        widget = SearchSelect(choices=[("", "Select..."), ("a", "Alpha")])
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 1

    def test_alpine_x_data(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", attrs={"x-data": True})
        assert wrapper is not None

    def test_selected_label_shown_in_summary(self):
        """When a value is selected, its label is shown in the summary."""
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test", value="b")
        wrapper = soup.find("details", attrs={"x-data": True})
        x_data = wrapper["x-data"]
        assert "label: 'Beta'" in x_data

    def test_no_results_element(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is not None
        assert no_results.get("x-show") == "noResults"

    def test_listbox_role(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        listbox = soup.find("ul", {"role": "listbox"})
        assert listbox is not None

    def test_id_on_hidden_input(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_city"})
        hidden = soup.find("input", {"type": "hidden"})
        assert hidden["id"] == "id_city"

    def test_selected_label_context(self):
        """get_context returns the label for the selected value."""
        widget = SearchSelect(choices=[("a", "Alpha"), ("b", "Beta")])
        ctx = widget.get_context("test", "a", {})
        assert ctx["widget"]["selected_label"] == "Alpha"

    def test_selected_label_empty_when_no_value(self):
        widget = SearchSelect(choices=[("", ""), ("a", "Alpha")])
        ctx = widget.get_context("test", "", {})
        assert ctx["widget"]["selected_label"] == ""

    def test_aria_invalid_on_summary(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
        summary = soup.find("summary")
        assert summary["aria-invalid"] == "true"

    def test_no_aria_invalid_when_valid(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        summary = soup.find("summary")
        assert not summary.has_attr("aria-invalid")

    def test_search_url_in_context(self):
        widget = SearchSelect(search_url="/search/", choices=[("a", "Alpha")])
        ctx = widget.get_context("test", "", {"id": "id_test"})
        assert ctx["widget"]["search_url"] == "/search/"

    def test_search_url_none_by_default(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        ctx = widget.get_context("test", "", {"id": "id_test"})
        assert ctx["widget"]["search_url"] is None

    def test_htmx_attrs_when_search_url(self):
        widget = SearchSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="city", attrs={"id": "id_city"})
        dropdown = soup.find("div", class_="dropdown-content")
        search = dropdown.find("input", {"type": "text"})
        assert search["hx-get"] == "/search/"
        assert "input changed delay:300ms" in search["hx-trigger"]
        assert search["hx-target"] == "#id_city_listbox"
        assert search["hx-swap"] == "innerHTML"

    def test_no_htmx_attrs_without_search_url(self):
        widget = SearchSelect(choices=[("a", "Alpha")], show_search=True)
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        dropdown = soup.find("div", class_="dropdown-content")
        search = dropdown.find("input", {"type": "text"})
        assert not search.has_attr("hx-get")

    def test_no_client_options_when_search_url(self):
        widget = SearchSelect(search_url="/search/", choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 0

    def test_no_alpine_no_results_when_search_url(self):
        widget = SearchSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        no_results = soup.find("p", string="No results")
        assert no_results is None

    def test_event_delegation_data_attrs(self):
        """Buttons use data-value/data-label for event delegation."""
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        btn = soup.find("button", {"type": "button"})
        assert btn["data-value"] == "a"
        assert btn["data-label"] == "Alpha"

    def test_ul_has_click_handler(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        listbox = soup.find("ul", {"role": "listbox"})
        assert "@click" in str(listbox)

    def test_icons_in_options(self):
        widget = SearchSelect(
            choices=[("a", "Alpha"), ("b", "Beta")],
            icons={"a": mark_safe('<img src="a.svg">')},
        )
        soup = render_widget(widget, name="test")
        icon = soup.find("img", {"src": "a.svg"})
        assert icon is not None

    def test_no_icon_when_not_provided(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        icons = soup.find_all("img")
        assert len(icons) == 0

    def test_icon_in_context(self):
        widget = SearchSelect(
            choices=[("a", "Alpha"), ("b", "Beta")],
            icons={"a": mark_safe("<svg>icon</svg>")},
        )
        ctx = widget.get_context("test", "", {})
        for _group, options, _index in ctx["widget"]["optgroups"]:
            for option in options:
                if option["value"] == "a":
                    assert option["icon"] == "<svg>icon</svg>"
                else:
                    assert option["icon"] == ""

    def test_wrapper_has_id(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        details = soup.find("details", class_="search-select")
        assert details["id"] == "id_test_searchselect"

    def test_no_wrapper_id_without_id(self):
        widget = SearchSelect(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        details = soup.find("details", class_="search-select")
        assert not details.has_attr("id")

    def test_htmx_wrapper_has_id(self):
        widget = SearchSelect(search_url="/search/", choices=[])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        details = soup.find("details", class_="search-select")
        assert details["id"] == "id_test_searchselect"


class TestComboBox:
    """ComboBox: text input with autocomplete suggestions (free text)."""

    def test_renders_dropdown_wrapper(self):
        widget = ComboBox(suggestions=["Alpha", "Beta"])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", class_="dropdown")
        assert wrapper is not None

    def test_combobox_class_on_wrapper(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", class_="combobox")
        assert wrapper is not None

    def test_text_input_is_form_field(self):
        """The text input submits directly — no hidden input."""
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        text_input = soup.find("input", class_="combobox-input")
        assert text_input is not None
        assert text_input["name"] == "test"
        assert text_input["type"] == "text"
        # No hidden input
        hidden = soup.find("input", {"type": "hidden"})
        assert hidden is None

    def test_combobox_role(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["role"] == "combobox"
        assert trigger["aria-autocomplete"] == "list"

    def test_suggestions_as_buttons(self):
        widget = ComboBox(suggestions=["Alpha", "Beta", "Gamma"])
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 3

    def test_suggestion_labels(self):
        widget = ComboBox(suggestions=["Alpha", "Beta"])
        soup = render_widget(widget, name="test")
        spans = soup.find_all("span", class_="select-none")
        texts = [s.get_text(strip=True) for s in spans]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_preserves_value(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test", value="hello")
        text_input = soup.find("input", class_="combobox-input")
        assert text_input["value"] == "hello"

    def test_default_placeholder(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        text_input = soup.find("input", class_="combobox-input")
        assert "search" in text_input.get("placeholder", "").lower()

    def test_custom_placeholder(self):
        widget = ComboBox(suggestions=["Alpha"], attrs={"placeholder": "Type here"})
        soup = render_widget(widget, name="test")
        text_input = soup.find("input", class_="combobox-input")
        assert text_input["placeholder"] == "Type here"

    def test_alpine_x_data(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper is not None

    def test_no_results_element(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is not None

    def test_listbox_role(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        listbox = soup.find("ul", {"role": "listbox"})
        assert listbox is not None

    def test_empty_suggestions(self):
        widget = ComboBox()
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 0

    def test_aria_invalid(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["aria-invalid"] == "true"

    def test_multiple_mode_context(self):
        widget = ComboBox(suggestions=["A", "B"], multiple=True)
        ctx = widget.get_context("test", "", {})
        assert ctx["widget"]["multiple"] is True

    def test_single_mode_context(self):
        widget = ComboBox(suggestions=["A", "B"])
        ctx = widget.get_context("test", "", {})
        assert ctx["widget"]["multiple"] is False

    def test_search_url_in_context(self):
        widget = ComboBox(search_url="/search/")
        ctx = widget.get_context("test", "", {"id": "id_test"})
        assert ctx["widget"]["search_url"] == "/search/"

    def test_search_url_none_by_default(self):
        widget = ComboBox(suggestions=["A"])
        ctx = widget.get_context("test", "", {"id": "id_test"})
        assert ctx["widget"]["search_url"] is None

    def test_htmx_attrs_when_search_url(self):
        widget = ComboBox(search_url="/search/")
        soup = render_widget(widget, name="tags", attrs={"id": "id_tags"})
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["hx-get"] == "/search/"
        assert "input changed delay:300ms" in trigger["hx-trigger"]
        assert trigger["hx-target"] == "#id_tags_listbox"
        assert trigger["hx-swap"] == "innerHTML"

    def test_no_htmx_attrs_without_search_url(self):
        widget = ComboBox(suggestions=["A"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        trigger = soup.find("input", class_="combobox-input")
        assert not trigger.has_attr("hx-get")

    def test_no_client_suggestions_when_search_url(self):
        widget = ComboBox(suggestions=["Alpha"], search_url="/search/")
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 0

    def test_no_alpine_no_results_when_search_url(self):
        widget = ComboBox(search_url="/search/")
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        no_results = soup.find("p", string="No results")
        assert no_results is None

    def test_event_delegation_data_attrs(self):
        """Buttons use data-suggestion for event delegation."""
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        btn = soup.find("button", {"type": "button"})
        assert btn["data-suggestion"] == "Alpha"

    def test_icons_in_suggestions(self):
        widget = ComboBox(
            suggestions=["Python", "Go"],
            icons={"Python": mark_safe('<img src="py.svg">')},
        )
        soup = render_widget(widget, name="test")
        icon = soup.find("img", {"src": "py.svg"})
        assert icon is not None

    def test_no_icon_when_not_provided(self):
        widget = ComboBox(suggestions=["Alpha"])
        soup = render_widget(widget, name="test")
        icons = soup.find_all("img")
        assert len(icons) == 0

    def test_suggestions_context_as_dicts(self):
        widget = ComboBox(suggestions=["A", "B"], icons={"A": mark_safe("<svg/>")})
        ctx = widget.get_context("test", "", {})
        sugs = ctx["widget"]["suggestions"]
        assert sugs[0] == {"text": "A", "icon": mark_safe("<svg/>"), "description": ""}
        assert sugs[1] == {"text": "B", "icon": "", "description": ""}

    def test_wrapper_has_id(self):
        widget = ComboBox(suggestions=["A"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        wrapper = soup.find("div", class_="combobox")
        assert wrapper["id"] == "id_test_combobox"

    def test_no_wrapper_id_without_id(self):
        widget = ComboBox(suggestions=["A"])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", class_="combobox")
        assert not wrapper.has_attr("id")


class TestDataList:
    def test_renders_text_input(self):
        widget = DataList(datalist=["A", "B"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp is not None
        assert inp.get("type") == "text"

    def test_list_attribute_set(self):
        widget = DataList(datalist=["A"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["list"] == "id_test_list"

    def test_datalist_element_rendered(self):
        widget = DataList(datalist=["Chrome", "Firefox"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        datalist = soup.find("datalist")
        assert datalist is not None
        assert datalist["id"] == "id_test_list"

    def test_datalist_options(self):
        widget = DataList(datalist=["Chrome", "Firefox", "Safari"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        options = soup.find("datalist").find_all("option")
        assert len(options) == 3
        values = [o["value"] for o in options]
        assert values == ["Chrome", "Firefox", "Safari"]

    def test_empty_datalist(self):
        widget = DataList()
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        options = soup.find("datalist").find_all("option")
        assert len(options) == 0

    def test_no_datalist_without_id(self):
        """Without an id, no datalist or list attr is rendered."""
        widget = DataList(datalist=["A"])
        soup = render_widget(widget, name="test")
        datalist = soup.find("datalist")
        assert datalist is None

    def test_preserves_value(self):
        widget = DataList(datalist=["A", "B"])
        soup = render_widget(widget, name="test", value="hello", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["value"] == "hello"

    def test_preserves_placeholder(self):
        widget = DataList(datalist=["A"], attrs={"placeholder": "Pick one"})
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["placeholder"] == "Pick one"


class TestDropZone:
    def test_renders_dropzone_wrapper(self):
        soup = render_widget(FileDropZone())
        wrapper = soup.find("div", class_="dropzone")
        assert wrapper is not None

    def test_file_input(self):
        soup = render_widget(FileDropZone(), name="file")
        inp = soup.find("input", {"type": "file"})
        assert inp is not None
        assert inp["name"] == "file"

    def test_alpine_x_data(self):
        soup = render_widget(FileDropZone())
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper is not None
        assert "files:" in wrapper["x-data"]
        assert "dragging:" in wrapper["x-data"]

    def test_drag_event_handlers(self):
        soup = render_widget(FileDropZone())
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper.has_attr("@dragover.prevent")
        assert wrapper.has_attr("@dragleave.prevent")
        assert wrapper.has_attr("@drop.prevent")

    def test_drop_area(self):
        soup = render_widget(FileDropZone())
        zone = soup.find("div", class_="dropzone-area")
        assert zone is not None

    def test_click_to_browse(self):
        soup = render_widget(FileDropZone())
        zone = soup.find("div", class_="dropzone-area")
        assert "@click" in str(zone)

    def test_file_input_change_handler(self):
        soup = render_widget(FileDropZone())
        inp = soup.find("input", {"type": "file"})
        assert inp.has_attr("@change")

    def test_upload_icon(self):
        soup = render_widget(FileDropZone())
        svg = soup.find("svg")
        assert svg is not None

    def test_browse_text(self):
        soup = render_widget(FileDropZone())
        text = soup.get_text()
        assert "browse" in text.lower()

    def test_multiple_attr_passthrough(self):
        widget = FileDropZone(attrs={"multiple": True})
        soup = render_widget(widget, name="files")
        inp = soup.find("input", {"type": "file"})
        assert inp.has_attr("multiple")

    def test_id_on_input(self):
        soup = render_widget(FileDropZone(), name="file", attrs={"id": "id_file"})
        inp = soup.find("input", {"type": "file"})
        assert inp["id"] == "id_file"

    def test_wrapper_has_id(self):
        soup = render_widget(FileDropZone(), attrs={"id": "id_file"})
        wrapper = soup.find("div", class_="dropzone")
        assert wrapper["id"] == "id_file_dropzone"

    def test_no_wrapper_id_without_id(self):
        soup = render_widget(FileDropZone())
        wrapper = soup.find("div", class_="dropzone")
        assert not wrapper.has_attr("id")


class TestImageUpload:
    def test_renders_image_upload_wrapper(self):
        soup = render_widget(ImageDropZone())
        wrapper = soup.find("div", class_="image-upload")
        assert wrapper is not None

    def test_file_input(self):
        soup = render_widget(ImageDropZone(), name="avatar")
        inp = soup.find("input", {"type": "file"})
        assert inp is not None
        assert inp["name"] == "avatar"

    def test_accept_image(self):
        soup = render_widget(ImageDropZone(), name="avatar")
        inp = soup.find("input", {"type": "file"})
        assert inp["accept"] == "image/*"

    def test_alpine_x_data(self):
        soup = render_widget(ImageDropZone())
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper is not None
        assert "preview:" in wrapper["x-data"]
        assert "dragging:" in wrapper["x-data"]

    def test_drag_event_handlers(self):
        soup = render_widget(ImageDropZone())
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper.has_attr("@dragover.prevent")
        assert wrapper.has_attr("@dragleave.prevent")
        assert wrapper.has_attr("@drop.prevent")

    def test_image_preview_element(self):
        soup = render_widget(ImageDropZone())
        img = soup.find("img", {":src": "preview"})
        assert img is not None

    def test_remove_button(self):
        soup = render_widget(ImageDropZone())
        btn = soup.find("button", string="Remove")
        assert btn is not None
        assert btn["type"] == "button"

    def test_image_icon(self):
        soup = render_widget(ImageDropZone())
        svg = soup.find("svg")
        assert svg is not None

    def test_browse_text(self):
        soup = render_widget(ImageDropZone())
        text = soup.get_text()
        assert "browse" in text.lower()

    def test_id_on_input(self):
        soup = render_widget(ImageDropZone(), name="img", attrs={"id": "id_img"})
        inp = soup.find("input", {"type": "file"})
        assert inp["id"] == "id_img"

    def test_custom_accept_override(self):
        widget = ImageDropZone(attrs={"accept": ".png,.jpg"})
        soup = render_widget(widget, name="img")
        inp = soup.find("input", {"type": "file"})
        assert inp["accept"] == ".png,.jpg"

    def test_wrapper_has_id(self):
        soup = render_widget(ImageDropZone(), attrs={"id": "id_avatar"})
        wrapper = soup.find("div", class_="image-upload")
        assert wrapper["id"] == "id_avatar_upload"

    def test_no_wrapper_id_without_id(self):
        soup = render_widget(ImageDropZone())
        wrapper = soup.find("div", class_="image-upload")
        assert not wrapper.has_attr("id")


class TestValidatedTextarea:
    def test_renders_plain_textarea_without_validate_url(self):
        widget = ValidatedTextarea()
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea is not None
        assert textarea["name"] == "content"
        # No overlay structure
        assert soup.find("div", class_="validated-textarea") is None

    def test_renders_overlay_with_validate_url(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        wrapper = soup.find("div", class_="validated-textarea")
        assert wrapper is not None

    def test_highlights_div_present(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        highlights = soup.find("div", class_="validated-textarea-highlights")
        assert highlights is not None
        assert highlights["id"] == "id_content_highlights"
        assert highlights["aria-hidden"] == "true"

    def test_textarea_inside_overlay(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        wrapper = soup.find("div", class_="validated-textarea")
        textarea = wrapper.find("textarea")
        assert textarea is not None
        assert textarea["name"] == "content"
        assert textarea["id"] == "id_content"

    def test_errors_tooltip_present(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        tooltip = soup.find("div", class_="validated-textarea-tooltip")
        assert tooltip is not None
        assert tooltip["id"] == "id_content_vttooltip"
        errors = tooltip.find("div", class_="formwork-errors")
        assert errors is not None
        assert errors["id"] == "id_content_errors"
        assert errors["role"] == "alert"

    def test_htmx_attrs(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea["hx-post"] == "/validate/"
        assert "input changed delay:500ms" in textarea["hx-trigger"]
        assert textarea["hx-target"] == "#id_content_highlights"
        assert textarea["hx-swap"] == "innerHTML"

    def test_htmx_params_none(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea["hx-params"] == "none"

    def test_htmx_config_request(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        config = textarea["hx-on::config-request"]
        assert "event.detail.parameters.text = this.value" in config
        assert "event.detail.parameters.field_name = 'content'" in config
        assert "event.detail.parameters.errors_id = 'id_content_errors'" in config

    def test_alpine_x_data(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper is not None

    def test_scroll_sync(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea.has_attr("@scroll")

    def test_input_mirrors_text_to_highlights(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea.has_attr("@input")
        assert "backdrop" in textarea["@input"]

    def test_no_htmx_without_validate_url(self):
        widget = ValidatedTextarea()
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert not textarea.has_attr("hx-post")

    def test_preserves_value(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", value="hello world", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea.string == "hello world"

    def test_preserves_value_in_highlights(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", value="hello world", attrs={"id": "id_content"})
        highlights = soup.find("div", class_="validated-textarea-highlights")
        assert "hello world" in highlights.get_text()

    def test_preserves_attrs(self):
        widget = ValidatedTextarea(validate_url="/validate/", attrs={"rows": "5"})
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        textarea = soup.find("textarea")
        assert textarea["rows"] == "5"

    def test_validate_url_in_context(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        ctx = widget.get_context("content", "", {"id": "id_content"})
        assert ctx["widget"]["validate_url"] == "/validate/"

    def test_validate_url_none_by_default(self):
        widget = ValidatedTextarea()
        ctx = widget.get_context("content", "", {"id": "id_content"})
        assert ctx["widget"]["validate_url"] is None

    def test_wrapper_has_id(self):
        widget = ValidatedTextarea(validate_url="/validate/")
        soup = render_widget(widget, name="content", attrs={"id": "id_content"})
        wrapper = soup.find("div", class_="validated-textarea")
        assert wrapper["id"] == "id_content_vtextarea"
