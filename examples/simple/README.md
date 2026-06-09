# Simple Example

Minimal django-formwork setup: one form with standard and custom widgets, DaisyUI styling, htmx morphing, and error display.

## Setup

```bash
cd examples/simple
uv pip install django django-formwork                # Python deps
npm install tailwindcss daisyui                      # CSS build tools
uv run manage.py formwork install                    # Download Lucide icons
npx @tailwindcss/cli -i app.css -o static/dist.css  # Build CSS
uv run manage.py migrate                             # Create + seed the cookbook DB
uv run manage.py runserver
```

Open http://localhost:8000/ in your browser.

## What it demonstrates

- `FORM_RENDERER = "django_formwork.FormworkRenderer"`: all forms styled automatically
- `formwork.css` as the single Tailwind input (includes DaisyUI + icons)
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

Regenerate the docs screenshots (after building CSS and running migrate):

```bash
uv run python generate_screenshots.py
```
