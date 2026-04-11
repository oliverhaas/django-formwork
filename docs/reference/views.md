# Server-side Views

Formwork provides three class-based views for server-side search and validation. All are in `django_formwork.views`.

## FormworkSearchView

Base view for server-side widget search. It handles GET requests, calls `get_results()`, and returns an HTML fragment that htmx swaps into the widget's option list.

### Usage

Subclass it and implement `get_results()`:

```python
# views.py
from django_formwork.views import FormworkSearchView

class CitySearchView(FormworkSearchView):
    def get_results(self, query: str, **kwargs) -> list[dict]:
        cities = City.objects.filter(name__icontains=query)[:20]
        return [{"value": str(c.pk), "label": c.name} for c in cities]
```

```python
# urls.py
urlpatterns = [
    path("search/cities/", CitySearchView.as_view(), name="city-search"),
]
```

```python
# forms.py
from django.urls import reverse_lazy
from django_formwork.widgets import SearchSelect

city = forms.ChoiceField(
    widget=SearchSelect(search_url=reverse_lazy("city-search")),
)
```

### Result dict keys

| Key | Required | Description |
|---|---|---|
| `label` | Yes | Display text shown in the dropdown |
| `value` | For SearchSelect | Submitted form value |
| `icon` | No | Icon markup; wrap in `mark_safe()`, plain strings are auto-escaped |
| `description` | No | Secondary line of text shown below the label |

### Customising templates

The HTML fragment is rendered by one of three inline templates, selected by the `type` query parameter (sent automatically by the widget):

| Template attribute | Widget | Purpose |
|---|---|---|
| `SEARCH_SELECT_TEMPLATE` | `SearchSelect` | Value + label, with checkmark for current selection |
| `COMBOBOX_TEMPLATE` | `ComboBox` | Label only, for autocomplete suggestions |
| `MULTISELECT_TEMPLATE` | `MultiSelect` | Checkbox options that sync with Alpine.js widget state |

Override any of these as class attributes on your subclass to change the rendered markup.

### `get_total_count()`

Called once per request (before `get_results`) to determine the total number of unfiltered results. The widget uses this count to decide whether to show its search input (shown when count exceeds `search_threshold`, default 20 for `SearchSelect`).

By default `get_total_count()` calls `get_results("")` and returns `len()`. Override it if counting is cheaper than fetching:

```python
def get_total_count(self, **kwargs) -> int:
    return City.objects.count()
```

---

## FormworkAutoSearchView

A dispatch view that serves all widgets registered via the auto-registration system (widgets with `search_fields`, or forms with `search_choices_<fieldname>` methods). A single URL pattern handles every registered endpoint.

### Setup

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
]
```

This mounts one URL: `__formwork__/search/<key>/` which `FormworkAutoSearchView` handles.

### Auto-registration

Registration happens automatically when a `FormworkForm` or `FormworkModelForm` is instantiated. Two modes are supported:

**Model-backed** — The widget has `search_fields` and the field is a `ModelChoiceField` or `ModelMultipleChoiceField`. Formwork registers an endpoint that filters the queryset using `__icontains` on the listed fields:

```python
from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchSelect

class CityForm(FormworkForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        widget=SearchSelect(search_fields=["name", "country__name"]),
    )
```

**Choices-backed** — The form defines a `search_choices_<fieldname>(self, query, request)` method. It receives the search query and the request, and returns a list of dicts or `(value, label)` tuples:

```python
from django_formwork.forms import FormworkForm
from django_formwork.widgets import SearchSelect

class TagForm(FormworkForm):
    tags = forms.ChoiceField(widget=SearchSelect)

    def search_choices_tags(self, query, request):
        return [
            {"value": t.slug, "label": t.name}
            for t in Tag.objects.filter(name__icontains=query)[:20]
        ]
```

### Access control

For model-backed registrations, pass a `permission` callable to the widget:

```python
SearchSelect(
    search_fields=["name"],
    permission=lambda request: request.user.is_staff,
)
```

The view returns HTTP 403 if the callable returns `False`.

---

## FormworkValidateView

Base view for server-side textarea validation. It handles POST requests, calls `get_errors()`, and returns:

1. An HTML fragment with `<mark>` tags wrapping error spans — htmx swaps this into the `ValidatedTextarea` highlights overlay.
2. An out-of-band (`hx-swap-oob`) fragment with error messages — htmx swaps this into the error display area.

### Usage

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
# urls.py
urlpatterns = [
    path("validate/spell/", SpellCheckView.as_view(), name="spell-check"),
]
```

```python
# forms.py
from django.urls import reverse_lazy
from django_formwork.widgets import ValidatedTextarea

content = forms.CharField(
    widget=ValidatedTextarea(validate_url=reverse_lazy("spell-check")),
)
```

### Error dict keys

| Key | Required | Description |
|---|---|---|
| `message` | Yes | Error description displayed below the textarea |
| `start` | No | Start character index in the text (for highlight) |
| `end` | No | End character index in the text (for highlight) |

If `start` and `end` are both present, the text between those indices is wrapped in a `<mark>` tag in the highlights overlay. Overlapping spans are merged before rendering.

### Security note

`FormworkValidateView` is **CSRF-exempt** because it performs read-only validation — it reads text and returns highlighted output, but makes no changes to application state.

!!! warning "Do not use for side-effecting operations"
    Because the view is CSRF-exempt, do not subclass `FormworkValidateView` for any operation that writes to the database, sends emails, or has any other side effect. For operations with side effects, use a regular Django view with CSRF protection enabled.
