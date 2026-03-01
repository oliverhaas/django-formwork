from bs4 import BeautifulSoup
from django import forms

from django_formwork.forms import FormworkForm


def render_html(form):
    return BeautifulSoup(str(form), "html.parser")


class TestFieldsetStructure:
    """Each visible field is wrapped in a DaisyUI fieldset."""

    def test_field_wrapped_in_fieldset(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset is not None

    def test_label_is_fieldset_legend(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        assert label is not None
        assert "Name" in label.get_text()

    def test_label_has_for_attribute(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        assert label["for"] == "id_name"

    def test_widget_inside_fieldset(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        inp = fieldset.find("input")
        assert inp is not None

    def test_help_text_as_label_paragraph(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        helptext = soup.find("p", class_="label")
        assert helptext is not None
        assert "Enter your name" in helptext.get_text()

    def test_help_text_has_id(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        helptext = soup.find("p", class_="label", id="id_name_helptext")
        assert helptext is not None

    def test_multi_widget_uses_legend(self):
        """RadioSelect fields use <legend> instead of <label>."""

        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        soup = render_html(F())
        legend = soup.find("legend", class_="fieldset-legend")
        assert legend is not None
        assert "Choice" in legend.get_text()


class TestFieldOrdering:
    """Label -> widget -> errors -> helptext ordering."""

    def test_label_before_widget(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        all_elements = list(soup.descendants)
        label = soup.find("label", class_="fieldset-legend")
        inp = soup.find("input")
        assert all_elements.index(label) < all_elements.index(inp)

    def test_widget_before_helptext(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Help")

        soup = render_html(F())
        all_elements = list(soup.descendants)
        inp = soup.find("input")
        helptext = soup.find("p", class_="label")
        assert all_elements.index(inp) < all_elements.index(helptext)

    def test_errors_before_helptext(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Help")

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        helptext = soup.find("p", attrs={"id": "id_name_helptext"})
        assert error_div is not None
        assert helptext is not None
        all_elements = list(soup.descendants)
        assert all_elements.index(error_div) < all_elements.index(helptext)


class TestErrorRendering:
    """Errors render as DaisyUI tooltip on the fieldset."""

    def test_errors_rendered_in_container(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div is not None
        assert error_div.find("p") is not None

    def test_error_container_has_role_alert(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div["role"] == "alert"

    def test_tooltip_wrapper_around_widget_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        wrapper = soup.find("div", class_="tooltip")
        assert wrapper is not None
        assert "tooltip-error" in wrapper.get("class", [])
        assert "tooltip-bottom" in wrapper.get("class", [])
        # Widget is inside the tooltip wrapper
        assert wrapper.find("input") is not None

    def test_no_tooltip_wrapper_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        wrapper = soup.find("div", class_="tooltip")
        assert wrapper is None

    def test_no_errors_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        assert error_div is None

    def test_multiple_errors_in_single_container(self):
        class F(FormworkForm):
            email = forms.EmailField(min_length=20)

        form = F(data={"email": "bad"})
        form.is_valid()
        soup = render_html(form)
        error_div = soup.find("div", class_="tooltip-content")
        errors = error_div.find_all("p")
        assert len(errors) >= 2


class TestNonFieldErrors:
    """Non-field errors use DaisyUI alert component."""

    def test_non_field_errors_rendered(self):
        class F(FormworkForm):
            name = forms.CharField()

            def clean(self):
                raise forms.ValidationError("Form-level error")

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        alert = soup.find("div", class_="alert")
        assert alert is not None
        assert "alert-error" in alert.get("class", [])
        assert "Form-level error" in alert.get_text()


class TestAriaAttributes:
    """Django's built-in aria attributes are preserved."""

    def test_aria_invalid_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"aria-invalid": "true"})
        assert inp is not None

    def test_no_aria_invalid_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        assert inp.get("aria-invalid") is None

    def test_aria_describedby_for_help_text(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        soup = render_html(F())
        inp = soup.find("input", {"name": "name"})
        assert inp is not None
        assert "id_name_helptext" in (inp.get("aria-describedby") or "")


class TestHiddenFields:
    """Hidden fields render without fieldset wrapper."""

    def test_hidden_field_rendered(self):
        class F(FormworkForm):
            visible = forms.CharField()
            hidden = forms.CharField(widget=forms.HiddenInput)

        soup = render_html(F())
        hidden_input = soup.find("input", {"type": "hidden", "name": "hidden"})
        assert hidden_input is not None

    def test_hidden_field_not_in_fieldset(self):
        class F(FormworkForm):
            visible = forms.CharField()
            hidden = forms.CharField(widget=forms.HiddenInput)

        soup = render_html(F())
        fieldsets = soup.find_all("fieldset", class_="fieldset")
        legends = [fs.find(["legend", "label"], class_="fieldset-legend") for fs in fieldsets]
        legend_texts = [leg.get_text() for leg in legends if leg]
        assert not any("Hidden" in t for t in legend_texts)


class TestRequiredFieldAsterisk:
    """Required fields show an asterisk indicator."""

    def test_required_field_has_asterisk(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        asterisk = label.find("span", class_="text-error")
        assert asterisk is not None
        assert "*" in asterisk.get_text()

    def test_optional_field_no_asterisk(self):
        class F(FormworkForm):
            name = forms.CharField(required=False)

        soup = render_html(F())
        label = soup.find("label", class_="fieldset-legend")
        asterisk = label.find("span", class_="text-error")
        assert asterisk is None

    def test_required_fieldset_widget_has_asterisk(self):
        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        soup = render_html(F())
        legend = soup.find("legend", class_="fieldset-legend")
        asterisk = legend.find("span", class_="text-error")
        assert asterisk is not None

    def test_optional_fieldset_widget_no_asterisk(self):
        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
                required=False,
            )

        soup = render_html(F())
        legend = soup.find("legend", class_="fieldset-legend")
        asterisk = legend.find("span", class_="text-error")
        assert asterisk is None
