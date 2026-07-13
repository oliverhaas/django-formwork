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


class TaskForm(FormworkModelForm):
    """CRUD form for a task. Demonstrates SearchSelect (static choices with
    selected_toggle_class, and model-backed auto-wired server search) +
    MultiSelect + DatePicker + ImageDropZone + FileDropZone + Rating.
    """

    priority = forms.ChoiceField(
        choices=[
            (
                value,
                ChoiceLabel(
                    label,
                    selected_toggle_class=f"select-soft select-{Task.PRIORITY_COLORS[value]}",
                ),
            )
            for value, label in Task.Priority.choices
        ],
        initial=Task.Priority.MEDIUM,
        widget=SearchSelect,
        help_text="SearchSelect whose closed trigger adopts each option's selected_toggle_class: "
        "select-soft tinted by severity, recoloring on pick without a round-trip.",
    )

    assignee = FormworkModelChoiceField(
        queryset=Member.objects.all(),
        required=False,
        empty_label="Unassigned",
        widget=SearchSelect(search_fields=["name", "email"], search_decorator=None),
        icon_from_instance=lambda member: format_html(
            "<span class='badge badge-neutral badge-sm w-8'>{}</span>", member.initials
        ),
        description_from_instance=lambda member: member.email,
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
            "status": "Plain native select (a four-option lifecycle doesn't need a fancy widget).",
            "due_date": "DatePicker with a calendar dropdown.",
            "cover_image": "Shown as a thumbnail in the task list (ImageDropZone, ≤5 MB).",
            "attachment": "Any single file (FileDropZone, ≤10 MB).",
        }

    # Ghost variants keep inline table cells text-like.
    ROW_WIDGET_CLASSES = {
        "status": "select-ghost",
        "assignee": "select-ghost",
        "tags": "select-ghost",
        "due_date": "input-ghost",
    }

    def __init__(self, *args, editable_fields=None, row=False, **kwargs):
        """``editable_fields``: iterable of field names left editable; every
        other field is marked ``disabled`` so its cleaned value always comes
        from the bound instance rather than POST data, regardless of what
        (if anything) was submitted for it. Lets the same form back a
        row's single-field inline edit (htmx) and the full edit page
        without risking clobbering fields the row doesn't render.

        ``row``: style widgets for inline table cells (ghost variants).
        """
        super().__init__(*args, **kwargs)
        if editable_fields is not None:
            for name, field in self.fields.items():
                if name not in editable_fields:
                    field.disabled = True
        if row:
            for name, css in self.ROW_WIDGET_CLASSES.items():
                attrs = self.fields[name].widget.attrs
                attrs["class"] = f"{attrs['class']} {css}".strip() if attrs.get("class") else css


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


class TaskFilterForm(forms.Form):
    """Filter bar above the task list."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search…"}),
        label="",
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses"), *Task.Status.choices],
        required=False,
        label="",
    )
    priority = forms.ChoiceField(
        choices=[("", "All priorities"), *Task.Priority.choices],
        required=False,
        label="",
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
