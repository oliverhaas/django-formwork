from django import forms
from django.test import override_settings

from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.renderers import FormworkRenderer


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


class TestFormworkRenderer:
    def test_form_template_name(self):
        assert FormworkRenderer.form_template_name == "django/forms/formwork.html"

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_plain_form_uses_formwork_template(self):
        """A plain Form rendered with FormworkRenderer uses the formwork template."""

        class F(forms.Form):
            name = forms.CharField()

        html = str(F())
        assert "fieldset" in html
        assert "fieldset-legend" in html

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_plain_form_renders_errors_in_tooltip(self):
        """Validation errors render inside a tooltip wrapper."""

        class F(forms.Form):
            name = forms.CharField()

        form = F(data={})
        form.is_valid()
        html = str(form)
        assert "tooltip" in html
        assert "formwork-errors" in html

    def test_plain_form_without_renderer_uses_default(self):
        """Without FORM_RENDERER setting, plain Form uses Django's div.html."""

        class F(forms.Form):
            name = forms.CharField()

        html = str(F())
        assert "fieldset-legend" not in html
