"""Forms for the task manager example."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.utils.html import format_html

from django_formwork import ChoiceLabel, FormworkForm, FormworkModelForm
from django_formwork.widgets import (
    ComboBox,
    DatePicker,
    DateTimePicker,
    FileDropzoneInput,
    ImageDropzoneInput,
    OTPInput,
    PasswordInput,
    Range,
    Rating,
    Select,
    SelectMultiple,
    ToggleInput,
    ValidatedTextarea,
)

from .models import Activity, Member, Profile, Tag, Task
from .widgets import PhoneInput

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

# Lifecycle ramp minus neutral, which reads as an unstyled border on a select.
STATUS_SELECT_COLORS: dict[str, str] = {
    Task.Status.TODO: "info",
    Task.Status.IN_PROGRESS: "primary",
    Task.Status.REVIEW: "accent",
    Task.Status.DONE: "success",
}

# Per-option trigger classes shared by the edit and details forms: the closed
# Select adopts the selected option's class (priority tinted soft by
# severity, status a solid select-{color} border on the lifecycle ramp).
PRIORITY_CHOICES = [
    (value, ChoiceLabel(label, selected_toggle_class=f"select-soft select-{Task.PRIORITY_COLORS[value]}"))
    for value, label in Task.Priority.choices
]
STATUS_CHOICES = [
    (value, ChoiceLabel(label, selected_toggle_class=f"select-{STATUS_SELECT_COLORS[value]}"))
    for value, label in Task.Status.choices
]


def search_members(_request: HttpRequest) -> QuerySet[Member]:
    """The rows the assignee search offers."""
    return Member.objects.all()


def search_tags(_request: HttpRequest) -> QuerySet[Tag]:
    """The rows the tag search offers."""
    return Tag.objects.all()


class MemberChoiceField(forms.ModelChoiceField):
    """A member with an initials badge and an email line."""

    def label_from_instance(self, obj: Member) -> ChoiceLabel:
        return ChoiceLabel(
            obj.name,
            icon=format_html("<span class='badge badge-ghost badge-sm w-8'>{}</span>", obj.initials),
            description=obj.email,
        )


class TaskEditForm(FormworkModelForm):
    """The new and edit pages: every field of a task.

    The template lays the fields out in sections with ``as_field_group``.
    """

    status = forms.ChoiceField(choices=STATUS_CHOICES, initial=Task.Status.TODO, widget=Select)
    priority = forms.ChoiceField(choices=PRIORITY_CHOICES, initial=Task.Priority.MEDIUM, widget=Select)
    assignee = MemberChoiceField(
        queryset=Member.objects.all(),
        required=False,
        empty_label="Unassigned",
        widget=Select(search_fields=["name", "email"], search_queryset=search_members, search_decorator=None),
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=SelectMultiple(search_fields=["name"], search_queryset=search_tags, search_decorator=None),
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        empty_value=None,
        widget=Rating(allow_clear=True),
        required=False,
        help_text="How well the result turned out. Rate it after the task is done.",
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "tags",
            "due_date",
            "remind_at",
            "cover_image",
            "attachment",
            "rating",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": DatePicker,
            "remind_at": DateTimePicker,
            "cover_image": ImageDropzoneInput(max_size=5 * 1024 * 1024),
            "attachment": FileDropzoneInput(max_size=10 * 1024 * 1024),
        }
        help_texts = {
            "remind_at": "Shown on the task page.",
            "cover_image": "Shown at the top of the task page.",
            "attachment": "One file of any type, linked under the description.",
        }


class TaskDetailsForm(FormworkModelForm):
    """The task page's side column: a form that saves each change on its own."""

    status = forms.ChoiceField(choices=STATUS_CHOICES, widget=Select)
    priority = forms.ChoiceField(choices=PRIORITY_CHOICES, widget=Select)
    assignee = MemberChoiceField(
        queryset=Member.objects.all(),
        required=False,
        empty_label="Unassigned",
        widget=Select(search_fields=["name", "email"], search_queryset=search_members, search_decorator=None),
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=SelectMultiple(search_fields=["name"], search_queryset=search_tags, search_decorator=None),
    )

    class Meta:
        model = Task
        fields = ["status", "assignee", "due_date", "priority", "tags"]
        widgets = {"due_date": DatePicker}


class CommentForm(FormworkModelForm):
    class Meta:
        model = Activity
        fields = ["comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Ask a question or share an update"})}
        labels = {"comment": "Add a comment"}

    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()
        if not comment:
            raise forms.ValidationError("Write a comment first.")
        return comment


