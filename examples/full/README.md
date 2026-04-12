# Full Example — Task Manager

A task management app demonstrating django-formwork's real-world usage: CRUD operations, search/filter, and a multi-step wizard.

## Run

```bash
cd examples/full
uv run --extra-with django-formwork manage.py migrate
uv run --extra-with django-formwork manage.py runserver
```

Open http://localhost:8000/ in your browser.

## Pages

- **/** — Task list with htmx-driven search and filter
- **/tasks/new/** — Create a task (CRUD form with custom widgets)
- **/tasks/\<id\>/edit/** — Edit a task with dirty-field highlighting
- **/wizard/** — Multi-step project creation wizard with progress indicator

## What it demonstrates

- **CRUD** — list, create, edit, delete with htmx morph transitions
- **Search/filter** — htmx-driven filtering with debounced input
- **Multi-step wizard** — session-backed form wizard with DaisyUI steps component
- **Custom widgets** — SearchSelect, ComboBox, Toggle, Range, RadioSelect
- **Dirty highlighting** — `data-formwork-dirty` on edit forms
- **Morph behavior** — validation errors appear without page reload
