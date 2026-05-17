# django-formwork

DaisyUI-styled Django forms with htmx-powered widgets. Drop-in renderer, a set of custom widgets, and a per-page bundle for the htmx morph extension and Alpine integration.

## What's in the box

- **Renderer** — `FormworkRenderer` overrides the form and field templates so `{{ form }}` and `{{ field.as_field_group }}` produce DaisyUI markup. Set `FORM_RENDERER` globally, or opt in per form via `FormworkForm` / `FormworkModelForm`.
- **Custom widgets** — Toggle, Range, Rating, PasswordReveal, SearchSelect, MultiSelect, ComboBox, DataList, FileDropZone, ImageDropZone, ValidatedTextarea.
- **htmx 4 integration** — auto-registered server-side search endpoints for dropdown widgets, server-side textarea validation, and a `formwork-morph` extension that preserves Alpine state, focused inputs, and `<details>` open state across full-form morphs.
- **Admin-safe** — Django admin renders widgets directly, never forms or field groups, so the renderer override doesn't affect admin pages.

## Requirements

- Python 3.14+
- Django 6.0
- [DaisyUI](https://daisyui.com/) 5 (CSS framework, included by you)
- [Tailwind CSS](https://tailwindcss.com/) 4 (for building `formwork.css`)

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

Every form in the project now renders with DaisyUI styling.
