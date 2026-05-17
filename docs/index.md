# django-formwork

django-formwork applies DaisyUI styling to Django forms and ships a small set of widgets that lean on htmx and Alpine.js. Set `FORM_RENDERER` once, include the CSS and JS template tags, and `{{ form }}` produces DaisyUI markup. The admin is unaffected; it renders widgets directly, never `{{ form }}` or `as_field_group()`.

The custom widgets are `Toggle`, `Range`, `Rating`, `PasswordReveal`, `SearchSelect`, `MultiSelect`, `ComboBox`, `DataList`, `FileDropZone`, `ImageDropZone`, `ValidatedTextarea`, `DatePicker`, `InputNumber`, `InputMask`, `OTPInput`, `PhoneInput`, and `CountryInput`. The dropdowns and the validated textarea auto-wire server-side endpoints when paired with a `FormworkForm`.

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
