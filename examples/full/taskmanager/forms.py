"""Forms for the task manager example."""

from __future__ import annotations

from django import forms
from django.utils.html import format_html

from django_formwork import ChoiceLabel, FormworkForm, FormworkModelChoiceField, FormworkModelForm
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

from .models import Member, Profile, Tag, Task
from .widgets import PhoneInput

# Lifecycle ramp minus neutral, which reads as an unstyled border on a select.
STATUS_SELECT_COLORS: dict[str, str] = {
    Task.Status.TODO: "info",
    Task.Status.IN_PROGRESS: "primary",
    Task.Status.REVIEW: "accent",
    Task.Status.DONE: "success",
}

# Per-option trigger classes shared by the edit and row forms: the closed
# SearchSelect adopts the selected option's class (priority tinted soft by
# severity, status a solid select-{color} border on the lifecycle ramp).
PRIORITY_CHOICES = [
    (value, ChoiceLabel(label, selected_toggle_class=f"select-soft select-{Task.PRIORITY_COLORS[value]}"))
    for value, label in Task.Priority.choices
]
STATUS_CHOICES = [
    (value, ChoiceLabel(label, selected_toggle_class=f"select-{STATUS_SELECT_COLORS[value]}"))
    for value, label in Task.Status.choices
]


class TaskEditForm(FormworkModelForm):
    """Full create/edit page: every task field, solid select-{color} status
    border. Showcases SearchSelect + MultiSelect + DatePicker + drop zones +
    Rating.
    """

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial=Task.Priority.MEDIUM,
        widget=SearchSelect,
        help_text="SearchSelect whose closed trigger adopts each option's selected_toggle_class: "
        "select-soft tinted by severity, recoloring on pick without a round-trip.",
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial=Task.Status.TODO,
        widget=SearchSelect,
        help_text="Same trick as priority, but a select-{color} border instead of a soft fill: "
        "solid here on the edit page, dotted in the inline list rows, recoloring on pick.",
    )
    assignee = FormworkModelChoiceField(
        queryset=Member.objects.all(),
        required=False,
        empty_label="Unassigned",
        widget=SearchSelect(search_fields=["name", "email"], search_decorator=None),
        icon_from_instance=lambda instance: format_html(
            "<span class='badge badge-ghost badge-sm w-8'>{}</span>", instance.initials
        ),
        description_from_instance=lambda instance: instance.email,
        help_text="SearchSelect over the Member model: server-side search, initials badge, email line.",
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=MultiSelect(search_fields=["name"], search_decorator=None),
        help_text="MultiSelect with server-side search over tag names.",
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        empty_value=None,
        widget=Rating(allow_clear=True),
        required=False,
        help_text="Quality rating after completion (clearable Rating stars).",
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
            "due_date": DatePicker,
            "cover_image": ImageDropZone(max_size=5 * 1024 * 1024),
            "attachment": FileDropZone(max_size=10 * 1024 * 1024),
        }
        help_texts = {
            "due_date": "DatePicker with a calendar dropdown.",
            "cover_image": "Shown as a thumbnail in the task list (ImageDropZone, ≤5 MB).",
            "attachment": "Any single file (FileDropZone, ≤10 MB).",
        }


class TaskRowForm(FormworkModelForm):
    """Inline autosaving list row: only the lifecycle columns, with widgets
    styled for table cells (ghost inputs, dotted status border). Fields the row
    doesn't render aren't on the form, so a row save can't touch them.
    """

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial=Task.Priority.MEDIUM,
        widget=SearchSelect,
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial=Task.Status.TODO,
        widget=SearchSelect(attrs={"class": "select-dotted"}),
    )
    assignee = FormworkModelChoiceField(
        queryset=Member.objects.all(),
        required=False,
        empty_label="Unassigned",
        widget=SearchSelect(
            search_fields=["name", "email"], search_decorator=None, attrs={"class": "select-ghost"}
        ),
        icon_from_instance=lambda instance: format_html(
            "<span class='badge badge-ghost badge-sm w-8'>{}</span>", instance.initials
        ),
        description_from_instance=lambda instance: instance.email,
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=MultiSelect(
            search_fields=["name"], search_decorator=None, attrs={"class": "select-ghost"}
        ),
    )

    class Meta:
        model = Task
        fields = ["status", "priority", "assignee", "tags", "due_date"]
        widgets = {"due_date": DatePicker(attrs={"class": "input-ghost"})}


