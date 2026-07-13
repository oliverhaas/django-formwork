"""Views for the task manager example."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    SettingsForm,
    TaskFilterForm,
    TaskForm,
    TaskQuickAddForm,
    WizardConfigForm,
    WizardFirstTaskForm,
    WizardProjectForm,
)
from .models import Profile, Tag, Task

# Fields editable per-cell in list rows (_list_row.html); task_status() disables the rest.
ROW_EDITABLE_FIELDS = {"status", "priority", "assignee", "due_date", "tags"}

# ─── Dashboard ──────────────────────────────────────────────────────────


def dashboard(request):
    """Stats cards, recent activity, and a quick-add form."""
    qs = Task.objects.all()
    by_status = dict(qs.values_list("status").annotate(n=Count("id")))
    status_icons = {
        Task.Status.TODO: "icon-circle-dashed",
        Task.Status.IN_PROGRESS: "icon-loader",
        Task.Status.REVIEW: "icon-eye",
        Task.Status.DONE: "icon-check",
    }
    stats_data = [
        {
            "key": status,
            "label": status.label,
            "icon": status_icons[status],
            "count": by_status.get(status, 0),
        }
        for status in Task.Status
    ]
    recent = qs.prefetch_related("assignee").order_by("-updated_at")[:8]

    if request.method == "POST":
        form = TaskQuickAddForm(request.POST)
        if form.is_valid():
            Task.objects.create(
                title=form.cleaned_data["title"],
                priority=form.cleaned_data["priority"],
            )
            messages.success(request, "Task added.")
            return redirect("dashboard")
    else:
        form = TaskQuickAddForm()

    return render(
        request,
        "dashboard.html",
        {
            "stats": stats_data,
            "total": qs.count(),
            "recent": recent,
            "form": form,
            "now": timezone.now(),
        },
    )


# ─── Tasks ──────────────────────────────────────────────────────────────


def task_list(request):
    """List tasks with htmx search/filter."""
    form = TaskFilterForm(request.GET)
    tasks = Task.objects.prefetch_related("tags", "assignee")

    if form.is_valid():
        q = form.cleaned_data.get("q")
        status = form.cleaned_data.get("status")
        priority = form.cleaned_data.get("priority")
        if q:
            tasks = tasks.filter(Q(title__icontains=q) | Q(tags__name__icontains=q)).distinct()
        if status:
            tasks = tasks.filter(status=status)
        if priority:
            tasks = tasks.filter(priority=priority)

    tasks = list(tasks)
    for t in tasks:
        t.row_form = TaskForm(instance=t, editable_fields=ROW_EDITABLE_FIELDS, auto_id=f"id_row_{t.pk}_%s")

    if request.headers.get("HX-Request") == "true":
        return render(request, "tasks/_list_rows.html", {"tasks": tasks})
    return render(request, "tasks/list.html", {"tasks": tasks, "filter_form": form})


def task_create(request):
    """Create a new task."""
    if request.method == "POST":
        form = TaskForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Task created.")
            return redirect("task_list")
    else:
        form = TaskForm()
    return render(request, "tasks/form.html", {"form": form, "title": "New task", "task": None})


def task_edit(request, pk):
    """Edit an existing task."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated.")
            return redirect("task_list")
    else:
        form = TaskForm(instance=task)
    return render(request, "tasks/form.html", {"form": form, "title": task.title, "task": task})


