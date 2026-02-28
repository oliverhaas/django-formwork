from bs4 import BeautifulSoup

from django_formwork.widgets import (
    ComboBoxInput,
    DataListInput,
    MultiSelectInput,
    PasswordRevealInput,
    RangeInput,
    RatingInput,
    ToggleInput,
)


def render_widget(widget, name="test", value=None, attrs=None):
    """Render a widget and return BeautifulSoup."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


class TestToggleInput:
    def test_has_toggle_class(self):
        widget = ToggleInput()
        assert "toggle" in widget.attrs.get("class", "")

    def test_renders_checkbox(self):
        soup = render_widget(ToggleInput())
        inp = soup.find("input")
        assert inp is not None
        assert inp["type"] == "checkbox"

    def test_toggle_class_in_output(self):
        soup = render_widget(ToggleInput())
        inp = soup.find("input")
        assert "toggle" in inp.get("class", [])

    def test_preserves_user_attrs(self):
        widget = ToggleInput(attrs={"class": "my-toggle"})
        cls = widget.attrs.get("class", "")
        assert "toggle" in cls
        assert "my-toggle" in cls


class TestRangeInput:
    def test_renders_range_type(self):
        soup = render_widget(RangeInput())
        inp = soup.find("input")
        assert inp is not None
        assert inp["type"] == "range"

    def test_min_max_attrs(self):
        widget = RangeInput(attrs={"min": "0", "max": "100"})
        soup = render_widget(widget)
        inp = soup.find("input")
        assert inp["min"] == "0"
        assert inp["max"] == "100"


class TestRatingInput:
    def test_renders_rating_wrapper(self):
        widget = RatingInput()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        rating_div = soup.find("div", class_="rating")
        assert rating_div is not None

    def test_renders_star_inputs(self):
        widget = RatingInput()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        radios = soup.find_all("input", {"type": "radio"})
        assert len(radios) == 3

    def test_star_class_on_inputs(self):
        widget = RatingInput()
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        radios = soup.find_all("input", {"type": "radio"})
        for radio in radios:
            assert "mask" in radio.get("class", [])
            assert "mask-star-2" in radio.get("class", [])

    def test_selected_value_checked(self):
        widget = RatingInput()
        widget.choices = [("1", "1 star"), ("2", "2 stars"), ("3", "3 stars")]
        soup = render_widget(widget, value="2")
        radios = soup.find_all("input", {"type": "radio"})
        checked = [r for r in radios if r.has_attr("checked")]
        assert len(checked) == 1
        assert checked[0]["value"] == "2"

    def test_allow_clear(self):
        widget = RatingInput(allow_clear=True)
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        hidden = soup.find("input", class_="rating-hidden")
        assert hidden is not None

    def test_custom_star_class(self):
        widget = RatingInput(star_class="mask-heart")
        widget.choices = [("1", "1 star")]
        soup = render_widget(widget, value="1")
        radio = soup.find("input", {"type": "radio", "class": "mask"})
        assert "mask-heart" in radio.get("class", [])

    def test_choices_helper(self):
        choices = RatingInput.make_choices(5)
        assert len(choices) == 5
        assert choices[0] == ("1", "1 star")
        assert choices[4] == ("5", "5 stars")

    def test_mask_class_on_star_inputs(self):
        widget = RatingInput()
        widget.choices = [("1", "1 star"), ("2", "2 stars")]
        soup = render_widget(widget, value="1")
        radios = soup.find_all("input", {"type": "radio"})
        for radio in radios:
            assert "mask" in radio.get("class", [])


class TestPasswordRevealInput:
    def test_renders_password_input(self):
        soup = render_widget(PasswordRevealInput())
        inp = soup.find("input")
        assert inp is not None

    def test_renders_toggle_button(self):
        soup = render_widget(PasswordRevealInput())
        btn = soup.find("button")
        assert btn is not None
        assert btn.get("x-on:click") == "show = !show"

    def test_alpine_x_data(self):
        soup = render_widget(PasswordRevealInput())
        label = soup.find("label")
        assert label.get("x-data") == "{ show: false }"

    def test_alpine_x_bind_type(self):
        soup = render_widget(PasswordRevealInput())
        inp = soup.find("input")
        assert inp.get("x-bind:type") == "show ? 'text' : 'password'"

    def test_wrapped_in_label(self):
        soup = render_widget(PasswordRevealInput())
        label = soup.find("label", class_="input")
        assert label is not None
        assert label.find("input") is not None

    def test_grow_class_on_input(self):
        soup = render_widget(PasswordRevealInput())
        inp = soup.find("input")
        assert "grow" in inp.get("class", [])

    def test_input_inside_label_wrapper(self):
        """Input is inside <label class="input">, not a direct child of fieldset."""
        soup = render_widget(PasswordRevealInput())
        label = soup.find("label", class_="input")
        assert label is not None
        inp = label.find("input")
        assert inp is not None


class TestMultiSelectInput:
    def test_renders_details_dropdown(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        details = soup.find("details", class_="dropdown")
        assert details is not None

    def test_renders_summary_trigger(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        summary = soup.find("summary")
        assert summary is not None
        assert "select" in summary.get("class", [])

    def test_dropdown_content(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        assert dropdown is not None

    def test_options_in_list_items(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        items = soup.find("div", class_="dropdown-content").find("ul").find_all("li")
        assert len(items) == 2

    def test_search_hidden_for_few_choices(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        search = soup.find("input", {"type": "text", "x-model": "search"})
        assert search is None

    def test_search_shown_for_many_choices(self):
        choices = [(str(i), f"Option {i}") for i in range(21)]
        widget = MultiSelectInput(choices=choices)
        soup = render_widget(widget, name="test")
        search = soup.find("input", {"type": "text", "x-model": "search"})
        assert search is not None

    def test_renders_hidden_checkboxes(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        soup = render_widget(widget, name="test")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 3
        for cb in checkboxes:
            assert "hidden" in cb.get("class", [])

    def test_checkbox_values(self):
        widget = MultiSelectInput(choices=[("py", "Python"), ("js", "JS")])
        soup = render_widget(widget, name="lang")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        values = [cb["value"] for cb in checkboxes]
        assert values == ["py", "js"]

    def test_checkbox_name(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="field")
        cb = soup.find("input", {"type": "checkbox"})
        assert cb["name"] == "field"

    def test_selected_values_checked(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        soup = render_widget(widget, name="test", value=["a", "c"])
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        checked = [cb["value"] for cb in checkboxes if cb.has_attr("checked")]
        assert checked == ["a", "c"]

    def test_checkmark_present(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        check = soup.find("span", class_="formwork-check")
        assert check is not None
        assert "opacity-0" in check.get("class", [])

    def test_checkmark_before_label_text(self):
        """Checkmark span comes before the text span, like a native select."""
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        label = soup.find("label")
        children = [c for c in label.children if getattr(c, "name", None)]
        names = [c.name for c in children]
        assert names == ["input", "span", "span"]

    def test_alpine_x_data(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", attrs={"x-data": True})
        assert wrapper is not None

    def test_labels_for_options(self):
        widget = MultiSelectInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        spans = soup.find_all("span", class_="select-none")
        texts = [s.get_text(strip=True) for s in spans]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_no_results_element(self):
        choices = [(str(i), f"Option {i}") for i in range(21)]
        widget = MultiSelectInput(choices=choices)
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is not None
        assert no_results.get("x-show") == "noResults"

    def test_no_results_hidden_for_few_choices(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is None

    def test_aria_invalid_on_summary(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
        summary = soup.find("summary")
        assert summary["aria-invalid"] == "true"

    def test_no_aria_invalid_when_valid(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        summary = soup.find("summary")
        assert not summary.has_attr("aria-invalid")

    def test_multiselect_class_on_checkboxes(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        for cb in checkboxes:
            assert "multiselect" in cb.get("class", [])


class TestComboBoxInput:
    def test_renders_dropdown_wrapper(self):
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", class_="dropdown")
        assert wrapper is not None

    def test_combobox_class_on_wrapper(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", class_="combobox")
        assert wrapper is not None

    def test_renders_text_input_trigger(self):
        """The trigger is a text input, not a summary/select."""
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        trigger = soup.find("input", class_="combobox-input")
        assert trigger is not None
        assert trigger["type"] == "text"

    def test_combobox_role_on_input(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["role"] == "combobox"
        assert trigger["aria-autocomplete"] == "list"

    def test_renders_hidden_value_input(self):
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        hidden = soup.find("input", {"type": "hidden"})
        assert hidden is not None
        assert hidden["name"] == "test"

    def test_dropdown_content(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        assert dropdown is not None

    def test_no_search_input_in_dropdown(self):
        """Search is the trigger input itself, not inside the dropdown."""
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        dropdown = soup.find("div", class_="dropdown-content")
        search = dropdown.find("input", {"type": "text"})
        assert search is None

    def test_options_as_buttons(self):
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 2

    def test_option_labels(self):
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        spans = soup.find_all("span", class_="select-none")
        texts = [s.get_text(strip=True) for s in spans]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_empty_option_excluded(self):
        """The empty option (value='') is excluded from the dropdown list."""
        widget = ComboBoxInput(choices=[("", "Select..."), ("a", "Alpha")])
        soup = render_widget(widget, name="test")
        buttons = soup.find_all("button", {"type": "button"})
        assert len(buttons) == 1

    def test_alpine_x_data(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("div", attrs={"x-data": True})
        assert wrapper is not None

    def test_selected_label_shown_as_text(self):
        """When a value is selected, its label is shown as real input text."""
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        # Alpine sets :value="search" where search starts with selected_label
        # We verify the x-data initializes search with the label
        soup = render_widget(widget, name="test", value="b")
        wrapper = soup.find("div", attrs={"x-data": True})
        x_data = wrapper["x-data"]
        assert "search: 'Beta'" in x_data

    def test_no_results_element(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        no_results = soup.find("p", string="No results")
        assert no_results is not None
        assert no_results.get("x-show") == "noResults"

    def test_listbox_role(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test")
        listbox = soup.find("ul", {"role": "listbox"})
        assert listbox is not None

    def test_id_on_hidden_input(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_city"})
        hidden = soup.find("input", {"type": "hidden"})
        assert hidden["id"] == "id_city"

    def test_selected_label_context(self):
        """get_context returns the label for the selected value."""
        widget = ComboBoxInput(choices=[("a", "Alpha"), ("b", "Beta")])
        ctx = widget.get_context("test", "a", {})
        assert ctx["widget"]["selected_label"] == "Alpha"

    def test_selected_label_empty_when_no_value(self):
        widget = ComboBoxInput(choices=[("", ""), ("a", "Alpha")])
        ctx = widget.get_context("test", "", {})
        # Empty option label should not be shown as selected label
        assert ctx["widget"]["selected_label"] == ""

    def test_aria_invalid_on_input(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test", "aria-invalid": "true"})
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["aria-invalid"] == "true"

    def test_no_aria_invalid_when_valid(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        trigger = soup.find("input", class_="combobox-input")
        assert not trigger.has_attr("aria-invalid")

    def test_aria_controls_links_to_listbox(self):
        widget = ComboBoxInput(choices=[("a", "Alpha")])
        soup = render_widget(widget, name="test", attrs={"id": "id_city"})
        trigger = soup.find("input", class_="combobox-input")
        assert trigger["aria-controls"] == "id_city_listbox"


class TestDataListInput:
    def test_renders_text_input(self):
        widget = DataListInput(datalist=["A", "B"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp is not None
        assert inp.get("type") == "text"

    def test_list_attribute_set(self):
        widget = DataListInput(datalist=["A"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["list"] == "id_test_list"

    def test_datalist_element_rendered(self):
        widget = DataListInput(datalist=["Chrome", "Firefox"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        datalist = soup.find("datalist")
        assert datalist is not None
        assert datalist["id"] == "id_test_list"

    def test_datalist_options(self):
        widget = DataListInput(datalist=["Chrome", "Firefox", "Safari"])
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        options = soup.find("datalist").find_all("option")
        assert len(options) == 3
        values = [o["value"] for o in options]
        assert values == ["Chrome", "Firefox", "Safari"]

    def test_empty_datalist(self):
        widget = DataListInput()
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        options = soup.find("datalist").find_all("option")
        assert len(options) == 0

    def test_no_datalist_without_id(self):
        """Without an id, no datalist or list attr is rendered."""
        widget = DataListInput(datalist=["A"])
        soup = render_widget(widget, name="test")
        datalist = soup.find("datalist")
        assert datalist is None

    def test_preserves_value(self):
        widget = DataListInput(datalist=["A", "B"])
        soup = render_widget(widget, name="test", value="hello", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["value"] == "hello"

    def test_preserves_placeholder(self):
        widget = DataListInput(datalist=["A"], attrs={"placeholder": "Pick one"})
        soup = render_widget(widget, name="test", attrs={"id": "id_test"})
        inp = soup.find("input")
        assert inp["placeholder"] == "Pick one"