class TaskQuickAddForm(forms.Form):
    """One-line dashboard quick-add: title + priority."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "What needs doing?"}),
    )
    priority = forms.ChoiceField(
        choices=Task.Priority.choices,
        initial=Task.Priority.MEDIUM,
    )


# --- Wizard ----------------------------------------------------------------


class WizardProjectForm(FormworkForm):
    """Step 1: project basics."""

    project_name = forms.CharField(max_length=100, help_text="Pick something memorable.")
    project_description = forms.CharField(
        widget=ValidatedTextarea(attrs={"rows": 3}),
        required=False,
        help_text="Optional summary.",
    )


class WizardConfigForm(FormworkForm):
    """Step 2: configuration."""

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
        help_text=(
            "Who can see this project. Private means only you, team shares it with "
            "everyone in your workspace, and public makes it readable by anyone with "
            "the link. You can change this later in the project settings."
        ),
    )


class WizardFirstTaskForm(FormworkForm):
    """Step 3: kick off with one task."""

    first_task = forms.CharField(max_length=200, label="Title")
    first_task_priority = forms.ChoiceField(
        choices=Task.Priority.choices,
        initial=Task.Priority.MEDIUM,
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


class SettingsForm(FormworkModelForm):
    """Account settings, persisted on the demo's single Profile row.

    Exercises the widgets the task domain doesn't. The password and 2FA
    fields are widget showcases only and are never stored.
    """

    country = forms.ChoiceField(
        choices=[("", ""), *Profile.Country.choices],
        widget=SearchSelect(),
        required=False,
        help_text="Where you're based.",
    )
    new_password = forms.CharField(
        widget=PasswordReveal,
        required=False,
        help_text=(
            "Leave blank to keep your current password. The eye button (PasswordReveal) "
            "shows what you typed. If you do change it, use at "
            "least 12 characters and avoid reusing a password from another site. A "
            "passphrase of a few unrelated words is easy to remember and hard to guess."
        ),
    )
    two_factor_code = forms.CharField(
        widget=OTPInput(length=6),
        required=False,
        help_text="Six-digit code from your authenticator (OTPInput).",
    )
    satisfaction = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        empty_value=None,
        widget=Rating(allow_clear=True),
        required=False,
        help_text="How are we doing? (five-star Rating widget)",
    )

    field_order = [
        "full_name",
        "email",
        "phone",
        "country",
        "avatar",
        "new_password",
        "two_factor_code",
        "favourite_food",
        "satisfaction",
    ]

    class Meta:
        model = Profile
        fields = ["full_name", "email", "phone", "country", "avatar", "favourite_food", "satisfaction"]
        widgets = {
            "phone": PhoneInput,
            "avatar": ImageDropZone(max_size=2 * 1024 * 1024),
            "favourite_food": ComboBox(
                suggestions=["Pizza", "Pasta", "Sushi", "Tacos", "Curry", "Ramen", "Salad"],
            ),
        }
        help_texts = {
            "phone": "Country code + number (custom PhoneInput multi-widget).",
            "avatar": (
                "Square-ish PNG or JPG, ≤2 MB (ImageDropZone). The picture is shown at small sizes "
                "throughout the app, so pick something that stays recognizable as a "
                "tiny thumbnail. A close-up works better than a wide shot."
            ),
            "favourite_food": "Autocompletes as you type (ComboBox with static suggestions).",
        }
