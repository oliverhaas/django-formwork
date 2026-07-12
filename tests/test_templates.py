from bs4 import BeautifulSoup
from django import forms
from django.template import Context, Template

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

    def test_help_text_has_leading_info_icon(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        soup = render_html(F())
        helptext = soup.find("p", class_="label")
        icon = helptext.find("i", class_="icon-info")
        assert icon is not None
        assert icon.get("aria-hidden") == "true"

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


class TestInlineErrorRendering:
    """Errors render as a red help-text-style row when Meta.error_display = "inline"."""

    def test_no_tooltip_wrapper(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        assert soup.find("div", class_="tooltip") is None

    def test_error_row_has_role_alert_and_id(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error_row = soup.find("p", attrs={"id": "id_name_error"})
        assert error_row is not None
        assert error_row["role"] == "alert"
        assert "text-error" in error_row.get("class", [])

    def test_error_row_has_leading_icon(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error_row = soup.find("p", attrs={"id": "id_name_error"})
        icon = error_row.find("i", class_="icon-circle-alert")
        assert icon is not None
        assert icon.get("aria-hidden") == "true"

    def test_error_row_has_formwork_errors_hook(self):
        # .formwork-errors is what disableNativeValidation() keys off, so inline
        # mode reaches parity with tooltip mode: once a server error is showing,
        # native validation turns off and later errors route to the server.
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error_row = soup.find("p", attrs={"id": "id_name_error"})
        assert "formwork-errors" in error_row.get("class", [])

    def test_multiple_errors_joined_in_single_row(self):
        class F(FormworkForm):
            email = forms.EmailField(min_length=20)

        form = F(data={"email": "bad"}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error_row = soup.find("p", attrs={"id": "id_email_error"})
        assert error_row.find_all("p") == []
        assert len(form.errors["email"]) >= 2
        for message in form.errors["email"]:
            assert message in error_row.get_text()

    def test_help_text_hidden_but_present_when_collapsed(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Enter your name")

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        helptext = soup.find("p", attrs={"id": "id_name_helptext"})
        assert helptext is not None
        assert "Enter your name" in helptext.get_text()
        assert "sr-only" in helptext.get(":class", "")

    def test_no_more_button_when_no_help_text_and_no_overflow(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        error_row = soup.find("p", attrs={"id": "id_name_error"})
        button = error_row.find("button")
        assert button is not None
        assert "x-show" in button.attrs

    def test_tooltip_mode_still_default(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        assert soup.find("div", class_="tooltip") is not None
        assert soup.find("p", attrs={"id": "id_name_error"}) is None


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

    def test_aria_describedby_targets_exist(self):
        """Every id referenced by aria-describedby must point to a real element.

        Django bakes ``aria-describedby="{auto_id}_error"`` onto the widget, so
        the error container's id has to match it or the reference dangles for
        screen readers.
        """

        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        described = (inp.get("aria-describedby") or "").split()
        assert described, "expected aria-describedby on an errored field"
        for ref in described:
            assert soup.find(id=ref) is not None, f"aria-describedby points to missing #{ref}"

    def test_aria_describedby_targets_exist_in_inline_mode(self):
        """The sr-only help text must stay in the DOM so aria-describedby still resolves."""

        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        form = F(data={"name": ""}, error_display="inline")
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        described = (inp.get("aria-describedby") or "").split()
        assert described, "expected aria-describedby on an errored field"
        for ref in described:
            assert soup.find(id=ref) is not None, f"aria-describedby points to missing #{ref}"


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


class TestMorphingIds:
    """All elements have stable IDs for htmx morph matching."""

    def test_fieldset_has_id(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_name_field"

    def test_fieldset_id_uses_auto_id(self):
        class F(FormworkForm):
            email = forms.EmailField()

        soup = render_html(F())
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_email_field"

    def test_fieldset_id_with_prefix(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F(prefix="contact"))
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_contact-name_field"

    def test_tooltip_has_id_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        tooltip = soup.find("div", class_="tooltip")
        assert tooltip["id"] == "id_name_tooltip"

    def test_errors_div_has_id_on_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        errors = soup.find("div", class_="tooltip-content")
        assert errors["id"] == "id_name_error"

    def test_non_field_errors_has_id(self):
        class F(FormworkForm):
            name = forms.CharField()

            def clean(self):
                raise forms.ValidationError("Form-level error")

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        alert = soup.find("div", class_="alert")
        assert alert["id"] == "formwork-non-field-errors"

    def test_use_fieldset_branch_has_ids(self):
        """RadioSelect fields use <legend> and use_fieldset=True branch."""

        class F(FormworkForm):
            choice = forms.ChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=forms.RadioSelect,
            )

        form = F(data={})
        form.is_valid()
        soup = render_html(form)
        fieldset = soup.find("fieldset", class_="fieldset")
        assert fieldset["id"] == "id_choice_field"
        tooltip = soup.find("div", class_="tooltip")
        assert tooltip["id"] == "id_choice_tooltip"
        errors = soup.find("div", class_="tooltip-content")
        assert errors["id"] == "id_choice_error"

    def test_no_tooltip_id_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        tooltip = soup.find("div", class_="tooltip")
        assert tooltip is None


class TestTemplateTags:
    """The formwork_css and formwork_js template tags output correct HTML."""

    def test_formwork_css_tag(self):
        template = Template("{% load formwork %}{% formwork_css %}")
        html = template.render(Context())
        assert "<link" in html
        assert "formwork/formwork.css" in html

    def test_formwork_js_tag(self):
        template = Template("{% load formwork %}{% formwork_js %}")
        html = template.render(Context())
        assert "<script" in html
        assert "formwork/formwork.js" in html
