# Server-side Views

Formwork has two views: `FormworkSearchView` serves the server-side search of
every dropdown, and `FormworkValidateView` is the base class for a textarea
validation endpoint. Both are importable from `django_formwork` (or from
`django_formwork.views`).

## Server-side search

`Select`, `SelectMultiple`, `ComboBox` and `ComboBoxMultiple` search on the
server when the widget gets a `search_queryset`. You configure the search on
the widget; you write no URL and no view.

### Setup

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
]
```

This mounts one URL, `__formwork__/search/<key>/` (name `formwork:search`),
which `FormworkSearchView` serves for every registered search.

### Configure a widget

```python
from django.contrib.auth.decorators import login_required

from django_formwork import FormworkForm, widgets


def cities(request):
    return City.objects.filter(active=True).select_related("country")


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

| Parameter | Description |
|---|---|
| `search_queryset` | `callable(request, **params)` that returns the rows to search. The endpoint calls it for each request, so it can scope the rows to the user. |
| `search_fields` | Field paths that the query matches with `__icontains` (or ranks, with `search_ranked`). Without them the endpoint does not filter: `search_queryset` reads `request.GET["q"]` itself and returns its rows best first. |
| `search_decorator` | Required. A view decorator that wraps the endpoint, such as `login_required` or `permission_required("app.view_city")`. Pass `None` for a public endpoint. |
| `search_ranked` | Orders the rows by match quality on PostgreSQL. See [Ranked search](#ranked-search). |
| `search_key`, `search_params` | Reuse another field's search with its own params. See [Search templates](#search-templates). |
| `allow_clear` | `Select` and `SelectMultiple`: the list starts with the empty choice of an optional field (`empty_label` of a `ModelChoiceField`), so the user can clear it. |

The form registers each search when its class is created, under a stable key
built from the module, the form and the field name. Formwork imports the
`forms` module of every installed app at startup, so a search declared there
exists in every worker before the first request. A form defined elsewhere
registers when its module is first imported. Registration raises
`ImproperlyConfigured` for a widget without `search_decorator`, for
`search_fields` without `search_queryset`, and for `search_ranked` without
`search_fields` or outside PostgreSQL.

The endpoint renders each row with `label_from_instance` of the field, so a
[`ChoiceLabel`](widgets.md#choicelabel) adds an icon, a description or a
trigger class to the results. A `ComboBox` over a `CharField` takes its own
`label_from_instance=` and falls back to `str()`.

### Paging

The widget renders the first 20 rows itself, plus the selected rows that lie
past them. A search returns the next 20 matches at most. When more exist, the
list ends with a hint and a "Load more" button that fetches the next page. The
endpoint fetches one row past the page to tell whether more exist, so it never
runs a `COUNT`. The first "Load more" request excludes the selected rows that
the widget already shows past the first page.

With static choices and no `search_queryset`, the widget filters in the
browser. It shows the search box past `search_threshold` (10) options, or when
`show_search=True`.

### Access control

`search_decorator` wraps `FormworkSearchView.dispatch` for that search.
Formwork refuses to expose a search without an explicit decision, so omitting
it raises `ImproperlyConfigured`:

```python
from django.contrib.auth.decorators import login_required, permission_required

widgets.Select(search_queryset=cities, search_fields=["name"], search_decorator=login_required)
widgets.Select(
    search_queryset=cities,
    search_fields=["name"],
    search_decorator=permission_required("geo.view_city"),
)
widgets.Select(search_queryset=cities, search_fields=["name"], search_decorator=None)  # public
```

A request for an unknown key from an anonymous user redirects to
`settings.LOGIN_URL` when `django.contrib.auth` is installed, so the response
does not tell a missing key from a protected one. Otherwise an unknown key
returns 404. Queries longer than `FormworkSearchView.MAX_QUERY_LENGTH` (200)
characters are truncated.

`FormworkSearchView` is final: configure a search through the widget, not by
subclassing the view.

### Ranked search

`search_ranked=True` orders the rows by how well they match, and matches typos
too. It needs PostgreSQL with the `pg_trgm` extension, and at least one
`search_fields` entry.

```python
widgets.Select(
    search_queryset=cities,
    search_fields=["name"],
    search_ranked=True,
    search_decorator=login_required,
)
```

Rows that contain the query come first, then typo matches. Within each group,
whole-word matches rank above partial ones, and the closest value comes first.
A query shorter than 3 characters has too few trigrams to rank by, so it ranks
exact matches first, then prefix matches, then the other rows that contain the
query.

A GIN trigram index on `UPPER(field::text)` per search field serves every
lookup of the ranked search and of plain `__icontains`:

```python
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import TextField
from django.db.models.functions import Cast, Upper


class City(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        indexes = [
            GinIndex(
                OpClass(Upper(Cast("name", output_field=TextField())), name="gin_trgm_ops"),
                name="city_name_trgm",
            ),
        ]
```

Create the extension in a migration with
`django.contrib.postgres.operations.TrigramExtension()`. Without
`search_ranked`, `__icontains` runs as `LIKE '%query%'`; the leading wildcard
rules out a B-tree index, so a large table needs the same trigram index.

`ranked_search(queryset, fields, query)` in `django_formwork.search` applies
the same ordering to any queryset.

### Search templates

A form that builds fields in `__init__` (one field per group, for example)
reuses one registered search with its own params. Declare a template field
whose `search_queryset` takes keyword-only `int` or `str` params after the
request, then pass its `search_key` and the params to the fields you build:

```python
def group_members(request, *, group: int):
    return User.objects.filter(groups=group)


class TeamForm(FormworkForm):
    members_template = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=widgets.SelectMultiple(
            search_queryset=group_members,
            search_fields=["email"],
            search_decorator=login_required,
        ),
    )

    def __init__(self, *args, groups, **kwargs):
        super().__init__(*args, **kwargs)
        key = self.fields.pop("members_template").widget.search_key
        for group in groups:
            self.fields[f"group_{group.pk}"] = forms.ModelMultipleChoiceField(
                queryset=User.objects.filter(groups=group),
                widget=widgets.SelectMultiple(search_key=key, search_params={"group": group.pk}),
            )
```

The params travel in the search URL, and the endpoint converts them to the
declared type before it calls `search_queryset`. The widget raises
`ImproperlyConfigured` when the params do not match the declared names, and a
param cannot take a name the endpoint reads itself (`q`, `offset`, `exclude`,
`widget`, `allow_clear`). A user can edit the params in the URL, so
`search_queryset` must return only rows that the requesting user is allowed to see,
whatever the params say.

---

## FormworkValidateView

Base view for server-side textarea validation. It handles POST requests, calls `get_errors()`, and returns:

1. An HTML fragment with `<mark>` tags wrapping error spans: htmx swaps this into the `ValidatedTextarea` highlights overlay.
2. An out-of-band (`hx-swap-oob`) fragment with error messages: htmx swaps this into the error display area.

### Usage

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

### Access control

Like the search side's `search_decorator`, the view exposes a `validate_decorator` hook. Set it on your subclass to wrap `dispatch` with a standard Django auth decorator:

```python
from django.contrib.auth.decorators import login_required


class SpellCheckView(FormworkValidateView):
    validate_decorator = login_required
```

`None` (the default) leaves the endpoint public. A real subclass doing expensive work (spellcheck, LLM calls, database lookups) should set a decorator so it doesn't ship an unauthenticated, unrate-limited endpoint.

### `MAX_TEXT_LENGTH`

Text longer than `MAX_TEXT_LENGTH` characters (default `50_000`) is truncated before being passed to `get_errors()`, mirroring `MAX_QUERY_LENGTH` on the search side. Override the class attribute to change the limit.

### Security note

`FormworkValidateView` is **CSRF-exempt** because it performs read-only validation: it reads text and returns highlighted output, but makes no changes to application state.

!!! warning "Do not use for side-effecting operations"
    Because the view is CSRF-exempt, do not subclass `FormworkValidateView` for any operation that writes to the database, sends emails, or has any other side effect. For operations with side effects, use a regular Django view with CSRF protection enabled.
