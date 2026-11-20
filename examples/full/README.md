# Full example — Taskwork

A small task tracker built on django-formwork. The app pages are what a team member works in: their own tasks, a board, a page per task, a project wizard and the settings. The admin at `/admin/` holds the tables, filters and bulk actions, so the two do not repeat each other.

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
| `/` | My work: your open tasks by due date (overdue, this week, later), what you finished this week, the team's latest activity and a quick add. A checkbox ticks a task off. |
| `/tasks/` | The board: one column per status, your tasks first in each. Drag a card to another column to move it (on a touch screen, change the status on the task page), or add a task at the foot of a column. The filters live in the URL. |
| `/tasks/<id>/` | The task page: description, comments and changes on the left. Status, assignee, due date, priority and tags on the right save each change by themselves (section forms). |
| `/tasks/new/` and `/tasks/<id>/edit/` | The full task form, with every field. The template places the fields in sections with `as_field_group`. |
| `/wizard/` | Four-step project wizard (Project → Configuration → First task → Review) with the DaisyUI `steps` component |
| `/settings/` | Your profile, sign-in and preferences, saved on a single local `Profile` row. The member you pick here is "you" on My work and the board. Shows `PhoneInput`, `Select`, `ImageDropzoneInput`, `PasswordInput`, `OTPInput`, `ComboBox` and `Rating`. |

## Admin

`/admin/` runs `django_formwork.admin` over eight apps, so the index, the
changelists and the change forms look like a real back office:

| App | Models | Shows |
|---|---|---|
| `taskmanager` | Tasks, members, tags, profile | Status and priority badges, a reminder with its day and time in one calendar, an inline of assigned tasks, a singleton without an add page |
| `people` | Departments, employees, time off, equipment | A self-referencing manager, empty-value filters, approvals as actions |
| `crm` | Companies, contacts, deals, activities, follow-ups | Autocomplete, related-only filters, stacked and tabular inlines, follow-ups as generic inlines on companies, contacts and deals, a website field whose widget adds an Open link to its label row (`label_links()`), the deals of each stage as a chart over the list, a deal's pipeline steps over its form |
| `billing` | Invoices, payments | Line and payment inlines, file fields, `raw_id_fields`, each month's invoices as stacked columns over the list |
| `helpdesk` | Tickets, canned responses | Over a thousand tickets, a reply inline, horizontal radios, opened and solved tickets per week over the list |
| `recruiting` | Openings, candidates, applications, interviews | A JSON field, a range filter, stage actions |
| `events` | Venues, events, registrations | Prepopulated slugs, an editable list column, about 20,000 registrations, registrations per month over the list, an event's sign-ups over time under its form |
| `content` | Topics, posts, comments | Many-to-many topics, image covers, comment moderation, a word count under a post's body from the admin's `class Media`, placeholder icons (no `icon` set) |

The figures and charts over the lists of deals, invoices, tickets and events are
`list_top` slots. They load after the page and follow the list's search and filters.
The cards over a change form are `change_top` slots. Each app computes its numbers
in `stats.py`, `taskmanager/figures.py` has the helpers they share, and
`templates/charts/` has the templates. The charts are [Chart.js](https://www.chartjs.org/)
with the theme's colors (`taskmanager/static/taskmanager/charts.js`).

## PostgreSQL and pghistory

On SQLite, the admin's history panel lists the admin's own entries. On PostgreSQL,
[django-pghistory](https://django-pghistory.readthedocs.io/) records each insert and
update of tasks, companies, deals, tickets and posts with a database trigger, so the
panel also shows changes made outside the admin. The `audit` app holds the event
models, and the admin site uses `PghistoryHistory` when pghistory is installed.

`TASKWORK_POSTGRES` names the database and turns this mode on. libpq's `PGHOST`,
`PGPORT`, `PGUSER` and `PGPASSWORD` say where the database runs:

```bash
docker run -d --name taskwork-postgres -p 5433:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=taskwork postgres:18
export TASKWORK_POSTGRES=taskwork PGHOST=localhost PGPORT=5433 PGUSER=postgres PGPASSWORD=postgres
uv run --group postgres manage.py migrate      # also installs the triggers
uv run --group postgres manage.py seed
uv run --group postgres manage.py runserver
```

The seed writes its rows without a user, so their first event names no user.

## Widgets covered

Every widget in the package gets airtime across these pages. Quick lookup:

- **My work quick add**: a text input and `DatePicker`
- **Board filters**: `SearchInput`, `Select` with a placeholder for "any"
- **Task page side column**: `Select`, `SelectMultiple` and `DatePicker` in a section form that saves on change
- **Task form**: `Select` (assignee, backed by the `Member` model with an initials badge and email per option, server search), `SelectMultiple` (tags, server search), `DatePicker`, `DateTimePicker` (reminder), `ImageDropzoneInput`, `FileDropzoneInput`, `Rating`
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

Covers the persisted settings flow (Profile singleton, phone validation, avatar upload), the task flows (My work, the board, the task page and its activity) and a smoke test that renders the changelist, add and change page of every model in the admin. [django-nplus1](https://github.com/oliverhaas/django-nplus1) fails a test whose page loads a relation for each row; on the dev server it logs a warning instead. With the variables from "PostgreSQL and pghistory" set, `uv run --group postgres pytest` runs them on PostgreSQL.

## CSS theme switching

The topbar `palette` dropdown swaps DaisyUI themes at runtime (persisted via `localStorage`). All UI colours derive from theme tokens — try `synthwave`, `night`, or `dracula` to see the same layout in different skins.