def task_delete(request, pk):
    """Delete a task."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task.delete()
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(status=200, headers={"HX-Redirect": "/tasks/"})
        return redirect("task_list")
    return render(request, "tasks/confirm_delete.html", {"task": task})


def task_status(request, pk):
    """Inline row edit via htmx: saves only the field named by the posted "field" marker."""
    task = get_object_or_404(Task, pk=pk)
    field = request.POST.get("field")
    editable = [field] if field in ROW_EDITABLE_FIELDS else []
    save_form = TaskForm(request.POST, instance=task, editable_fields=editable, auto_id=f"id_row_{task.pk}_%s")
    if save_form.is_valid():
        save_form.save()
    task.row_form = TaskForm(instance=task, editable_fields=ROW_EDITABLE_FIELDS, auto_id=f"id_row_{task.pk}_%s")
    return render(request, "tasks/_list_row.html", {"task": task})


# ─── Wizard ─────────────────────────────────────────────────────────────

WIZARD_FORMS = [WizardProjectForm, WizardConfigForm, WizardFirstTaskForm]
WIZARD_TITLES = ["Project", "Configuration", "First task"]


def wizard(request):
    """Multi-step project creation wizard backed by session storage."""
    step = int(request.GET.get("step", request.POST.get("step", 0)))
    step = max(0, min(step, len(WIZARD_FORMS)))

    data = request.session.get("wizard_data", {})

    if request.method == "POST" and step < len(WIZARD_FORMS):
        form = WIZARD_FORMS[step](request.POST)
        if form.is_valid():
            data[str(step)] = form.cleaned_data
            request.session["wizard_data"] = data
            return redirect(f"{request.path}?step={step + 1}")
        return render(request, "wizard/page.html", _wizard_ctx(step, form, data))

    if step == len(WIZARD_FORMS):  # Review page
        return render(request, "wizard/review.html", _wizard_ctx(step, None, data))

    initial = data.get(str(step), {})
    form = WIZARD_FORMS[step](initial=initial)
    return render(request, "wizard/page.html", _wizard_ctx(step, form, data))


def wizard_confirm(request):
    """Finalise the wizard: create the project task and clear session."""
    if request.method != "POST":
        return redirect("wizard")
    data = request.session.get("wizard_data", {})
    project = data.get("0", {})
    first = data.get("2", {})

    task = Task.objects.create(
        title=first.get("first_task", "Untitled"),
        priority=first.get("first_task_priority", Task.Priority.MEDIUM),
        description=f"Project: {project.get('project_name', 'Unnamed')}",
        due_date=first.get("first_task_due"),
    )
    if first.get("first_task_tags"):
        task.tags.set(first["first_task_tags"])

    request.session.pop("wizard_data", None)
    messages.success(request, f"Project '{project.get('project_name')}' created.")
    return redirect("task_edit", pk=task.pk)


def _wizard_ctx(step, form, data):
    total = len(WIZARD_FORMS) + 1  # forms + review
    return {
        "form": form,
        "step": step,
        "step_index": step + 1,
        "step_title": WIZARD_TITLES[step] if step < len(WIZARD_FORMS) else "Review",
        "step_titles": [*WIZARD_TITLES, "Review"],
        "total_steps": total,
        "is_review": step == len(WIZARD_FORMS),
        "has_prev": step > 0,
        "wizard_data": data,
        "review_data": _wizard_summary(data) if step == len(WIZARD_FORMS) else None,
    }


def _wizard_summary(data):
    project = data.get("0", {})
    config = data.get("1", {})
    first = data.get("2", {})
    tags = first.get("first_task_tags") or []
    if hasattr(tags, "all"):
        tags_list = list(tags)
    else:
        tags_list = [Tag.objects.filter(pk=t).first() for t in tags]
    tags_list = [t for t in tags_list if t]
    return [
        (
            "Project",
            [
                ("Name", project.get("project_name", "")),
                ("Description", project.get("project_description", "") or "—"),
            ],
        ),
        (
            "Configuration",
            [
                ("Notifications", "On" if config.get("enable_notifications") else "Off"),
                ("Max tasks", config.get("max_tasks", "—")),
                ("Visibility", (config.get("visibility") or "").title() or "—"),
            ],
        ),
        (
            "First task",
            [
                ("Title", first.get("first_task", "")),
                ("Priority", (first.get("first_task_priority") or "").title()),
                ("Due", first.get("first_task_due") or "—"),
                ("Tags", ", ".join(t.name for t in tags_list) or "—"),
            ],
        ),
    ]


# ─── Settings ───────────────────────────────────────────────────────────


def settings_page(request):
    """Account settings, persisted on the demo's single Profile row."""
    profile = Profile.load()
    if request.method == "POST":
        form = SettingsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
            return redirect("settings")
    else:
        form = SettingsForm(instance=profile)
    return render(request, "settings.html", {"form": form})
