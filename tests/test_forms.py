from django import forms

from django_formwork.forms import FormworkBoundField, FormworkForm, FormworkModelForm


class TestFormworkForm:
    def test_uses_formwork_bound_field(self):
        assert FormworkForm.bound_field_class is FormworkBoundField

    def test_applies_daisy_classes(self):
        class F(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            bio = forms.CharField(widget=forms.Textarea)

        form = F()
        assert "input" in form.fields["name"].widget.attrs.get("class", "")
        assert "input" in form.fields["email"].widget.attrs.get("class", "")
        assert "textarea" in form.fields["bio"].widget.attrs.get("class", "")

    def test_preserves_custom_attrs(self):
        class F(FormworkForm):
            name = forms.CharField(widget=forms.TextInput(attrs={"class": "custom"}))

        form = F()
        css = form.fields["name"].widget.attrs["class"]
        assert "custom" in css
        assert "input" in css

    def test_renders_without_error(self):
        class F(FormworkForm):
            name = forms.CharField()

        form = F()
        html = str(form)
        assert "<input" in html

    def test_error_classes_on_bound_field(self):
        class F(FormworkForm):
            name = forms.CharField()
            bio = forms.CharField(widget=forms.Textarea)
            choice = forms.ChoiceField(choices=[("a", "A")])

        form = F(data={"name": "", "bio": "", "choice": ""})
        form.is_valid()
        html = str(form)
        assert "input-error" in html
        assert "textarea-error" in html
        assert "select-error" in html


class TestFormworkModelForm:
    def test_uses_formwork_bound_field(self):
        assert FormworkModelForm.bound_field_class is FormworkBoundField
