"""Views for the task manager example."""

from __future__ import annotations

from datetime import timedelta
from operator import attrgetter

from django.contrib import messages
from django.db.models import Count, DateField, F, Q
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .filters import TaskFilter
from .forms import (
    BoardAddForm,
    BoardMoveForm,
    CommentForm,
    QuickAddForm,
    SettingsForm,
    TaskDetailsForm,
    TaskDoneForm,
    TaskEditForm,
    WizardConfigForm,
    WizardFirstTaskForm,
    WizardProjectForm,
)
from .models import Activity, Member, Profile, Task

# The board shows this many of the latest done tasks; the admin lists the rest.
DONE_ON_BOARD = 8


def with_comment_count(tasks):
    return tasks.annotate(comment_count=Count("activity", filter=~Q(activity__comment="")))


def set_status(task: Task, status: str, author: Member | None) -> None:
    """Move a task and note the move in its activity."""
    if task.status == status:
        return
    task.status = status
    task.save(update_fields=["status", "updated_at"])
    Activity.objects.create(task=task, author=author, field="Status", value=task.get_status_display())


# ─── My work ────────────────────────────────────────────────────────────


def dashboard(request):
    """Your open tasks by due date, what you finished this week, and the team's latest activity."""
    me = Profile.load().member
    if request.method == "POST":
        form = QuickAddForm(request.POST)
        if form.is_valid():
            Task.objects.create(assignee=me, **form.cleaned_data)
            return redirect("dashboard")
    else:
        form = QuickAddForm()

    today = timezone.localdate()
    mine = with_comment_count(Task.objects.filter(assignee=me) if me else Task.objects.none())
    open_tasks = list(mine.exclude(status=Task.Status.DONE).prefetch_related("tags").order_by("due_date", "-id"))
    week_end = today + timedelta(days=7)
    groups = [
        ("overdue", "Overdue", [t for t in open_tasks if t.due_date and t.due_date < today]),
        ("week", "Due this week", [t for t in open_tasks if t.due_date and today <= t.due_date < week_end]),
        ("later", "Later", [t for t in open_tasks if not t.due_date or t.due_date >= week_end]),
    ]
    done = list(
        mine.filter(status=Task.Status.DONE, updated_at__gte=timezone.now() - timedelta(days=7))
        .prefetch_related("tags")
        .order_by("-updated_at")
    )
    for task in [*open_tasks, *done]:
        task.done_form = TaskDoneForm(task=task)
    return render(
        request,
        "dashboard.html",
        {
            "me": me,
            "form": form,
            "groups": groups,
            "done": done,
            "open_count": len(open_tasks),
            "feed": Activity.objects.select_related("author", "task").order_by("-created_at")[:6],
            "today": today,
        },
    )


@require_POST
def task_done(request, pk):
    """Tick a task off on My work, or untick it to reopen it."""
    task = get_object_or_404(Task, pk=pk)
    form = TaskDoneForm(request.POST, task=task)
    if form.is_valid():
        status = Task.Status.DONE if form.cleaned_data["done"] else Task.Status.TODO
        set_status(task, status, Profile.load().member)
    return redirect("dashboard")


# ─── Board ──────────────────────────────────────────────────────────────


def board(request):
    """Tasks in one column per status, your own first in each."""
    me = Profile.load().member
    task_filter = TaskFilter(
        request.GET, queryset=with_comment_count(Task.objects.select_related("assignee").prefetch_related("tags"))
    )
    tasks = task_filter.qs.order_by(F("due_date").asc(nulls_last=True), "-pk")
    columns = []
    for status in Task.Status:
        cards = shown = [t for t in tasks if t.status == status]
        if status == Task.Status.DONE:
            shown = sorted(cards, key=attrgetter("updated_at"), reverse=True)[:DONE_ON_BOARD]
        columns.append(
            {
                "status": status,
                "color": Task.STATUS_COLORS[status],
                "count": len(cards),
                "mine": [t for t in shown if me and t.assignee_id == me.pk],
                "others": [t for t in shown if not me or t.assignee_id != me.pk],
                "hidden": len(cards) - len(shown),
                "add_form": BoardAddForm(initial={"status": status}),
            }
        )
    return render(
        request,
        "tasks/board.html",
        {"filter": task_filter, "columns": columns, "me": me, "move_form": BoardMoveForm()},
    )


def back_to_board(request):
    """The board with the filters of the page that posted."""
    query = request.GET.urlencode()
    return redirect(f"{reverse('board')}?{query}" if query else reverse("board"))


@require_POST
def board_add(request):
    """Add a task to a column from its title field. The task is yours."""
    form = BoardAddForm(request.POST)
    if form.is_valid():
        form.instance.assignee = Profile.load().member
        form.save()
    return back_to_board(request)


@require_POST
def board_move(request):
    """Move a task that was dropped on another column."""
    form = BoardMoveForm(request.POST)
    if form.is_valid():
        set_status(form.cleaned_data["task"], form.cleaned_data["status"], Profile.load().member)
    return back_to_board(request)


# ─── Task page ──────────────────────────────────────────────────────────


