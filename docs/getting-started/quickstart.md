# Quick Start

## Basic form

With `FORM_RENDERER` set, any Django form renders with DaisyUI styling:

```python
# forms.py
from django import forms

class ContactForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)
```

```html
<!-- template.html -->
{% load formwork %}
{% formwork_css %}

<form method="post" class="max-w-md mx-auto">
  {% csrf_token %}
  {{ form }}
  <button type="submit" class="btn btn-primary mt-4">Send</button>
</form>

{% formwork_js %}
```

Each field renders inside a `<fieldset class="fieldset">` with proper labels, help text, and error tooltips.

## Per-form styling

If you don't want to set `FORM_RENDERER` globally, use the form base classes:

```python
from django_formwork.forms import FormworkForm, FormworkModelForm

class ContactForm(FormworkForm):
    name = forms.CharField()
    email = forms.EmailField()

class ProfileForm(FormworkModelForm):
    class Meta:
        model = Profile
        fields = ["name", "bio", "avatar"]
```

## Custom widgets

Formwork includes widgets that go beyond standard HTML inputs:

```python
from django_formwork.widgets import (
    Toggle, Range, Rating, PasswordReveal,
    SearchSelect, MultiSelect, ComboBox, DataList,
    FileDropZone, ImageDropZone, ValidatedTextarea,
)

class ExampleForm(forms.Form):
    # Toggle switch instead of checkbox
    dark_mode = forms.BooleanField(widget=Toggle)

    # Range slider
    volume = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100}))

    # Star rating
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5), coerce=int, widget=Rating,
    )

    # Password with show/hide toggle
    password = forms.CharField(widget=PasswordReveal)

    # Searchable single-select dropdown
    country = forms.ChoiceField(
        choices=[("us", "United States"), ("de", "Germany")],
        widget=SearchSelect,
    )

    # Multi-select with checkboxes
    languages = forms.MultipleChoiceField(
        choices=[("py", "Python"), ("js", "JavaScript")],
        widget=MultiSelect,
    )

    # Text input with autocomplete suggestions
    tags = forms.CharField(
        widget=ComboBox(suggestions=["Python", "Django", "htmx"]),
    )

    # Native browser datalist
    browser = forms.CharField(
        widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
    )

    # Drag-and-drop file upload
    attachment = forms.FileField(widget=FileDropZone)

    # Image upload with preview
    avatar = forms.ImageField(widget=ImageDropZone)
```

## Server-side search

For large datasets, use htmx-powered server-side search:

```python
# views.py
from django_formwork.views import FormworkSearchView

class CountrySearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):
        countries = Country.objects.filter(name__icontains=query)[:20]
        return [{"value": c.code, "label": c.name} for c in countries]
```

```python
# forms.py
country = forms.ChoiceField(
    widget=SearchSelect(search_url=reverse_lazy("country-search")),
)
```

## Template tags

```html
{% load formwork %}

<!-- CSS link tag -->
{% formwork_css %}

<!-- JS script tag (idiomorph morph config) -->
{% formwork_js %}
```
