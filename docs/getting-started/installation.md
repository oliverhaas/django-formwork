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

Two CSS files ship with the package. `formwork.css` is the Tailwind source: it contains `@apply` directives and has to be processed by the Tailwind CLI or PostCSS plugin as part of your build. Use it in production.

`formwork-dist.css` is a pre-compiled snapshot that you can drop in without a build step. It's handy for prototyping or for projects without a Tailwind pipeline, but it may lag behind `formwork.css` if you customise things.

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

The dynamic widgets (server-side search, password reveal, combo boxes, validated textarea) depend on htmx 4 and Alpine.js. Load them yourself and then include the JS tag:

```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta3"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3"></script>
{% load formwork %}
{% formwork_js %}
```

htmx 4 handles the server-side search and validation requests; its built-in `outerMorph` swap covers what idiomorph used to do in earlier versions. Alpine.js drives the client-side state of the dropdowns, password reveal, and drop zones. `{% formwork_js %}` loads `formwork.js` as an ES module, which in turn imports `formwork-core.js` (the htmx morph extension, dirty-field tracking, and native-validation disabling) plus each widget's Alpine.data component.

### JS loading paths

The `{% formwork_js %}` bundle is one tag and covers everything; that's the path most projects want. Two alternatives also work.

For per-form loading via Django's `Media`, use `{{ form.media }}` for the widget JS the form actually contains, and add `{% formwork_core_js %}` for the page-global core (morph, dirty-tracking, validation disabling). `SearchSelect`, `MultiSelect`, and `ComboBox` each declare a `Media` class pointing at their Alpine component file.

For bundler-driven loading, `import "/static/formwork/formwork.js"` from a vite, webpack, or esbuild entry. The bundler walks the chain and emits a single bundle; no template tag is needed.

ES modules are deduplicated by URL, so mixing tags is harmless. Combining `{% formwork_js %}` and `{% formwork_core_js %}` on the same page still executes the core only once.
