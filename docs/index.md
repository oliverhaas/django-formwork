# django-formwork

django-formwork is an opinionated UI framework for Django, built on Django forms. Forms are the central building block of most Django apps (CRUD pages, admin, search filters, sign-ups, content editors), so formwork treats the form as the primary UI surface: define a `Form` or `ModelForm` and you get DaisyUI styling, widgets that go beyond Django's built-ins, and the htmx + Alpine wiring that makes them dynamic without bespoke per-page JS. Set `FORM_RENDERER` once, build the CSS with Tailwind as the [installation guide](getting-started/installation.md#4-build-the-css) shows, include the JS template tag, and `{{ form }}` produces the full DaisyUI markup. The admin is unaffected; it renders widgets directly, never `{{ form }}` or `as_field_group()`.

The widgets are `Select`, `SelectMultiple`, `ComboBox`, `ComboBoxMultiple`, `TextInput`, `Textarea`, `PasswordInput`, `SearchInput`, `DateInput`, `DateRangeInput`, `DatePicker`, `StepperNumberInput`, `SuffixNumberInput`, `CheckboxInput`, `ToggleInput`, `CheckboxSelectMultiple`, `CardRadioSelect`, `CardCheckboxSelectMultiple`, `FileDropzoneInput`, `ImageDropzoneInput`, `OTPInput`, `InputMask`, `Range`, `Rating`, `DataList`, `ValidatedTextarea` and `Display`. `Select`, `SelectMultiple`, `ComboBox` and `ComboBoxMultiple` search on the server when the widget gets a `search_queryset`, and the validated textarea posts to a view you write.

`{% formwork_js %}` loads an ES module that imports `formwork-core.js` (the `formwork-morph` htmx extension, dirty-field tracking, native-validation disabling) and the Alpine.data component of each widget. `{{ form.media }}` loads the same files per form, and a JS bundler can import them. The [installation guide](getting-started/installation.md#js-loading-paths) describes the three paths.

## Requirements

Python 3.14+, Django 6.0, [DaisyUI](https://daisyui.com/) 5, [Tailwind CSS](https://tailwindcss.com/) 4. DaisyUI and Tailwind are not bundled.

## Quick start

```bash
pip install django-formwork
```

```python
# settings.py
INSTALLED_APPS = [..., "django.forms", "django_iconx", "django_formwork"]
FORM_RENDERER = "django_formwork.FormworkRenderer"
```

```html
<!-- base.html -->
{% load formwork static %}
<head>
  <link rel="stylesheet" href="{% static 'dist.css' %}">  <!-- your Tailwind build of formwork.css -->
  <script src="https://unpkg.com/htmx.org@4.0.0/dist/htmx.min.js"></script>
  <script src="https://unpkg.com/htmx.org@4.0.0/dist/ext/hx-alpine-compat.min.js"></script>
  {% formwork_js %}
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>

<form method="post">
  {% csrf_token %}
  {{ form }}
  <button type="submit" class="btn btn-primary">Save</button>
</form>
```

The [installation guide](getting-started/installation.md) explains each setting and the script order.
