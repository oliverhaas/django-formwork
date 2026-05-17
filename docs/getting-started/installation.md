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

### DaisyUI version

Formwork requires **DaisyUI 5.x**. DaisyUI 4 and earlier use a different component API and are not compatible. Within the DaisyUI 5 series, formwork is tested against the latest stable release — any DaisyUI 5.x version should work.

### CSS files

Formwork ships two CSS files:

- **`formwork.css`** — Tailwind source file. It contains `@apply` directives and must be processed by the Tailwind CLI or PostCSS plugin as part of your build. Use this for production.
- **`formwork-dist.css`** — Pre-compiled output. It can be included directly without a build step, useful for quick prototyping or projects that don't use a Tailwind build pipeline. It is a snapshot and may lag behind `formwork.css` if you customise things.

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

For quick prototyping without a build step, use the pre-compiled file instead:

```html
<link rel="stylesheet" href="{% static 'formwork/formwork-dist.css' %}">
```

### htmx + Alpine.js (optional)

Needed by the dynamic widgets (server-side search, password reveal, combo boxes, validated textarea):

```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta3"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3"></script>
{% load formwork %}
{% formwork_js %}
```

- **htmx 4** powers server-side search and validation. Its built-in `outerMorph` swap replaces the standalone idiomorph dependency from older versions.
- **Alpine.js** drives the client-side state of dropdowns, password reveal, and the drop zones.
- **`{% formwork_js %}`** loads `formwork.js` as an ES module. The file imports `formwork-core.js` (htmx morph extension, dirty-tracking, native-validation disabling) plus the per-widget Alpine.data components.

### JS loading paths

`{% formwork_js %}` is the easy path: one tag, everything loaded. Two alternatives are also supported:

- **Per-form Media** — each of `SearchSelect`, `MultiSelect`, `ComboBox` declares `class Media: js = ...`, so `{{ form.media }}` includes only the widget JS the form actually uses. In this mode load `{% formwork_core_js %}` separately for the core (morph, dirty-tracking, validation disabling).
- **JS bundler** — `import "/static/formwork/formwork.js"` (or alias it) from a vite/webpack/esbuild entry. The bundler resolves the chain and produces a single output; no `{% formwork_js %}` needed.

ES module URL deduplication makes the paths safely composable; combining `{% formwork_js %}` and `{% formwork_core_js %}` on the same page still executes the core only once.
