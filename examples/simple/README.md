# Simple Example

Minimal django-formwork setup: one form with standard and custom widgets, DaisyUI styling, htmx morphing, and error display.

## Setup

This example is a self-contained Django project with its own `pyproject.toml`,
pinned to the copy of django-formwork in this repo checkout. It's editable, so
framework changes show up immediately, no reinstall needed.

```bash
npm install                                          # once, from the repo root: Tailwind + DaisyUI
cd examples/simple
uv sync                                              # Python deps: Django, django-formwork (editable), Pillow
uv run manage.py formwork install                    # Icons: SVGs + static/iconx/icons.css
npx @tailwindcss/cli -i app.css -o static/dist.css   # Build CSS (resolves Tailwind/DaisyUI from the repo root)
uv run manage.py migrate                             # Create + seed the cookbook DB
uv run manage.py runserver
```

Open http://localhost:8000/ in your browser.

## What it demonstrates

- `FORM_RENDERER = "django_formwork.FormworkRenderer"`: all forms styled automatically
- `app.css` as the Tailwind input: imports `formwork.css` (Tailwind + DaisyUI) plus the generated `static/iconx/icons.css`
- Standard widgets (TextInput, EmailInput, Textarea) auto-styled by CSS
- Custom widgets: Toggle, Range, Rating, PasswordReveal, SearchSelect, MultiSelect, ComboBox, DataList
- htmx 4 form submission with `outerMorph` swap (errors appear without page reload)

## Cookbook

The cookbook pages back the docs guide. After `migrate` (which seeds people and a
legacy ticket), visit:

- `/cookbook/1/` plain field
- `/cookbook/2/` searchable assignee dropdown
- `/cookbook/3/` server-side validation via htmx morph swap
- `/cookbook/4/` create on valid POST, redirect htmx-aware via `HX-Redirect`
- `/cookbook/5/` screenshot upload with `ImageDropZone`
- `/cookbook/6/` editing with `validate_dirty_only`

Regenerate the docs screenshots (after building CSS and running migrate).
This is a maintainer task: it needs `playwright`, which lives in the repo
root's `dev` dependency group, not in this example's own `pyproject.toml`.
Run it from the repo root:

```bash
uv run --group dev python examples/simple/generate_screenshots.py
```
