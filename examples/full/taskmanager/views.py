"""Views for the task manager example."""

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    TaskFilterForm,
    TaskForm,
    WizardStep1Form,
    WizardStep2Form,
    WizardStep3Form,
)
from .models import Task

# ─── CRUD ───────────────────────────────────────────────────────────────


def task_list(request):
    """List tasks with htmx search/filter."""
    form = TaskFilterForm(request.GET)
    tasks = Task.objects.all()

    if form.is_valid():
        q = form.cleaned_data.get("q")
        status = form.cleaned_data.get("status")
        priority = form.cleaned_data.get("priority")

        if q:
            tasks = tasks.filter(Q(title__icontains=q) | Q(tags__icontains=q))
        if status:
            tasks = tasks.filter(status=status)
        if priority:
            tasks = tasks.filter(priority=priority)

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return render(request, "tasks/task_list_partial.html", {"tasks": tasks})
    return render(request, "tasks/task_list.html", {"tasks": tasks, "filter_form": form})


def task_create(request):
    """Create a new task."""
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("task_list")
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return render(request, "tasks/task_form_partial.html", {"form": form})
    else:
        form = TaskForm()

    return render(request, "tasks/task_form.html", {"form": form, "title": "New Task"})


def task_edit(request, pk):
    """Edit an existing task."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect("task_list")
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return render(request, "tasks/task_form_partial.html", {"form": form})
    else:
        form = TaskForm(instance=task)

    return render(request, "tasks/task_form.html", {"form": form, "title": f"Edit: {task.title}"})


def task_delete(request, pk):
    """Delete a task (POST only)."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task.delete()
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(status=200, headers={"HX-Redirect": "/"})
        return redirect("task_list")
    return render(request, "tasks/task_confirm_delete.html", {"task": task})


# ─── Wizard ─────────────────────────────────────────────────────────────

WIZARD_FORMS = [WizardStep1Form, WizardStep2Form, WizardStep3Form]
WIZARD_TITLES = ["Project Basics", "Configuration", "Initial Task"]


def wizard(request):
    """Multi-step project creation wizard using session storage."""
    step = int(request.GET.get("step", request.POST.get("step", 0)))
    step = max(0, min(step, len(WIZARD_FORMS) - 1))

    wizard_data = request.session.get("wizard_data", {})

    if request.method == "POST":
        form = WIZARD_FORMS[step](request.POST)
        if form.is_valid():
            wizard_data[str(step)] = form.cleaned_data
            request.session["wizard_data"] = wizard_data

            if step < len(WIZARD_FORMS) - 1:
                # Advance to next step.
                next_step = step + 1
                next_form = WIZARD_FORMS[next_step](initial=wizard_data.get(str(next_step), {}))
                return render(
                    request,
                    "wizard/wizard.html",
                    _wizard_ctx(next_step, next_form, wizard_data),
                )
            # Final step — create the project.
            result = _finalize_wizard(wizard_data)
            request.session.pop("wizard_data", None)
            return render(request, "wizard/wizard_done.html", {"result": result})

        # Validation failed — re-render current step.
        is_htmx = request.headers.get("HX-Request") == "true"
        template = "wizard/wizard_form_partial.html" if is_htmx else "wizard/wizard.html"
        return render(request, template, _wizard_ctx(step, form, wizard_data))

    # GET — show the requested step.
    initial = wizard_data.get(str(step), {})
    form = WIZARD_FORMS[step](initial=initial)
    return render(request, "wizard/wizard.html", _wizard_ctx(step, form, wizard_data))


def _wizard_ctx(step, form, wizard_data):
    return {
        "form": form,
        "step": step,
        "step_title": WIZARD_TITLES[step],
        "total_steps": len(WIZARD_FORMS),
        "steps": [(i, WIZARD_TITLES[i], i <= step) for i in range(len(WIZARD_FORMS))],
        "has_prev": step > 0,
        "has_next": step < len(WIZARD_FORMS) - 1,
        "is_last": step == len(WIZARD_FORMS) - 1,
        "wizard_data": wizard_data,
    }


def _finalize_wizard(data):
    """Create a task from the wizard data."""
    step0 = data.get("0", {})
    step2 = data.get("2", {})
    task = Task.objects.create(
        title=step2.get("first_task", "Untitled"),
        priority=step2.get("first_task_priority", "medium"),
        tags=step2.get("first_task_tags", ""),
        description=f"Project: {step0.get('project_name', 'Unnamed')}",
    )
    return {
        "project_name": step0.get("project_name"),
        "task": task,
        "settings": data.get("1", {}),
    }
