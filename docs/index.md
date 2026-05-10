# Django Formwork

Better Django forms — modern styling out of the box, then htmx integration for dynamic behavior.

## What is Formwork?

Django Formwork is a form rendering library that gives your Django forms [DaisyUI](https://daisyui.com/) styling automatically. No widget subclassing, no manual CSS classes — just render `{{ form }}` and get styled forms.

**Key features:**

- **Zero-config styling** — Set `FORM_RENDERER` once and all forms get DaisyUI styling
- **Admin-safe** — Django admin is unaffected (it renders widgets directly, not forms)
- **Custom widgets** — Toggle switches, star ratings, password reveal, searchable dropdowns, combo boxes, file drop zones, and more
- **htmx 4 integration** — Server-side search, textarea validation, and full-form morphing with htmx's built-in `outerMorph` swap
- **CSS `@apply` architecture** — All DaisyUI classes are applied via CSS, not in Python or templates. Users can override with Tailwind utilities

## Requirements

- Python 3.12+
- Django 5.2+
- [DaisyUI](https://daisyui.com/) 5 (CSS framework, included by you)
- [Tailwind CSS](https://tailwindcss.com/) 4+ (for building `formwork.css`)

## Quick Start

```bash
pip install django-formwork
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "django_formwork",
]
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

That's it. Every form in your project now renders with DaisyUI styling.
