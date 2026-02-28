from bs4 import BeautifulSoup

from django_formwork.widgets import (
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
        dropdown = soup.find("ul", class_="dropdown-content")
        assert dropdown is not None

    def test_options_in_list_items(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        items = soup.find("ul", class_="dropdown-content").find_all("li")
        assert len(items) == 2

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

    def test_multiselect_class_on_checkboxes(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        for cb in checkboxes:
            assert "multiselect" in cb.get("class", [])
