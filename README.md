# django-formwork

[![CI](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Python](https://img.shields.io/pypi/pyversions/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Django](https://img.shields.io/badge/django-6.0-blue.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-formwork.svg)](https://github.com/oliverhaas/django-formwork/blob/main/LICENSE)

django-formwork is an opinionated UI framework for Django, built on Django forms. Forms are the central building block of most Django apps (CRUD pages, admin, search filters, sign-ups, content editors), so formwork treats the form as the primary UI surface. Define a `Form` or `ModelForm` and you get DaisyUI styling, widgets that go beyond Django's built-ins (dropdowns with server-side search, drop zones, OTP, date range, date picker, server-validated textarea, and more), and the htmx + Alpine wiring that makes them dynamic without bespoke per-page JS. Set `FORM_RENDERER` once, build the CSS, include the JS template tag, and `{{ form }}` produces the full DaisyUI markup. The admin is unaffected; it renders widgets directly, never `{{ form }}` or `as_field_group()`.

## Quick start

```bash
pip install django-formwork
```

```python
# settings.py
INSTALLED_APPS = [..., "django.forms", "django_iconx", "django_formwork"]
FORM_RENDERER = "django_formwork.FormworkRenderer"
```

`"django.forms"` gives the renderer Django's own widget templates. The `DjangoTemplates` backend must find app templates (`APP_DIRS=True` or the `app_directories` loader).

```html
{% load formwork static %}
<head>
  <link rel="stylesheet" href="{% static 'dist.css' %}">
  <script src="https://unpkg.com/htmx.org@4.0.0/dist/htmx.min.js"></script>
  <script src="https://unpkg.com/htmx.org@4.0.0/dist/ext/hx-alpine-compat.min.js"></script>
  {% formwork_js %}
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
...
{{ form }}
```

`dist.css` is your Tailwind build of formwork's `formwork.css`. The package ships only that Tailwind source, and the installation docs show the build entry point.

Keep the scripts in this order. htmx's alpine-compat extension is required: without it a morph strips what Alpine wrote into the DOM. `{% formwork_js %}` must run before Alpine, so that its `alpine:init` listeners exist when Alpine starts.

## Widgets

`Select`, `SelectMultiple`, `ComboBox`, `ComboBoxMultiple`, `TextInput`, `Textarea`, `PasswordInput`, `SearchInput`, `DateInput`, `DateRangeInput`, `DatePicker`, `StepperNumberInput`, `SuffixNumberInput`, `CheckboxInput`, `ToggleInput`, `CheckboxSelectMultiple`, `CardRadioSelect`, `CardCheckboxSelectMultiple`, `FileDropzoneInput`, `ImageDropzoneInput`, `OTPInput`, `InputMask`, `Range`, `Rating`, `DataList`, `ValidatedTextarea` and `Display`. The names shadow `django.forms` on purpose, so import the module: `from django_formwork import widgets`, then `widgets.Select`.

`Select`, `SelectMultiple`, `ComboBox` and `ComboBoxMultiple` search on the server when the widget gets a `search_queryset`. A `FormworkForm` or `FormworkModelForm` class registers the search when Python creates it, and one `include("django_formwork.urls")` serves every search. `ValidatedTextarea` posts its text to a `FormworkValidateView` subclass for live server-side validation.

## htmx 4 integration

`{% formwork_js %}` loads `formwork.js` as an ES module. It imports `formwork-core.js` (the `formwork-morph` htmx extension, dirty-field tracking, native validation disabling) and the Alpine component of each widget. Per-form `{{ form.media }}` and bundler imports also work; the installation docs describe all three paths. `{% formwork_sections_js %}` adds section forms: several forms on one page that each autosave their own fields of one row.

## Requirements

Python 3.14+, Django 6.0, DaisyUI 5, Tailwind CSS 4. DaisyUI and Tailwind are not bundled.

## Development

```bash
uv sync
uv run pytest -m "not screenshot and not benchmark"
```

The PostgreSQL run covers `search_ranked`. Django connects through libpq, so set `PGHOST`, `PGUSER` and `PGPASSWORD`; the test database is named `formwork`, and the suite creates the `pg_trgm` extension in it:

```bash
uv run pytest tests/ --ds settings.postgres -m "not screenshot and not benchmark and not e2e" -n auto --no-cov
```

## Documentation

https://oliverhaas.github.io/django-formwork/

## License

BSD 3-Clause. See [LICENSE](LICENSE).
