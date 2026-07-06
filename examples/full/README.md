# Full example — Taskwork

A small project-management UI built on django-formwork. Five pages exercise the framework end-to-end: dashboard, task list with inline edit, task detail, multi-step project wizard, and a settings page that picks up the widgets the task domain doesn't.

## Setup

```bash
cd examples/full
uv pip install django django-formwork pillow         # pillow for ImageField
npm install tailwindcss daisyui                      # CSS build tools
uv run manage.py formwork install                    # download Lucide icons
npx @tailwindcss/cli -i app.css -o static/dist.css   # compile CSS
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
| `/settings/` | Showcase page for `PhoneInput`, `ImageDropZone`, `PasswordReveal`, `OTPInput`, `ComboBox`, `Rating` |

## Widgets covered

Every widget in the package gets airtime across these pages. Quick lookup:

- **Dashboard quick-add**: `SearchSelect`
- **Tasks list filter bar**: `SearchSelect` (status, priority) + plain text input
- **Task form**: `SearchSelect`, `MultiSelect` (model-backed, auto-wired server search), `DatePicker`, `ImageDropZone`, `FileDropZone`, `Rating`
- **Wizard**: `ValidatedTextarea`, `Toggle`, `Range`, `RadioSelect`, `SearchSelect`, `DatePicker`, `MultiSelect`
- **Settings**: `PhoneInput`, `ImageDropZone`, `PasswordReveal`, `OTPInput`, `ComboBox`, `Rating`

## What's intentionally not here

- Auth — the settings page is a stub that doesn't persist anything.
- File processing — uploaded files are saved to `media/` and rendered, nothing else.
- Real-time anything — htmx morph swaps where it makes sense, no SSE / WebSockets.

## CSS theme switching

The topbar `palette` dropdown swaps DaisyUI themes at runtime (persisted via `localStorage`). All UI colours derive from theme tokens — try `synthwave`, `night`, or `dracula` to see the same layout in different skins.
