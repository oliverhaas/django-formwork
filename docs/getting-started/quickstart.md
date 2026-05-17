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

## Server-side textarea validation

`ValidatedTextarea` sends the textarea content to a server-side view as the user types, and highlights error spans in real time.

```python
# views.py
from django_formwork.views import FormworkValidateView

class SpellCheckView(FormworkValidateView):
    def get_errors(self, text: str, **kwargs) -> list[dict]:
        errors = []
        for match in find_misspellings(text):
            errors.append({
                "message": f"Misspelled: {match.word}",
                "start": match.start,
                "end": match.end,
            })
        return errors
```

```python
# forms.py
content = forms.CharField(
    widget=ValidatedTextarea(validate_url=reverse_lazy("spell-check")),
)
```

!!! warning "CSRF exemption"
    `FormworkValidateView` is CSRF-exempt because it performs read-only validation. Do not use it for operations with side effects (database writes, emails, etc.). For those, use a regular Django view with CSRF protection.

## Server-side search

`SearchSelect`, `MultiSelect`, and `ComboBox` register a search endpoint automatically when used on a `FormworkForm`. Wire the URL pattern once:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
]
```

Then pick one of the two registration paths.

**Model-backed** — pair the widget with `search_fields` against a queryset:

```python
from django.contrib.auth.decorators import login_required
from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchSelect

class CityForm(FormworkForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        widget=SearchSelect(
            search_fields=["name", "country__name"],
            search_decorator=login_required,
        ),
    )
```

**Choices-backed** — define a `search_choices_<fieldname>` method on the form:

```python
class TagForm(FormworkForm):
    tags = forms.ChoiceField(widget=SearchSelect)

    def search_choices_tags(self, query, request):
        return [
            {"value": t.slug, "label": t.name}
            for t in Tag.objects.filter(name__icontains=query)[:20]
        ]
```

`search_decorator` is required when using `search_fields` and protects the auto-generated endpoint; pass `None` explicitly for a public endpoint. See the [views reference](../reference/views.md) for details and for `FormworkSearchView` if you'd rather write the endpoint by hand.

## Template tags

```html
{% load formwork %}

<!-- CSS link tag -->
{% formwork_css %}

<!-- JS script tag (htmx 4 morph configuration) -->
{% formwork_js %}
```
