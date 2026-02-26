from bs4 import BeautifulSoup
from django import forms

from django_formwork.widgets import (
    DAISY_CLASSES,
    MultiSelectInput,
    PasswordRevealInput,
    RangeInput,
    RatingInput,
    ToggleInput,
    _add_css_class,
    apply_daisy_classes,
)


def render_widget(widget, name="test", value=None, attrs=None):
    """Render a widget and return BeautifulSoup."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


class TestAddCssClass:
    def test_adds_to_empty(self):
        attrs = {}
        _add_css_class(attrs, "input")
        assert attrs["class"] == "input"

    def test_appends(self):
        attrs = {"class": "custom"}
        _add_css_class(attrs, "input")
        assert attrs["class"] == "custom input"

    def test_no_duplicate(self):
        attrs = {"class": "input"}
        _add_css_class(attrs, "input")
        assert attrs["class"] == "input"


class TestApplyDaisyClasses:
    def test_text_input(self):
        class F(forms.Form):
            name = forms.CharField()

        form = F()
        apply_daisy_classes(form)
        assert "input" in form.fields["name"].widget.attrs["class"]

    def test_textarea(self):
        class F(forms.Form):
            bio = forms.CharField(widget=forms.Textarea)

        form = F()
        apply_daisy_classes(form)
        assert "textarea" in form.fields["bio"].widget.attrs["class"]

    def test_select(self):
        class F(forms.Form):
            choice = forms.ChoiceField(choices=[("a", "A")])

        form = F()
        apply_daisy_classes(form)
        assert "select" in form.fields["choice"].widget.attrs["class"]

    def test_checkbox(self):
        class F(forms.Form):
            agree = forms.BooleanField()

        form = F()
        apply_daisy_classes(form)
        assert "checkbox" in form.fields["agree"].widget.attrs["class"]

    def test_radio(self):
        class F(forms.Form):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F()
        apply_daisy_classes(form)
        assert "radio" in form.fields["choice"].widget.attrs["class"]

    def test_file_input(self):
        class F(forms.Form):
            doc = forms.FileField()

        form = F()
        apply_daisy_classes(form)
        assert "file-input" in form.fields["doc"].widget.attrs["class"]

    def test_preserves_existing_classes(self):
        class F(forms.Form):
            name = forms.CharField(widget=forms.TextInput(attrs={"class": "my-class"}))

        form = F()
        apply_daisy_classes(form)
        css = form.fields["name"].widget.attrs["class"]
        assert "my-class" in css
        assert "input" in css

    def test_all_mapped_widgets_covered(self):
        """All widgets in DAISY_CLASSES should get their class applied."""
        for widget_class, css_class in DAISY_CLASSES.items():
            widget = widget_class()
            form_field = forms.CharField(widget=widget)

            class F(forms.Form):
                field = form_field

            form = F()
            apply_daisy_classes(form)
            assert css_class in form.fields["field"].widget.attrs.get("class", ""), (
                f"{widget_class.__name__} should get '{css_class}'"
            )


class TestToggleInput:
    def test_has_toggle_class(self):
        widget = ToggleInput()
        assert "toggle" in widget.attrs["class"]

    def test_renders_checkbox(self):
        soup = render_widget(ToggleInput())
        inp = soup.find("input")
        assert inp is not None
        assert inp["type"] == "checkbox"

    def test_toggle_class_in_output(self):
        soup = render_widget(ToggleInput())
        inp = soup.find("input")
        assert "toggle" in inp.get("class", [])


class TestRangeInput:
    def test_has_range_class(self):
        widget = RangeInput()
        assert "range" in widget.attrs["class"]

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
        radio = soup.find("input", {"type": "radio"})
        assert "mask-heart" in radio.get("class", [])

    def test_choices_helper(self):
        choices = RatingInput.make_choices(5)
        assert len(choices) == 5
        assert choices[0] == ("1", "1 star")
        assert choices[4] == ("5", "5 stars")


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


class TestRadioSelectTemplate:
    """RadioSelect gets a custom template that doesn't put class on wrapper."""

    def test_template_overridden(self):
        class F(forms.Form):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F()
        apply_daisy_classes(form)
        assert form.fields["choice"].widget.template_name == "formwork/widgets/radio.html"

    def test_wrapper_div_has_no_daisy_class(self):
        class F(forms.Form):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F()
        apply_daisy_classes(form)
        soup = render_widget(form.fields["choice"].widget, name="choice", value="a")
        wrapper = soup.find("div", recursive=False)
        assert "radio" not in wrapper.get("class", [])

    def test_individual_inputs_have_daisy_class(self):
        class F(forms.Form):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F()
        apply_daisy_classes(form)
        soup = render_widget(form.fields["choice"].widget, name="choice", value="a")
        radios = soup.find_all("input", {"type": "radio"})
        assert len(radios) == 2
        for radio in radios:
            assert "radio" in radio.get("class", [])


class TestCheckboxSelectMultipleTemplate:
    """CheckboxSelectMultiple gets a custom template."""

    def test_template_overridden(self):
        class F(forms.Form):
            multi = forms.MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.CheckboxSelectMultiple,
            )

        form = F()
        apply_daisy_classes(form)
        assert form.fields["multi"].widget.template_name == "formwork/widgets/checkbox_select.html"

    def test_wrapper_div_has_no_daisy_class(self):
        class F(forms.Form):
            multi = forms.MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.CheckboxSelectMultiple,
            )

        form = F()
        apply_daisy_classes(form)
        soup = render_widget(form.fields["multi"].widget, name="multi", value=["a"])
        wrapper = soup.find("div", recursive=False)
        assert "checkbox" not in wrapper.get("class", [])

    def test_individual_inputs_have_daisy_class(self):
        class F(forms.Form):
            multi = forms.MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.CheckboxSelectMultiple,
            )

        form = F()
        apply_daisy_classes(form)
        soup = render_widget(form.fields["multi"].widget, name="multi", value=["a"])
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 2
        for cb in checkboxes:
            assert "checkbox" in cb.get("class", [])


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

    def test_dropdown_uses_menu(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        menu = soup.find("ul", class_="menu")
        assert menu is not None

    def test_options_in_list_items(self):
        widget = MultiSelectInput(choices=[("a", "A"), ("b", "B")])
        soup = render_widget(widget, name="test")
        items = soup.find("ul", class_="menu").find_all("li")
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

    def test_checkmark_svg_present(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        svg = soup.find("svg")
        assert svg is not None

    def test_alpine_x_data(self):
        widget = MultiSelectInput(choices=[("a", "A")])
        soup = render_widget(widget, name="test")
        wrapper = soup.find("details", attrs={"x-data": True})
        assert wrapper is not None

    def test_labels_for_options(self):
        widget = MultiSelectInput(choices=[("a", "Alpha"), ("b", "Beta")])
        soup = render_widget(widget, name="test")
        labels = soup.find_all("label")
        texts = [lab.get_text(strip=True) for lab in labels]
        assert "Alpha" in texts
        assert "Beta" in texts