class TaskDoneForm(forms.Form):
    """My work's tick box. Ticked marks the task done, unticked opens it again."""

    done = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "checkbox-sm checkbox-primary"}),
    )

    def __init__(self, *args, task: Task, **kwargs):
        kwargs.setdefault("initial", {"done": task.status == Task.Status.DONE})
        super().__init__(*args, auto_id=f"done-{task.pk}-%s", **kwargs)
        self.fields["done"].label = f"Done: {task.title}"


class QuickAddForm(FormworkForm):
    """My work's quick add: a title and an optional due date, for a task of your own."""

    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"placeholder": "What needs doing?"}))
    due_date = forms.DateField(widget=DatePicker, required=False)


class BoardAddForm(forms.ModelForm):
    """A board column's add field: the title, and the column's status in a hidden input."""

    class Meta:
        model = Task
        fields = ["title", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"enterkeyhint": "done", "autocomplete": "off"}),
            "status": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        # Each column has its own form, so the ids carry the column's status.
        status = kwargs.get("initial", {}).get("status", "")
        super().__init__(*args, auto_id=f"add-{status}-%s", **kwargs)


class BoardMoveForm(forms.Form):
    """A card dropped on a column."""

    task = forms.ModelChoiceField(queryset=Task.objects.all(), widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=Task.Status.choices, widget=forms.HiddenInput)


# --- Wizard ----------------------------------------------------------------


class WizardProjectForm(FormworkForm):
    """Step 1: project basics."""

    project_name = forms.CharField(max_length=100, help_text="Short and easy to find on the board.")
    project_description = forms.CharField(
        widget=ValidatedTextarea(attrs={"rows": 3}),
        required=False,
        help_text="A sentence or two about what the project is for.",
    )


class WizardConfigForm(FormworkForm):
    """Step 2: configuration."""

    enable_notifications = forms.BooleanField(
        widget=ToggleInput,
        required=False,
        initial=True,
        help_text="An email when a task in the project changes.",
    )
    max_tasks = forms.IntegerField(
        widget=Range(attrs={"min": "1", "max": "100", "step": "1"}),
        initial=20,
        help_text="The most open tasks the project can have at a time.",
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
        widget=SelectMultiple(search_fields=["name"], search_queryset=search_tags, search_decorator=None),
        label="Tags",
    )


# --- Settings (showcase remaining widgets) ---------------------------------


class SettingsForm(FormworkModelForm):
    """Account settings, persisted on the demo's single Profile row.

    The template lays the fields out in sections with ``as_field_group``.
    The password and 2FA fields show their widgets only and are never stored.
    """

    country = forms.ChoiceField(
        choices=[("", ""), *Profile.Country.choices],
        widget=Select(),
        required=False,
    )
    new_password = forms.CharField(
        widget=PasswordInput,
        required=False,
        help_text=(
            "Leave it empty to keep your current password. Use at least 12 characters, and not a "
            "password from another site: a few unrelated words are easy to remember and hard to guess."
        ),
    )
    two_factor_code = forms.CharField(
        label="Authenticator code",
        widget=OTPInput(length=6),
        required=False,
        help_text="The six digits your authenticator app shows for Taskwork.",
    )
    satisfaction = forms.TypedChoiceField(
        label="How do you like Taskwork?",
        choices=Rating.make_choices(5),
        coerce=int,
        empty_value=None,
        widget=Rating(allow_clear=True),
        required=False,
    )

    class Meta:
        model = Profile
        fields = ["full_name", "email", "member", "phone", "country", "avatar", "favourite_food", "satisfaction"]
        field_classes = {"member": MemberChoiceField}
        widgets = {
            "member": Select(
                search_fields=["name", "email"],
                search_queryset=search_members,
                search_decorator=None,
                attrs={"placeholder": "Pick yourself"},
            ),
            "phone": PhoneInput,
            "avatar": ImageDropzoneInput(max_size=2 * 1024 * 1024),
            "favourite_food": ComboBox(
                suggestions=["Pizza", "Pasta", "Sushi", "Tacos", "Curry", "Ramen", "Salad"],
            ),
        }
        help_texts = {
            "avatar": (
                "Shown next to your name in the top bar. It is small there, so a close-up of a face "
                "works better than a wide shot."
            ),
            "favourite_food": "For the team lunch. Type to see suggestions.",
        }
