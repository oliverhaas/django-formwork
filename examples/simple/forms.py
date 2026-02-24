from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import PasswordRevealInput, RangeInput, RatingInput, ToggleInput


class ContactForm(FormworkForm):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    priority = forms.ChoiceField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")])


class WidgetShowcaseForm(FormworkForm):
    password = forms.CharField(widget=PasswordRevealInput)
    agree_to_terms = forms.BooleanField(widget=ToggleInput, required=False)
    volume = forms.IntegerField(widget=RangeInput(attrs={"min": "0", "max": "100", "step": "10"}))
    rating = forms.TypedChoiceField(
        choices=RatingInput.make_choices(5),
        coerce=int,
        widget=RatingInput,
    )
    file_upload = forms.FileField(required=False)
