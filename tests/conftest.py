import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import RangeInput, RatingInput, ToggleInput


class SimpleForm(forms.Form):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


class AllWidgetsForm(FormworkForm):
    text = forms.CharField()
    email = forms.EmailField()
    url = forms.URLField()
    number = forms.IntegerField()
    password = forms.CharField(widget=forms.PasswordInput)
    textarea = forms.CharField(widget=forms.Textarea)
    checkbox = forms.BooleanField(required=False)
    select = forms.ChoiceField(choices=[("a", "A"), ("b", "B")])
    radio = forms.ChoiceField(
        choices=[("x", "X"), ("y", "Y")],
        widget=forms.RadioSelect,
    )
    multi_checkbox = forms.MultipleChoiceField(
        choices=[("1", "One"), ("2", "Two")],
        widget=forms.CheckboxSelectMultiple,
    )
    date = forms.DateField()
    file = forms.FileField(required=False)
    hidden = forms.CharField(widget=forms.HiddenInput)


class CustomWidgetsForm(FormworkForm):
    toggle = forms.BooleanField(widget=ToggleInput, required=False)
    volume = forms.IntegerField(widget=RangeInput(attrs={"min": "0", "max": "100"}))
    rating = forms.TypedChoiceField(
        choices=RatingInput.make_choices(5),
        coerce=int,
        widget=RatingInput,
    )


class SimpleFormworkForm(FormworkForm):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


@pytest.fixture
def simple_form():
    return SimpleForm()


@pytest.fixture
def all_widgets_form():
    return AllWidgetsForm()


@pytest.fixture
def custom_widgets_form():
    return CustomWidgetsForm()


@pytest.fixture
def simple_formwork_form():
    return SimpleFormworkForm()


@pytest.fixture
def bound_form_with_errors():
    form = SimpleFormworkForm(data={"name": "", "email": "bad", "message": ""})
    form.is_valid()
    return form
