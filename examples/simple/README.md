# Simple Example

Minimal django-formwork setup: one form with standard and custom widgets, DaisyUI styling, htmx morphing, and error display.

## Setup

```bash
cd examples/simple
uv pip install django django-formwork                # Python deps
npm install tailwindcss daisyui                      # CSS build tools
uv run manage.py formwork install                    # Download Lucide icons
npx @tailwindcss/cli -i app.css -o static/dist.css  # Build CSS
uv run manage.py runserver
```

Open http://localhost:8000/ in your browser.

## What it demonstrates

- `FORM_RENDERER = "django_formwork.FormworkRenderer"` — all forms styled automatically
- `formwork.css` as the single Tailwind input (includes DaisyUI + icons)
- Standard widgets (TextInput, EmailInput, Textarea) auto-styled by CSS
- Custom widgets: Toggle, Range, Rating, PasswordReveal, SearchSelect, MultiSelect, ComboBox, DataList
- htmx form submission with idiomorph morphing (errors appear without page reload)
