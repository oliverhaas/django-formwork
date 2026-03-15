# django-formwork

[![CI](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Python](https://img.shields.io/pypi/pyversions/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Django](https://img.shields.io/badge/django-5.2%20%7C%206.0-blue.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-formwork.svg)](https://github.com/oliverhaas/django-formwork/blob/main/LICENSE)

Better Django forms — modern styling out of the box, then htmx integration for dynamic behavior.

## Features

- **Zero-config styling** — Set `FORM_RENDERER` once and all forms get [DaisyUI](https://daisyui.com/) styling
- **Admin-safe** — Django admin is unaffected
- **Custom widgets** — Toggle, Range, Rating, PasswordReveal, SearchSelect, MultiSelect, ComboBox, DataList, FileDropZone, ImageDropZone, ValidatedTextarea
- **htmx integration** — Server-side search, textarea validation, full-form morphing with idiomorph
- **CSS `@apply` architecture** — All DaisyUI classes applied via CSS, easily overridable with Tailwind utilities

## Quick Start

```bash
pip install django-formwork
```

```python
INSTALLED_APPS = [..., "django_formwork"]
FORM_RENDERER = "django_formwork.FormworkRenderer"
```

```html
{% load formwork %}
{% formwork_css %}
{{ form }}
{% formwork_js %}
```

## Requirements

- Python 3.12+
- Django 5.2+
- DaisyUI 5 + Tailwind CSS 4+

## Documentation

Full documentation at [oliverhaas.github.io/django-formwork](https://oliverhaas.github.io/django-formwork/).

## License

BSD 3-Clause. See [LICENSE](LICENSE).
