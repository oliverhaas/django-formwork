# django-formwork

[![CI](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Python](https://img.shields.io/pypi/pyversions/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Django](https://img.shields.io/badge/django-6.0-blue.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-formwork.svg)](https://github.com/oliverhaas/django-formwork/blob/main/LICENSE)

django-formwork applies DaisyUI styling to Django forms and ships a small set of widgets that lean on htmx and Alpine.js. Set `FORM_RENDERER` once, include the CSS and JS template tags, and `{{ form }}` produces DaisyUI markup. The admin is unaffected; it renders widgets directly, never `{{ form }}` or `as_field_group()`.

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
{% load formwork %}
{% formwork_css %}
{{ form }}
{% formwork_js %}
```

## Widgets

`Toggle`, `Range`, `Rating`, `PasswordReveal`, `SearchSelect`, `MultiSelect`, `ComboBox`, `DataList`, `FileDropZone`, `ImageDropZone`, `ValidatedTextarea`. The three dropdown widgets auto-register a server-side search endpoint when used on a `FormworkForm`. `ValidatedTextarea` does the same for live server-side text validation.

## htmx 4 integration

`{% formwork_js %}` loads `formwork.js` as an ES module. It imports `formwork-core.js` (the `formwork-morph` htmx extension, dirty-field tracking, native validation disabling) and each widget's Alpine component. Per-form `{{ form.media }}` and bundler imports are also supported; details are in the installation docs.

## Requirements

Python 3.14+, Django 6.0, DaisyUI 5, Tailwind CSS 4. DaisyUI and Tailwind are not bundled.

## Documentation

https://oliverhaas.github.io/django-formwork/

## Contributing

Screenshot baselines under `tests/widgets/screenshots/` use Git LFS. Install it once globally before cloning:

```bash
sudo apt install git-lfs   # or brew install git-lfs
git lfs install
```

If you cloned before installing LFS, run `git lfs install && git lfs pull` to fetch the PNG bytes.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
