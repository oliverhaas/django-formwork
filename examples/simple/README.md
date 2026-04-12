# Simple Example

Minimal django-formwork setup: one form with standard and custom widgets, DaisyUI styling, htmx morphing, and error display.

## Run

```bash
cd examples/simple
uv run --extra-with django-formwork manage.py runserver
```

Or with pip:

```bash
cd examples/simple
pip install django django-formwork
python manage.py runserver
```

Open http://localhost:8000/ in your browser.

## What it demonstrates

- `FORM_RENDERER = "django_formwork.FormworkRenderer"` — all forms styled automatically
- `{% formwork_css %}` / `{% formwork_js %}` template tags
- Standard widgets (TextInput, EmailInput, Textarea) auto-styled by CSS
- Custom widgets: Toggle, Range, Rating, PasswordReveal, SearchSelect, MultiSelect, ComboBox, DataList
- htmx form submission with idiomorph morphing (errors appear without page reload)
- DaisyUI loaded via CDN (no build step)
