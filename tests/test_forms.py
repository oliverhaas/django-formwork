import pytest
from django import forms
from django.test import override_settings

from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.renderers import FormworkRenderer


class TestFormworkForm:
    def test_default_renderer(self):
        assert FormworkForm.default_renderer is FormworkRenderer

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

    def test_as_field_group_uses_formwork_template(self):
        """as_field_group on a FormworkForm field uses the formwork field template."""

        class F(FormworkForm):
            name = forms.CharField()

        form = F()
        html = form["name"].as_field_group()
        assert "fieldset" in html
        assert "fieldset-legend" in html


class TestFormworkModelForm:
    def test_default_renderer(self):
        assert FormworkModelForm.default_renderer is FormworkRenderer


class TestFormworkRenderer:
    def test_form_template_name(self):
        assert FormworkRenderer.form_template_name == "django/forms/formwork.html"

    def test_field_template_name(self):
        assert FormworkRenderer.field_template_name == "django/forms/formwork_field.html"

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

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_as_field_group_uses_formwork_field_template(self):
        """as_field_group on a plain Form uses the formwork field template."""

        class F(forms.Form):
            name = forms.CharField()

        form = F()
        html = form["name"].as_field_group()
        assert "fieldset" in html
        assert "fieldset-legend" in html

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_as_field_group_renders_errors_in_tooltip(self):
        """as_field_group renders validation errors in a tooltip."""

        class F(forms.Form):
            name = forms.CharField()

        form = F(data={})
        form.is_valid()
        html = form["name"].as_field_group()
        assert "tooltip" in html
        assert "formwork-errors" in html

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_as_field_group_renders_help_text(self):
        """as_field_group renders help text."""

        class F(forms.Form):
            name = forms.CharField(help_text="Enter your name")

        form = F()
        html = form["name"].as_field_group()
        assert "Enter your name" in html
        assert 'class="label"' in html

    @override_settings(FORM_RENDERER="django_formwork.FormworkRenderer")
    def test_as_field_group_renders_required_marker(self):
        """as_field_group shows required marker for required fields."""

        class F(forms.Form):
            name = forms.CharField()
            optional = forms.CharField(required=False)

        form = F()
        name_html = form["name"].as_field_group()
        optional_html = form["optional"].as_field_group()
        assert "text-error" in name_html
        assert "text-error" not in optional_html

    def test_plain_form_without_renderer_uses_default(self):
        """Without FORM_RENDERER setting, plain Form uses Django's div.html."""

        class F(forms.Form):
            name = forms.CharField()

        html = str(F())
        assert "fieldset-legend" not in html


@pytest.mark.django_db
@pytest.mark.integration
def test_model_form_renders_with_formwork_renderer():
    """FormworkModelForm renders model fields with formwork templates."""
    from e2e.models import BasicFormData

    class TestModelForm(FormworkModelForm):
        class Meta:
            model = BasicFormData
            fields = ["name", "email", "message"]

    form = TestModelForm()
    html = str(form)
    # Should render with formwork fieldset structure
    assert 'class="fieldset"' in html
    assert 'name="name"' in html
    assert 'name="email"' in html


@pytest.mark.django_db
@pytest.mark.integration
def test_model_form_saves_to_database():
    """FormworkModelForm.save() creates a model instance."""
    from e2e.models import BasicFormData

    class TestModelForm(FormworkModelForm):
        class Meta:
            model = BasicFormData
            fields = ["name", "email", "message"]

    form = TestModelForm(data={"name": "Alice", "email": "a@b.com", "message": "Hi"})
    assert form.is_valid()
    obj = form.save()
    assert obj.pk is not None
    assert obj.name == "Alice"


@pytest.mark.django_db
@pytest.mark.integration
def test_model_form_validation_errors():
    """FormworkModelForm shows errors for invalid data."""
    from e2e.models import BasicFormData

    class TestModelForm(FormworkModelForm):
        class Meta:
            model = BasicFormData
            fields = ["name", "email"]

    form = TestModelForm(data={"name": "", "email": "not-an-email"})
    assert not form.is_valid()
    html = str(form)
    assert "formwork-errors" in html


@pytest.mark.integration
def test_formset_renders_with_formwork_renderer():
    """Formsets render correctly with FormworkRenderer."""
    from django.forms import formset_factory

    class ItemForm(FormworkForm):
        name = forms.CharField()
        quantity = forms.IntegerField()

    item_formset_cls = formset_factory(ItemForm, extra=2)
    formset = item_formset_cls()
    formset.renderer = FormworkRenderer()
    html = str(formset)
    # Should contain form fields
    assert 'name="form-0-name"' in html
    assert 'name="form-1-name"' in html
    # Should have formwork fieldset structure
    assert 'class="fieldset"' in html
