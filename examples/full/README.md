# Full example — Taskwork

A small project-management UI built on django-formwork. Five pages exercise the framework end-to-end: dashboard, task list with inline edit, task detail, multi-step project wizard, and a settings page that picks up the widgets the task domain doesn't.

## Setup

This example is a self-contained Django project with its own `pyproject.toml`,
pinned to the copy of django-formwork in this repo checkout. It's editable, so
framework changes show up immediately, no reinstall needed.

```bash
npm install                                          # once, from the repo root: Tailwind + DaisyUI
cd examples/full
uv sync                                              # Python deps: Django, django-formwork (editable), Pillow
uv run manage.py formwork install                    # icons: SVGs + static/iconx/icons.css
npx @tailwindcss/cli -i app.css -o static/dist.css   # compile CSS (resolves Tailwind/DaisyUI from the repo root)
uv run manage.py migrate
uv run manage.py seed                                # ~15 sample tasks
uv run manage.py runserver
```

Open http://localhost:8000/.

## Pages

| URL | What it shows |
|---|---|
| `/` | Dashboard — DaisyUI `stats` cards, recent activity feed, inline quick-add form |
| `/tasks/` | Tasks list — htmx-driven filter bar, table with inline status edit per row |
| `/tasks/new/` and `/tasks/<id>/edit/` | Two-column task form: full `ModelForm` left, metadata sidebar right |
| `/wizard/` | Four-step project wizard (Project → Configuration → First task → Review) with the DaisyUI `steps` component |
| `/settings/` | Showcase page for `PhoneInput`, `SearchSelect`, `ImageDropZone`, `PasswordReveal`, `OTPInput`, `ComboBox`, `Rating` |

## Widgets covered

Every widget in the package gets airtime across these pages. Quick lookup:

- **Dashboard quick-add**: plain Django inputs (a four-option priority doesn't need a fancy widget)
- **Tasks list filter bar**: plain selects + plain text input
- **Task form**: `SearchSelect` (assignee), `MultiSelect` (model-backed, auto-wired server search), `DatePicker`, `ImageDropZone`, `FileDropZone`, `Rating`
- **Wizard**: `ValidatedTextarea`, `Toggle`, `Range`, `RadioSelect`, `DatePicker`, `MultiSelect`
- **Settings**: `PhoneInput`, `SearchSelect` (country), `ImageDropZone`, `PasswordReveal`, `OTPInput`, `ComboBox`, `Rating`

## What's intentionally not here

- Auth — the settings page is a stub that doesn't persist anything.
- File processing — uploaded files are saved to `media/` and rendered, nothing else.
- Real-time anything — htmx morph swaps where it makes sense, no SSE / WebSockets.

## CSS theme switching

The topbar `palette` dropdown swaps DaisyUI themes at runtime (persisted via `localStorage`). All UI colours derive from theme tokens — try `synthwave`, `night`, or `dracula` to see the same layout in different skins.
