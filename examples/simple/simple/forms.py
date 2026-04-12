"""Example form demonstrating standard and custom formwork widgets."""

from django import forms

from django_formwork.widgets import (
    ComboBox,
    DataList,
    MultiSelect,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
    Toggle,
)

COUNTRY_CHOICES = [
    ("us", "United States"),
    ("gb", "United Kingdom"),
    ("de", "Germany"),
    ("fr", "France"),
    ("jp", "Japan"),
    ("au", "Australia"),
    ("br", "Brazil"),
    ("ca", "Canada"),
]

LANGUAGE_CHOICES = [
    ("py", "Python"),
    ("js", "JavaScript"),
    ("go", "Go"),
    ("rs", "Rust"),
    ("ts", "TypeScript"),
]


class ContactForm(forms.Form):
    """A contact form with a mix of standard and custom widgets."""

    # Standard widgets — auto-styled by formwork CSS
    name = forms.CharField(
        max_length=100,
        help_text="Your full name.",
    )
    email = forms.EmailField(
        help_text="We'll never share your email.",
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="What's on your mind?",
    )

    # Custom widgets
    password = forms.CharField(
        widget=PasswordReveal,
        help_text="Password with show/hide toggle.",
    )
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        widget=SearchSelect,
        help_text="Searchable single-select dropdown.",
    )
    languages = forms.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=MultiSelect,
        required=False,
        help_text="Multi-select with checkboxes.",
    )
    tags = forms.CharField(
        widget=ComboBox(suggestions=["django", "htmx", "alpine", "tailwind", "daisyui"]),
        required=False,
        help_text="Free text with autocomplete suggestions.",
    )
    browser = forms.CharField(
        widget=DataList(datalist=["Chrome", "Firefox", "Safari", "Edge"]),
        required=False,
        help_text="Native browser datalist.",
    )
    volume = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100", "step": "10"}),
        initial=50,
        help_text="Range slider.",
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        help_text="Star rating.",
    )
    dark_mode = forms.BooleanField(
        widget=Toggle,
        required=False,
        help_text="Toggle switch.",
    )
    agree = forms.BooleanField(
        help_text="You must agree to continue.",
    )