def field_text(task: Task, name: str) -> str:
    """A field's value as the activity shows it."""
    field = task._meta.get_field(name)  # noqa: SLF001
    if field.choices:
        return getattr(task, f"get_{name}_display")()
    value = getattr(task, name)
    if field.many_to_many:
        return ", ".join(str(obj) for obj in value.all())
    if value is None:
        return ""
    return date_format(value, "M j, Y") if isinstance(field, DateField) else str(value)


def task_detail(request, pk):
    """Read a task and its activity. The side column saves each change on its own."""
    task = get_object_or_404(Task.objects.select_related("assignee"), pk=pk)
    details = TaskDetailsForm(request.POST if request.method == "POST" else None, instance=task)
    changed = []
    if details.is_bound and details.is_valid():
        changed = details.changed_data
        details.save()
        me = Profile.load().member
        Activity.objects.bulk_create(
            Activity(task=task, author=me, field=details[name].label, value=field_text(task, name)) for name in changed
        )
    response = task_page(request, task, details=details)
    if changed:
        # The activity list reloads itself on this event.
        response["HX-Trigger"] = "task-changed"
    return response


def task_page(request, task, *, details=None, comment_form=None):
    return render(
        request,
        "tasks/detail.html",
        {
            "task": task,
            "details": TaskDetailsForm(instance=task) if details is None else details,
            "comment_form": CommentForm() if comment_form is None else comment_form,
            "activity": task.activity.select_related("author"),
            "me": Profile.load().member,
        },
    )


@require_POST
def task_comment(request, pk):
    task = get_object_or_404(Task, pk=pk)
    form = CommentForm(request.POST)
    if not form.is_valid():
        return task_page(request, task, comment_form=form)
    form.instance.task = task
    form.instance.author = Profile.load().member
    form.save()
    return redirect(task)


def task_create(request):
    """The full form, with every field of a task."""
    if request.method == "POST":
        form = TaskEditForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save()
            messages.success(request, "Task created.")
            return redirect(task)
    else:
        form = TaskEditForm(initial={"assignee": Profile.load().member})
    return render(request, "tasks/form.html", {"form": form, "task": None})


def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskEditForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task saved.")
            return redirect(task)
    else:
        form = TaskEditForm(instance=task)
    return render(request, "tasks/form.html", {"form": form, "task": task})


def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task.delete()
        messages.success(request, f"Task deleted: {task.title}")
        return redirect("board")
    return render(request, "tasks/confirm_delete.html", {"task": task, "activity_count": task.activity.count()})


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
            submitted = request.POST.copy()
            submitted.pop("csrfmiddlewaretoken", None)
            submitted.pop("step", None)
            data[str(step)] = submitted.urlencode()
            request.session["wizard_data"] = data
            return redirect(f"{request.path}?step={step + 1}")
        return render(request, "wizard/page.html", _wizard_ctx(step, form, data))

    if step == len(WIZARD_FORMS):  # Review page
        return render(request, "wizard/review.html", _wizard_ctx(step, None, data))

    return render(request, "wizard/page.html", _wizard_ctx(step, _wizard_form(step, data), data))


def wizard_confirm(request):
    """Finalise the wizard: create the project task and clear session."""
    if request.method != "POST":
        return redirect("wizard")
    data = request.session.get("wizard_data", {})
    project = _wizard_cleaned(0, data)
    first_task_data = _wizard_cleaned(2, data)

    task = Task.objects.create(
        title=first_task_data.get("first_task", "Untitled"),
        priority=first_task_data.get("first_task_priority", Task.Priority.MEDIUM),
        description=f"Project: {project.get('project_name', 'Unnamed')}",
        due_date=first_task_data.get("first_task_due"),
    )
    if first_task_data.get("first_task_tags"):
        task.tags.set(first_task_data["first_task_tags"])

    request.session.pop("wizard_data", None)
    messages.success(request, f"Project '{project.get('project_name')}' created.")
    return redirect(task)


def _wizard_form(step, data):
    """Rebuild a step's form from the raw submitted data stored in the session."""
    stored = data.get(str(step))
    if stored is None:
        return WIZARD_FORMS[step]()
    return WIZARD_FORMS[step](QueryDict(stored))


def _wizard_cleaned(step, data):
    form = _wizard_form(step, data)
    return form.cleaned_data if form.is_bound and form.is_valid() else {}


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
        "review_data": _wizard_summary(data) if step == len(WIZARD_FORMS) else None,
    }


def _wizard_summary(data):
    project = _wizard_cleaned(0, data)
    config = _wizard_cleaned(1, data)
    first_task_data = _wizard_cleaned(2, data)
    tags_list = list(first_task_data.get("first_task_tags") or [])
    due = first_task_data.get("first_task_due")
    return [
        (
            "Project",
            [
                ("Name", project.get("project_name", "")),
                ("Description", project.get("project_description") or "None"),
            ],
        ),
        (
            "Configuration",
            [
                ("Notifications", "On" if config.get("enable_notifications") else "Off"),
                ("Max tasks", config.get("max_tasks", "None")),
                ("Visibility", (config.get("visibility") or "").title() or "None"),
            ],
        ),
        (
            "First task",
            [
                ("Title", first_task_data.get("first_task", "")),
                ("Priority", (first_task_data.get("first_task_priority") or "").title()),
                ("Due date", date_format(due, "M j, Y") if due else "None"),
                ("Tags", ", ".join(t.name for t in tags_list) or "None"),
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
