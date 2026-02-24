from bs4 import BeautifulSoup
from django import forms

from django_formwork.forms import FormworkForm


def render_html(form):
    return BeautifulSoup(str(form), "html.parser")


class TestDaisyUIWidgetClasses:
    """Widgets get correct DaisyUI classes in rendered HTML."""

    def test_text_input_has_input_class(self):
        class F(FormworkForm):
            name = forms.CharField()

        soup = render_html(F())
        inp = soup.find("input", {"name": "name"})
        assert "input" in inp.get("class", [])

    def test_textarea_has_textarea_class(self):
        class F(FormworkForm):
            bio = forms.CharField(widget=forms.Textarea)

        soup = render_html(F())
        ta = soup.find("textarea")
        assert "textarea" in ta.get("class", [])

    def test_select_has_select_class(self):
        class F(FormworkForm):
            choice = forms.ChoiceField(choices=[("a", "A")])

        soup = render_html(F())
        sel = soup.find("select")
        assert "select" in sel.get("class", [])

    def test_checkbox_has_checkbox_class(self):
        class F(FormworkForm):
            agree = forms.BooleanField(required=False)

        soup = render_html(F())
        inp = soup.find("input", {"type": "checkbox"})
        assert "checkbox" in inp.get("class", [])

    def test_file_input_has_file_input_class(self):
        class F(FormworkForm):
            doc = forms.FileField(required=False)

        soup = render_html(F())
        inp = soup.find("input", {"type": "file"})
        assert "file-input" in inp.get("class", [])


class TestErrorClassesInRenderedHTML:
    """Error modifier classes appear in rendered HTML."""

    def test_input_error_class(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": ""})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        assert "input-error" in inp.get("class", [])

    def test_textarea_error_class(self):
        class F(FormworkForm):
            bio = forms.CharField(widget=forms.Textarea)

        form = F(data={"bio": ""})
        form.is_valid()
        soup = render_html(form)
        ta = soup.find("textarea")
        assert "textarea-error" in ta.get("class", [])

    def test_select_error_class(self):
        class F(FormworkForm):
            choice = forms.ChoiceField(choices=[("a", "A")])

        form = F(data={"choice": ""})
        form.is_valid()
        soup = render_html(form)
        sel = soup.find("select")
        assert "select-error" in sel.get("class", [])

    def test_no_error_class_when_valid(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F(data={"name": "test"})
        form.is_valid()
        soup = render_html(form)
        inp = soup.find("input", {"name": "name"})
        assert "input-error" not in inp.get("class", [])


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

    def test_aria_describedby_for_help_text(self):
        class F(FormworkForm):
            name = forms.CharField(help_text="Your name")

        soup = render_html(F())
        inp = soup.find("input", {"name": "name"})
        assert inp is not None
        assert "id_name_helptext" in (inp.get("aria-describedby") or "")


class TestHiddenFields:
    """Hidden fields render without visible wrapper."""

    def test_hidden_field_rendered(self):
        class F(FormworkForm):
            visible = forms.CharField()
            hidden = forms.CharField(widget=forms.HiddenInput)

        soup = render_html(F())
        hidden_input = soup.find("input", {"type": "hidden", "name": "hidden"})
        assert hidden_input is not None
