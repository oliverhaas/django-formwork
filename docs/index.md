# django-formwork

django-formwork is an opinionated UI framework for Django, built on Django forms. Forms are the central building block of most Django apps (CRUD pages, admin, search filters, sign-ups, content editors), so formwork treats the form as the primary UI surface: define a `Form` or `ModelForm` and you get DaisyUI styling, widgets that go beyond Django's built-ins, and the htmx + Alpine wiring that makes them dynamic without bespoke per-page JS. Set `FORM_RENDERER` once, include the CSS and JS template tags, and `{{ form }}` produces the full DaisyUI markup. The admin is unaffected; it renders widgets directly, never `{{ form }}` or `as_field_group()`.

The widgets that ship with the framework are `Toggle`, `Range`, `Rating`, `PasswordReveal`, `SearchSelect`, `MultiSelect`, `ComboBox`, `DataList`, `FileDropZone`, `ImageDropZone`, `ValidatedTextarea`, `DatePicker`, `InputNumber`, `InputMask`, and `OTPInput`. The dropdowns and the validated textarea auto-wire server-side endpoints when paired with a `FormworkForm`.

On the JavaScript side, `{% formwork_js %}` loads an ES module that imports `formwork-core.js` (the `formwork-morph` htmx extension, dirty-field tracking, native-validation disabling) plus each widget's Alpine.data component. The same files can also be loaded per-form via `{{ form.media }}` or pulled in by a JS bundler; see the [installation guide](getting-started/installation.md).

## Requirements

Python 3.14+, Django 6.0, [DaisyUI](https://daisyui.com/) 5, [Tailwind CSS](https://tailwindcss.com/) 4. DaisyUI and Tailwind are not bundled.

## Quick start

```bash
pip install django-formwork
```

```python
# settings.py
INSTALLED_APPS = [..., "django_formwork"]
FORM_RENDERER = "django_formwork.FormworkRenderer"
```

```html
<!-- template.html -->
{% load formwork %}
{% formwork_css %}

<form method="post">
  {% csrf_token %}
  {{ form }}
  <button type="submit">Submit</button>
</form>

{% formwork_js %}
```
