# Server-side Views

Formwork provides three class-based views for server-side search and validation. All are in `django_formwork.views`.

## FormworkSearchView

Base view for the registry-driven search endpoint. `FormworkAutoSearchView` (below) inherits from it and serves every auto-registered widget; you'd subclass `FormworkSearchView` directly only if you want to render the formwork response templates (the `<li>` fragments that htmx swaps in) from a custom endpoint of your own — e.g. for a non-formwork widget that reuses the same look.

### Response templates

The HTML fragment is rendered by one of three class-level Django templates, selected by the `type` query parameter the widget sends:

| Template attribute | Widget | Purpose |
|---|---|---|
| `SEARCH_SELECT_TEMPLATE` | `SearchSelect` | Value + label, with checkmark for current selection |
| `COMBOBOX_TEMPLATE` | `ComboBox` | Label only, for autocomplete suggestions |
| `MULTISELECT_TEMPLATE` | `MultiSelect` | Checkbox options that sync with Alpine.js widget state |

Override any of these on your subclass to change the rendered markup. Implementing `get_results(query, **kwargs)` is the per-request hook.

### Result dict keys

| Key | Required | Description |
|---|---|---|
| `label` | Yes | Display text shown in the dropdown |
| `value` | For SearchSelect / MultiSelect | Submitted form value |
| `icon` | No | Icon markup; wrap in `mark_safe()`, plain strings are auto-escaped |
| `description` | No | Secondary line of text shown below the label |

### `MAX_QUERY_LENGTH`

Queries longer than `MAX_QUERY_LENGTH` (default `200`) are truncated before being passed to `get_results()`. Override the class attribute to change the limit.

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

Auto-registered endpoints require a `search_decorator` on the widget. Omitting it raises `ImproperlyConfigured` — formwork refuses to silently expose an unauthenticated search endpoint.

Pass a standard Django auth decorator:

```python
from django.contrib.auth.decorators import login_required, permission_required

# Require login:
SearchSelect(
    search_fields=["name"],
    search_decorator=login_required,
)

# Require a specific permission:
SearchSelect(
    search_fields=["name"],
    search_decorator=permission_required("myapp.view_city"),
)
```

To explicitly allow unauthenticated access (public endpoint), pass `None`:

```python
SearchSelect(
    search_fields=["name"],
    search_decorator=None,  # public — no auth required
)
```

The decorator wraps `FormworkAutoSearchView.dispatch` for that endpoint.

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
