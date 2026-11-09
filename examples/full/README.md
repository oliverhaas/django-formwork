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
uv run manage.py seed                                # sample data for every app, plus an admin/admin login
uv run manage.py runserver
```

Open http://localhost:8000/ for the app and http://localhost:8000/admin/ for the
admin (user `admin`, password `admin`).

`seed` deletes the sample rows and writes them again. `--scale 0.1` writes a
tenth of the rows, `--seed 2` gives a different but repeatable data set.

## Pages

| URL | What it shows |
|---|---|
| `/` | Dashboard — DaisyUI `stats` cards, recent activity feed, inline quick-add form |
| `/tasks/` | Tasks list — htmx-driven filter bar, table with inline status edit per row |
| `/tasks/new/` and `/tasks/<id>/edit/` | Two-column task form: full `ModelForm` left, metadata sidebar right |
| `/wizard/` | Four-step project wizard (Project → Configuration → First task → Review) with the DaisyUI `steps` component |
| `/settings/` | Showcase page for `PhoneInput`, `Select`, `ImageDropzoneInput`, `PasswordInput`, `OTPInput`, `ComboBox`, `Rating`, persisted on a single local `Profile` row |

## Admin

`/admin/` runs `django_formwork.admin` over eight apps, so the index, the
changelists and the change forms look like a real back office:

| App | Models | Shows |
|---|---|---|
| `taskmanager` | Tasks, members, tags, profile | Status and priority badges, an inline of assigned tasks, a singleton without an add page |
| `people` | Departments, employees, time off, equipment | A self-referencing manager, empty-value filters, approvals as actions |
| `crm` | Companies, contacts, deals, activities | Autocomplete, related-only filters, stacked and tabular inlines |
| `billing` | Invoices, payments | Line and payment inlines, file fields, `raw_id_fields` |
| `helpdesk` | Tickets, canned responses | Over a thousand tickets, a reply inline, horizontal radios |
| `recruiting` | Openings, candidates, applications, interviews | A JSON field, a range filter, stage actions |
| `events` | Venues, events, registrations | Prepopulated slugs, an editable list column, about 20,000 registrations |
| `content` | Topics, posts, comments | Many-to-many topics, image covers, comment moderation, placeholder icons (no `icon` set) |

## Widgets covered

Every widget in the package gets airtime across these pages. Quick lookup:

- **Dashboard quick-add**: plain Django inputs (a four-option priority doesn't need a fancy widget)
- **Tasks list filter bar**: plain selects + plain text input
- **Task form**: `Select` (assignee, backed by the `Member` model with an initials badge and email per option, server search), `SelectMultiple` (tags, server search), `DatePicker`, `ImageDropzoneInput`, `FileDropzoneInput`, `Rating`
- **Wizard**: `ValidatedTextarea`, `ToggleInput`, `Range`, `RadioSelect`, `DatePicker`, `SelectMultiple`
- **Settings**: `PhoneInput`, `Select` (country), `ImageDropzoneInput`, `PasswordInput`, `OTPInput`, `ComboBox`, `Rating`

## What's intentionally not here

- Auth for the app pages. Only the admin needs a login. Settings are pinned to one local `Profile` row, and assignees are plain `Member` rows rather than Django users.
- File processing — uploaded files are saved to `media/` and rendered, nothing else.
- Real-time anything — htmx morph swaps where it makes sense, no SSE / WebSockets.

## Tests

The example doubles as an integration test bed for the package:

```bash
uv run pytest
```

Covers the persisted settings flow (Profile singleton, phone validation, avatar upload), the task flows (Member assignee, htmx inline row edits) and a smoke test that renders the changelist, add and change page of every model in the admin.

## CSS theme switching

The topbar `palette` dropdown swaps DaisyUI themes at runtime (persisted via `localStorage`). All UI colours derive from theme tokens — try `synthwave`, `night`, or `dracula` to see the same layout in different skins.
