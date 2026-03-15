# Installation

## Install the package

```bash
pip install django-formwork
```

Or with uv:

```bash
uv add django-formwork
```

## Configure Django

Add `django_formwork` to your installed apps and set the form renderer:

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "django_formwork",
]

# Makes ALL forms use formwork templates automatically
FORM_RENDERER = "django_formwork.FormworkRenderer"
```

## Frontend dependencies

Formwork uses [DaisyUI](https://daisyui.com/) 5 for component styling and [Tailwind CSS](https://tailwindcss.com/) 4+ for the build step. You need to include these in your project.

### Tailwind CSS + DaisyUI setup

```bash
npm install -D tailwindcss @tailwindcss/cli daisyui@5
```

In your main CSS file, import Tailwind and DaisyUI, then import formwork's CSS:

```css
@import "tailwindcss";
@import "daisyui";
@import "../../path/to/site-packages/django_formwork/static/formwork/formwork.css";
```

### htmx + Alpine.js (optional)

For dynamic widgets (server-side search, password reveal, combo boxes, etc.):

```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2"></script>
<script src="https://cdn.jsdelivr.net/npm/idiomorph@0.7"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3"></script>
{% load formwork %}
{% formwork_js %}
```

- **htmx** — Powers server-side search and validation
- **idiomorph** — DOM morphing for htmx responses (preserves form state)
- **Alpine.js** — Client-side interactivity for custom widgets
- **formwork.js** — Configures idiomorph to preserve Alpine state during morphs
