# Full Example — Task Manager

A task management app demonstrating django-formwork's real-world usage: CRUD operations, search/filter, and a multi-step wizard.

## Setup

```bash
cd examples/full
uv pip install django django-formwork                # Python deps
npm install tailwindcss daisyui                      # CSS build tools
uv run manage.py formwork install                    # Download Lucide icons
npx @tailwindcss/cli -i app.css -o static/dist.css  # Build CSS
uv run manage.py migrate                             # Create database
uv run manage.py runserver
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
