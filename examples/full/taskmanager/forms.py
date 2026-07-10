"""Forms for the task manager example."""

from __future__ import annotations

from django import forms

from django_formwork import FormworkForm, FormworkModelForm
from django_formwork.widgets import (
    ComboBox,
    DatePicker,
    FileDropZone,
    ImageDropZone,
    MultiSelect,
    OTPInput,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
    Toggle,
    ValidatedTextarea,
)

from .models import Tag, Task
from .widgets import PhoneInput

# Demo country list; real projects supply their own (or use django-countries).
_COUNTRY_CHOICES = [
    ("", ""),
    ("us", "🇺🇸 United States"),
    ("gb", "🇬🇧 United Kingdom"),
    ("de", "🇩🇪 Germany"),
    ("fr", "🇫🇷 France"),
    ("es", "🇪🇸 Spain"),
    ("it", "🇮🇹 Italy"),
    ("nl", "🇳🇱 Netherlands"),
    ("se", "🇸🇪 Sweden"),
    ("pl", "🇵🇱 Poland"),
    ("ca", "🇨🇦 Canada"),
    ("br", "🇧🇷 Brazil"),
    ("mx", "🇲🇽 Mexico"),
    ("jp", "🇯🇵 Japan"),
    ("kr", "🇰🇷 South Korea"),
    ("cn", "🇨🇳 China"),
    ("in", "🇮🇳 India"),
    ("au", "🇦🇺 Australia"),
    ("za", "🇿🇦 South Africa"),
    ("ng", "🇳🇬 Nigeria"),
]


class TaskForm(FormworkModelForm):
    """CRUD form for a task. Demonstrates SearchSelect + MultiSelect (model-backed,
    auto-wired server search) + DatePicker + ImageDropZone + FileDropZone + Rating.
    """

    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=MultiSelect(search_fields=["name"], search_decorator=None),
    )

    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating(allow_clear=True),
        required=False,
        help_text="Quality rating (after completion).",
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "priority",
            "status",
            "assignee",
            "tags",
            "due_date",
            "cover_image",
            "attachment",
            "rating",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "priority": SearchSelect(choices=Task.PRIORITY_CHOICES),
            "status": SearchSelect(choices=Task.STATUS_CHOICES),
            "due_date": DatePicker,
            "cover_image": ImageDropZone(max_size=5 * 1024 * 1024),
            "attachment": FileDropZone(max_size=10 * 1024 * 1024),
        }


class TaskStatusForm(forms.ModelForm):
    """Single-field form for the htmx inline status edit on the list."""

    class Meta:
        model = Task
        fields = ["status"]


class TaskQuickAddForm(forms.Form):
    """One-line dashboard quick-add — title + priority."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "What needs doing?"}),
    )
    priority = forms.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        widget=SearchSelect(choices=Task.PRIORITY_CHOICES),
        initial="medium",
    )


class TaskFilterForm(forms.Form):
    """Filter bar above the task list."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search…"}),
        label="",
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses"), *Task.STATUS_CHOICES],
        required=False,
        label="",
    )
    priority = forms.ChoiceField(
        choices=[("", "All priorities"), *Task.PRIORITY_CHOICES],
        required=False,
        label="",
    )


# --- Wizard ----------------------------------------------------------------


class WizardProjectForm(FormworkForm):
    """Step 1 — project basics."""

    project_name = forms.CharField(max_length=100, help_text="Pick something memorable.")
    project_description = forms.CharField(
        widget=ValidatedTextarea(attrs={"rows": 3}),
        required=False,
        help_text="Optional summary.",
    )


class WizardConfigForm(FormworkForm):
    """Step 2 — configuration."""

    enable_notifications = forms.BooleanField(
        widget=Toggle,
        required=False,
        initial=True,
        help_text="Email updates when tasks change.",
    )
    max_tasks = forms.IntegerField(
        widget=Range(attrs={"min": "1", "max": "100", "step": "1"}),
        initial=20,
        help_text="Cap on total open tasks.",
    )
    visibility = forms.ChoiceField(
        choices=[("private", "Private"), ("team", "Team"), ("public", "Public")],
        widget=forms.RadioSelect,
        initial="team",
        help_text="Who can see this project.",
    )


class WizardFirstTaskForm(FormworkForm):
    """Step 3 — kick off with one task."""

    first_task = forms.CharField(max_length=200, label="Title")
    first_task_priority = forms.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        widget=SearchSelect(choices=Task.PRIORITY_CHOICES),
        initial="medium",
        label="Priority",
    )
    first_task_due = forms.DateField(widget=DatePicker, required=False, label="Due date")
    first_task_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=MultiSelect(search_fields=["name"], search_decorator=None),
        label="Tags",
    )


# --- Settings (showcase remaining widgets) ---------------------------------


class SettingsForm(FormworkForm):
    """Faux account settings — exercises the widgets the task domain doesn't."""

    full_name = forms.CharField(max_length=100, initial="Devon Vega")
    email = forms.EmailField(initial="devon@example.com")
    phone = forms.CharField(widget=PhoneInput, required=False, help_text="Country code + number.")
    country = forms.ChoiceField(
        choices=_COUNTRY_CHOICES,
        widget=SearchSelect(),
        required=False,
        help_text="Where you're based.",
    )
    avatar = forms.ImageField(
        widget=ImageDropZone(max_size=2 * 1024 * 1024),
        required=False,
        help_text="Square-ish PNG or JPG, ≤2 MB.",
    )
    new_password = forms.CharField(
        widget=PasswordReveal,
        required=False,
        help_text="Leave blank to keep current.",
    )
    two_factor_code = forms.CharField(
        widget=OTPInput(length=6),
        required=False,
        help_text="Six-digit code from your authenticator.",
    )
    favourite_food = forms.CharField(
        widget=ComboBox(suggestions=["Pizza", "Pasta", "Sushi", "Tacos", "Curry", "Ramen", "Salad"]),
        required=False,
        help_text="Autocompletes as you type.",
    )
    satisfaction = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        required=False,
        help_text="How are we doing?",
    )
