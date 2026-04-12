"""Forms for the task manager example."""

from django import forms

from django_formwork.widgets import ComboBox, Range, SearchSelect, Toggle

from .models import Task

TAG_SUGGESTIONS = ["bug", "feature", "docs", "refactor", "test", "design", "devops", "security"]


class TaskForm(forms.ModelForm):
    """Form for creating/editing a task — uses custom widgets."""

    tags = forms.CharField(
        widget=ComboBox(suggestions=TAG_SUGGESTIONS, multiple=True),
        required=False,
        help_text="Comma-separated tags.",
    )

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "status", "assignee", "tags", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "priority": SearchSelect(
                choices=Task.PRIORITY_CHOICES,
            ),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }


class TaskFilterForm(forms.Form):
    """Filter form for the task list — htmx-driven search."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search tasks..."}),
        label="",
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses")] + Task.STATUS_CHOICES,
        required=False,
    )
    priority = forms.ChoiceField(
        choices=[("", "All priorities")] + Task.PRIORITY_CHOICES,
        required=False,
    )


# --- Wizard forms (multi-step project creation) ---


class WizardStep1Form(forms.Form):
    """Step 1: Project basics."""

    project_name = forms.CharField(max_length=100, help_text="Name of the project.")
    project_description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Brief description.",
    )


class WizardStep2Form(forms.Form):
    """Step 2: Configuration."""

    enable_notifications = forms.BooleanField(
        widget=Toggle,
        required=False,
        help_text="Send email notifications for updates.",
    )
    max_tasks = forms.IntegerField(
        widget=Range(attrs={"min": "1", "max": "100", "step": "1"}),
        initial=20,
        help_text="Maximum number of tasks.",
    )
    visibility = forms.ChoiceField(
        choices=[("private", "Private"), ("team", "Team"), ("public", "Public")],
        widget=forms.RadioSelect,
        help_text="Who can see this project.",
    )


class WizardStep3Form(forms.Form):
    """Step 3: Initial tasks."""

    first_task = forms.CharField(
        max_length=200,
        help_text="Create the first task for this project.",
    )
    first_task_priority = forms.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        widget=SearchSelect(choices=Task.PRIORITY_CHOICES),
        help_text="Priority of the first task.",
    )
    first_task_tags = forms.CharField(
        widget=ComboBox(suggestions=TAG_SUGGESTIONS, multiple=True),
        required=False,
        help_text="Tags for the first task.",
    )
