# django-formwork

[![CI](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-formwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Python](https://img.shields.io/pypi/pyversions/django-formwork.svg)](https://pypi.org/project/django-formwork/)
[![Django](https://img.shields.io/badge/django-6.0-blue.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-formwork.svg)](https://github.com/oliverhaas/django-formwork/blob/main/LICENSE)

DaisyUI-styled Django forms with htmx-powered widgets. Drop-in renderer plus a set of custom widgets (search dropdowns, comboboxes, rating, drop zones, validated textarea); no widget subclassing or per-form attribute juggling required.

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

Every form in the project now renders with DaisyUI styling. Django admin is unaffected — it renders widgets directly, not forms.

## What you get

- **Renderer** — `FormworkRenderer` swaps the form and field templates so `{{ form }}` and `{{ field.as_field_group }}` produce DaisyUI markup. Per-form opt-in is available via `FormworkForm` / `FormworkModelForm`.
- **Custom widgets** — `Toggle`, `Range`, `Rating`, `PasswordReveal`, `SearchSelect`, `MultiSelect`, `ComboBox`, `DataList`, `FileDropZone`, `ImageDropZone`, `ValidatedTextarea`.
- **htmx 4 integration** — server-side search and textarea validation, plus a `formwork-morph` extension that preserves Alpine state, focused inputs, and `<details>` open state across full-form morphs.

## Requirements

- Python 3.14+
- Django 6.0
- DaisyUI 5 + Tailwind CSS 4 (you bring them; we don't bundle)

## Documentation

[oliverhaas.github.io/django-formwork](https://oliverhaas.github.io/django-formwork/)

## Contributing

Screenshot baselines under `tests/widgets/screenshots/` are stored via [Git LFS](https://git-lfs.com/). Install git-lfs once globally before cloning:

```bash
sudo apt install git-lfs   # or `brew install git-lfs`
git lfs install
```

If you cloned before installing LFS, run `git lfs install && git lfs pull` to fetch the real PNG bytes.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
