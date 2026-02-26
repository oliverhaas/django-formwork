from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    MultiSelectInput,
    PasswordRevealInput,
    RangeInput,
    RatingInput,
    ToggleInput,
)


class ContactForm(FormworkForm):
    name = forms.CharField(
        max_length=100,
        help_text="Your full name",
        widget=forms.TextInput(attrs={"placeholder": "Jane Doe"}),
    )
    email = forms.EmailField(
        help_text="We'll never share your email",
        widget=forms.EmailInput(attrs={"placeholder": "jane@example.com"}),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us what you need..."}),
        help_text="What can we help you with?",
    )
    priority = forms.ChoiceField(
        choices=[("", "Select priority..."), ("low", "Low"), ("medium", "Medium"), ("high", "High")],
    )


class WidgetShowcaseForm(FormworkForm):
    password = forms.CharField(
        widget=PasswordRevealInput(attrs={"placeholder": "Enter your password"}),
        help_text="Must be at least 8 characters",
    )
    agree_to_terms = forms.BooleanField(widget=ToggleInput, required=False, help_text="You agree to our terms")
    volume = forms.IntegerField(
        widget=RangeInput(attrs={"min": "0", "max": "100", "step": "10"}),
        help_text="Adjust the volume level",
    )
    rating = forms.TypedChoiceField(
        choices=RatingInput.make_choices(5),
        coerce=int,
        widget=RatingInput,
        help_text="Rate your experience",
    )
    file_upload = forms.FileField(required=False, help_text="PDF or image, max 5MB")


class AllWidgetsForm(FormworkForm):
    """Demonstrates all Django widget types with DaisyUI styling."""

    # Text-like inputs
    text = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Enter text"}),
        help_text="Standard text input",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "user@example.com"}),
        help_text="Email input with validation",
    )
    url = forms.URLField(
        widget=forms.URLInput(attrs={"placeholder": "https://example.com"}),
        help_text="URL input",
    )
    search = forms.CharField(
        widget=forms.SearchInput(attrs={"placeholder": "Search..."}),
        help_text="Search input",
        required=False,
    )
    phone = forms.CharField(
        widget=forms.TelInput(attrs={"placeholder": "+1 (555) 000-0000"}),
        help_text="Telephone input",
        required=False,
    )
    number = forms.IntegerField(
        widget=forms.NumberInput(attrs={"placeholder": "42"}),
        help_text="Number input",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Secret"}),
        help_text="Standard password input",
    )
    color = forms.CharField(
        widget=forms.ColorInput,
        help_text="Color picker",
        required=False,
    )

    # Date/time inputs
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date picker",
        required=False,
    )
    time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="Time picker",
        required=False,
    )
    datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Date and time picker",
        required=False,
    )

    # Textarea
    textarea = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Write something..."}),
        help_text="Multi-line text area",
    )

    # Select widgets
    select = forms.ChoiceField(
        choices=[("", "Choose..."), ("a", "Option A"), ("b", "Option B"), ("c", "Option C")],
        help_text="Single select dropdown",
    )
    select_multiple = forms.MultipleChoiceField(
        choices=[("python", "Python"), ("js", "JavaScript"), ("go", "Go"), ("rust", "Rust")],
        widget=MultiSelectInput,
        help_text="Multi-select dropdown with checkboxes",
        required=False,
    )

    # Radio and checkbox
    radio = forms.ChoiceField(
        choices=[("sm", "Small"), ("md", "Medium"), ("lg", "Large")],
        widget=forms.RadioSelect,
        help_text="Radio button group",
    )
    checkbox = forms.BooleanField(
        required=False,
        help_text="Single checkbox",
    )
    checkbox_multiple = forms.MultipleChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("push", "Push")],
        widget=forms.CheckboxSelectMultiple,
        help_text="Multiple checkboxes",
        required=False,
    )

    # File
    file = forms.FileField(
        required=False,
        help_text="File upload",
    )

    # Custom formwork widgets
    toggle = forms.BooleanField(
        widget=ToggleInput,
        required=False,
        help_text="Toggle switch",
    )
    range_slider = forms.IntegerField(
        widget=RangeInput(attrs={"min": "0", "max": "100", "step": "10"}),
        help_text="Range slider",
    )
    star_rating = forms.TypedChoiceField(
        choices=RatingInput.make_choices(5),
        coerce=int,
        widget=RatingInput,
        help_text="Star rating",
    )
    password_reveal = forms.CharField(
        widget=PasswordRevealInput(attrs={"placeholder": "Reveal me"}),
        help_text="Password with reveal toggle",
    )
