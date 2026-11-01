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
<!-- template.html; the base template loads the CSS and the scripts -->
<form method="post" class="max-w-md mx-auto">
  {% csrf_token %}
  {{ form }}
  <button type="submit" class="btn btn-primary mt-4">Send</button>
</form>
```

The [installation guide](installation.md#5-htmx-and-alpinejs) shows the `<head>` with the scripts in the order they must load.

Each field renders inside a `<fieldset class="fieldset">` with a label, help text and errors. A required field shows a red `*` after its label. Errors sit inline under a field that has help text and in a tooltip on a field without.

## Per-form styling

If you don't want to set `FORM_RENDERER` globally, use the form base classes:

```python
from django_formwork import FormworkForm, FormworkModelForm


class ContactForm(FormworkForm):
    name = forms.CharField()
    email = forms.EmailField()


class ProfileForm(FormworkModelForm):
    class Meta:
        model = Profile
        fields = ["name", "bio", "avatar"]
```

## Formwork widgets

The widget names follow Django's and shadow `django.forms` on purpose, so import the module and write `widgets.Select`:

```python
from django import forms

from django_formwork import widgets


class ExampleForm(forms.Form):
    # Toggle switch, with the label beside it
    dark_mode = forms.BooleanField(widget=widgets.ToggleInput, required=False)

    # Range slider
    volume = forms.IntegerField(widget=widgets.Range(attrs={"min": 0, "max": 100}))

    # Star rating
    rating = forms.TypedChoiceField(
        choices=widgets.Rating.make_choices(5),
        coerce=int,
        widget=widgets.Rating,
    )

    # Password with a show/hide button
    password = forms.CharField(widget=widgets.PasswordInput)

    # Dropdown; a search box appears past ten options
    country = forms.ChoiceField(
        choices=[("us", "United States"), ("de", "Germany")],
        widget=widgets.Select,
    )

    # Multi-select dropdown with checkboxes
    languages = forms.MultipleChoiceField(
        choices=[("py", "Python"), ("js", "JavaScript")],
        widget=widgets.SelectMultiple,
    )

    # Free text with suggestions
    topic = forms.CharField(
        widget=widgets.ComboBox(suggestions=["Python", "Django", "htmx"]),
    )

    # Number between - and + buttons
    seats = forms.IntegerField(widget=widgets.StepperNumberInput(integer=True, min=1))

    # Native date input
    start = forms.DateField(widget=widgets.DateInput)

    # Drag-and-drop file upload
    attachment = forms.FileField(widget=widgets.FileDropzoneInput)

    # Image upload with preview
    avatar = forms.ImageField(widget=widgets.ImageDropzoneInput)
```

The [widget reference](../reference/widgets.md) lists every widget and its parameters.

## Server-side textarea validation

`ValidatedTextarea` sends the textarea content to a server-side view as the user types, and highlights error spans in real time.

```python
# views.py
from django_formwork import FormworkValidateView


class SpellCheckView(FormworkValidateView):
    def get_errors(self, text: str, **kwargs) -> list[dict]:
        errors = []
        for match in find_misspellings(text):
            errors.append(
                {
                    "message": f"Misspelled: {match.word}",
                    "start": match.start,
                    "end": match.end,
                }
            )
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

`Select`, `SelectMultiple` and `ComboBox` search on the server when the widget gets a `search_queryset`. Wire the URL pattern once:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
]
```

Then give the widget the rows to search, the fields to match and an access rule:

```python
from django.contrib.auth.decorators import login_required

from django_formwork import FormworkForm, widgets


def cities(request):
    return City.objects.filter(active=True)


class CityForm(FormworkForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.filter(active=True),
        widget=widgets.Select(
            search_queryset=cities,
            search_fields=["name", "country__name"],
            search_decorator=login_required,
        ),
    )
```

The form registers the search when its class is created. Formwork imports the `forms` module of each installed app at startup, so a search declared there works in every worker from the first request. `search_queryset` is a callable that takes the request; the endpoint calls it for each search, so it can scope the rows to the user. `search_decorator` is required: pass an auth decorator such as `login_required`, or `None` for a public endpoint. The [views reference](../reference/views.md) covers the endpoint, paging, ranked search and search templates.

## Template tags

```html
{% load formwork %}

<!-- CSS link tag -->
{% formwork_css %}

<!-- JS module: core plus every widget component; load it after htmx and before Alpine -->
{% formwork_js %}

<!-- Section forms (opt-in); load it after htmx -->
{% formwork_sections_js %}

<!-- Hidden input that names the section a section form saves -->
{% formwork_section "general" %}
```
