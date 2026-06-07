"""Example form demonstrating standard and custom formwork widgets."""

from django import forms
from django.utils.html import format_html

from django_formwork.fields import FormworkModelChoiceField
from django_formwork.forms import FormworkForm, FormworkModelForm
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

from .models import PRIORITY_CHOICES, Person, Ticket

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


def _assignee_icon(person: Person) -> str:
    """Small initials badge shown beside each assignee in the dropdown.

    Single-quoted attributes so the markup nests cleanly inside the widget's
    double-quoted ``data-icon="..."`` attribute.
    """
    initials = "".join(part[0] for part in person.name.split()[:2]).upper()
    return format_html("<span class='badge badge-neutral badge-sm'>{}</span>", initials)


# Step 1: the simplest possible form.
class TicketTitleForm(forms.Form):
    title = forms.CharField(max_length=200, help_text="A short summary of the ticket.")


# Step 2: a searchable assignee dropdown with icons and descriptions.
class TicketWidgetsForm(FormworkForm):
    title = forms.CharField(max_length=200)
    assignee = FormworkModelChoiceField(
        queryset=Person.objects.all(),
        widget=SearchSelect(search_fields=["name", "email"], search_decorator=None),
        icon_from_instance=_assignee_icon,
        description_from_instance=lambda person: person.email,
        required=False,
        help_text="Type to search people by name or email.",
    )
    priority = forms.ChoiceField(choices=PRIORITY_CHOICES)


# Step 3: a server-side validation rule that morphs back into the form.
class TicketValidatedForm(TicketWidgetsForm):
    def clean_title(self):
        title = self.cleaned_data["title"]
        if Ticket.objects.filter(title__iexact=title).exists():
            raise forms.ValidationError("A ticket with this title already exists.")
        return title


# Step 4: editing an existing ticket, skipping validation on unchanged fields.
class TicketEditForm(FormworkModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "assignee", "priority", "description"]
        validate_dirty_only = True
