from django import forms

from django_formwork.forms import FormworkForm, FormworkModelForm


class TestFormworkForm:
    def test_template_name(self):
        assert FormworkForm.template_name == "django/forms/formwork.html"

    def test_renders_without_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F()
        html = str(form)
        assert "<input" in html

    def test_no_widget_attrs_mutation(self):
        """FormworkForm does not mutate widget.attrs at init time."""

        class F(FormworkForm):
            name = forms.CharField()

        form = F()
        assert "class" not in form.fields["name"].widget.attrs


class TestFormworkModelForm:
    def test_template_name(self):
        assert FormworkModelForm.template_name == "django/forms/formwork.html"
