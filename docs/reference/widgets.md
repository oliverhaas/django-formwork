# Widget Reference

All widgets are in `django_formwork.widgets` and can be imported directly:

```python
from django_formwork.widgets import Toggle, Range, Rating, ...
```

DaisyUI component-layer classes (`alert-error`, `btn`, etc.) appear directly in widget templates. Only the utility-layer DaisyUI classes (`.input`, `.select`) are applied via `@apply` in `formwork.css`, because they live in `@layer utilities` and would otherwise beat user component-layer overrides. For built-in Django widgets (text input, select, etc.) we don't override the template; CSS selectors in `formwork.css` handle the styling.

---

## Color variants

Every form-control widget accepts DaisyUI color modifiers through its `class` attr,
and this works identically on the custom widgets that are not real `<select>`
elements (`SearchSelect` and `MultiSelect` render a `<details>/<summary>`, `ComboBox`
renders a text `<input>`). The modifiers are safelisted in `formwork.css`, so they
compile even though the class is injected at render time and never appears in a
template that Tailwind scans.

**Which base does each widget use?** The color/soft class is keyed to the underlying
DaisyUI base, not the widget name:

| Base | Widgets | Example class |
|---|---|---|
| `select-*` | `SearchSelect`, `MultiSelect`, native `<select>` | `select-accent`, `select-soft` |
| `input-*` | `ComboBox`, `DataList`, native text inputs | `input-accent`, `input-soft` |
| `textarea-*` | `ValidatedTextarea`, native `<textarea>` | `textarea-accent`, `textarea-soft` |

`ComboBox` is an `.input`, so it takes `input-accent` / `input-soft`, not the
`select-` prefix, even though it behaves like a select.

### Border color (DaisyUI built-in)

The eight DaisyUI colors tint the control's border:

```python
from django_formwork.widgets import SearchSelect

city = forms.ChoiceField(
    widget=SearchSelect(attrs={"class": "select-accent"}),
    choices=CITIES,
)
```

### Soft fill (`-soft`)

`formwork.css` adds a `-soft` variant (DaisyUI ships none for form controls) that
colors the whole control: a light tinted background with colored text, mirroring
DaisyUI's `btn-soft` / `alert-soft` look. It **composes** with the color modifiers:

```python
# Accent-tinted fill with accent text:
widget=SearchSelect(attrs={"class": "select-soft select-accent"})

# ComboBox uses the input base:
widget=ComboBox(attrs={"class": "input-soft input-accent"})
```

`-soft` also follows the validation state automatically: an `aria-invalid` control
(or an explicit `select-error`) renders a red-tinted fill, because both the error
state and `-soft` flow through the same `--input-color` variable. Used on its own
(no color modifier), `-soft` gives a readable neutral fill.

---

## Floating labels

**Widgets:** `TextInput`, `Select`, `Textarea`

Pass `floating_label=True` to reuse a control's placeholder as a
[DaisyUI floating label](https://daisyui.com/components/floating-label/): the
placeholder text sits inside the control when empty and floats above it on
focus/fill. The widget wraps the control in `<label class="floating-label">` with
a `<span>` carrying the label text; that wrapping label plus span becomes the
control's accessible name, so the redundant field legend is hidden via CSS.

These three widgets are drop-in replacements for Django's own `forms.TextInput`,
`forms.Select`, and `forms.Textarea`, so import them from `django_formwork.widgets`
(they intentionally shadow the stock names). With `floating_label=False` (the
default) they render identically to the stock widgets.

```python
from django_formwork.widgets import Select, TextInput, Textarea

nickname = forms.CharField(
    widget=TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
)
note = forms.CharField(
    widget=Textarea(attrs={"placeholder": "Note"}, floating_label=True),
)
# For a <select>, the placeholder is used only as the floating label text
# (it is not a valid <select> attribute, so it is stripped from the element).
# Supply an empty first choice for the in-field blank state.
role = forms.ChoiceField(
    choices=[("", ""), ("admin", "Admin"), ("user", "User")],
    widget=Select(attrs={"placeholder": "Role"}, floating_label=True),
)
```

---

## Toggle

**Parent class:** `forms.CheckboxInput`

Checkbox rendered as a DaisyUI toggle switch. Adds the `toggle` CSS class so `formwork.css` applies toggle styling instead of the default checkbox styling.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<input>` element |

### Usage

```python
agree = forms.BooleanField(widget=Toggle)

# With extra attrs:
dark_mode = forms.BooleanField(widget=Toggle(attrs={"class": "toggle-primary"}))
```

---

## Range

**Parent class:** `forms.NumberInput`

HTML5 range slider. Sets `input_type = "range"` — CSS targets `input[type="range"]` directly. No extra attributes needed beyond standard HTML range attrs.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes, e.g. `min`, `max`, `step` |

### Usage

```python
volume = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100}))
brightness = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100, "step": 5}))
```

---

## Rating

**Parent class:** `forms.RadioSelect`

Star-rating widget using DaisyUI's rating component. Renders a `<div class="rating">` containing radio inputs styled as stars.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes passed to radio inputs |
| `star_class` | `str` | `"mask-star-2"` | DaisyUI mask class for the star shape |
| `allow_clear` | `bool` | `False` | Add a hidden first radio to allow clearing the selection |

### Class methods

**`Rating.make_choices(max_stars=5)`** — Returns a choices list `[("1", "1 star"), ("2", "2 stars"), ...]` for use with `TypedChoiceField`. Use this instead of defining choices manually — `Rating.choices` is a reserved property name on `ChoiceWidget`.

### Usage

```python
rating = forms.TypedChoiceField(
    choices=Rating.make_choices(5),
    coerce=int,
    widget=Rating,
)

# Custom star shape with clear button:
score = forms.TypedChoiceField(
    choices=Rating.make_choices(5),
    coerce=int,
    widget=Rating(star_class="mask-heart", allow_clear=True),
)
```

---

## PasswordReveal

**Parent class:** `forms.PasswordInput`

Password input with a show/hide toggle button. Wraps the input in a `<label class="password-reveal">` container with a toggle button powered by Alpine.js. DaisyUI's `.input` styling is applied via CSS `@apply` on the label, not on the input element itself.

The value is never rendered back into the field (`render_value=False`), following Django's default password input behaviour.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<input>` element |

### Usage

```python
password = forms.CharField(widget=PasswordReveal)
```

**Requires Alpine.js** to be loaded on the page.

---

## MultiSelect

**Parent class:** `forms.SelectMultiple`

Multi-select dropdown with checkboxes. Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes. Uses Alpine.js for open/close state and selected-count display. Submitted values are tracked in Alpine state and sent via hidden inputs.

When `search_fields` is provided (or the form defines `search_choices_<fieldname>`), an htmx-powered search endpoint is auto-registered. See [server-side search](views.md#formworkautosearchview).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `choices` | `tuple` | `()` | Initial choices |
| `show_search` | `bool \| None` | `None` | Force show/hide search input; `None` = auto (shows when ≥20 options or a registry search endpoint is wired) |
| `search_fields` | `Sequence[str] \| None` | `None` | Model field paths for auto-registration (e.g. `["name", "country__name"]`) |
| `search_decorator` | `Callable \| None` | *(required if `search_fields` is set)* | Auth decorator for the auto-registered endpoint (see note below) |

`FormworkModelMultipleChoiceField` adds optional `icon_from_instance` and `description_from_instance` callbacks for model-backed dropdowns.

### Usage

```python
# Static choices:
languages = forms.MultipleChoiceField(
    choices=[("py", "Python"), ("js", "JavaScript")],
    widget=MultiSelect,
)

# Auto-registered server-side search (model queryset):
class TagForm(FormworkForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=MultiSelect(
            search_fields=["name"],
            search_decorator=login_required,
        ),
    )

# Auto-registered server-side search (custom callback):
class LangForm(FormworkForm):
    languages = forms.MultipleChoiceField(widget=MultiSelect)

    def search_choices_languages(query, request):
        return [{"value": k, "label": v} for k, v in _langs(query)]
```

**Requires Alpine.js and htmx** (for server-side search).

---

## SearchSelect

**Parent class:** `forms.Select`

Single-select dropdown with text search/filter. Renders a DaisyUI-styled dropdown with a search input. Submits a single key value via a hidden `<input>` element.

This is a `<select>` replacement — the submitted value is a key from the choices list, not free text.

When `search_fields` is provided (or the form defines `search_choices_<fieldname>`), an htmx-powered search endpoint is auto-registered. See [server-side search](views.md#formworkautosearchview).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `choices` | `tuple` | `()` | Initial choices |
| `show_search` | `bool \| None` | `None` | Force show/hide search input; `None` = auto (shows when ≥20 options) |
| `search_fields` | `Sequence[str] \| None` | `None` | Model field paths for auto-registration |
| `search_decorator` | `Callable \| None` | *(required if `search_fields` is set)* | Auth decorator for the auto-registered endpoint (see note below) |

For icons/descriptions on choice labels, wrap the label in [`ChoiceLabel`](https://github.com/oliverhaas/django-formwork/blob/main/django_formwork/fields.py); for model-backed widgets, use `FormworkModelChoiceField` and pass `icon_from_instance` / `description_from_instance`.

`ChoiceLabel` also carries a `selected_toggle_class`: a free-form CSS class string that the widget moves onto the closed trigger (the `<summary>` box) whenever that option is the selected one. It is applied on the server-rendered initial value, restored after a validation error, and swapped client-side when the user picks a different option, with no round-trip. The library relays the string verbatim; it never interprets, validates, or restricts it, so any class works (a DaisyUI `select-*` color, a utility, or your own class). For model-backed widgets, pass `selected_toggle_class_from_instance` to `FormworkModelChoiceField`.

### Usage

```python
# Static choices with icons:
from django.utils.html import mark_safe
from django_formwork import ChoiceLabel

city = forms.ChoiceField(
    choices=[
        ("nyc", ChoiceLabel("New York", icon=mark_safe("<span>🗽</span>"))),
        ("ldn", "London"),
    ],
    widget=SearchSelect,
)

# Recolor the closed box by the selected option:
priority = forms.ChoiceField(
    choices=[
        ("low", ChoiceLabel("Low", selected_toggle_class="select-success")),
        ("mid", ChoiceLabel("Medium", selected_toggle_class="select-warning")),
        ("high", ChoiceLabel("High", selected_toggle_class="select-error")),
    ],
    widget=SearchSelect,
)

# Auto-registered server-side search (model queryset):
class CityForm(FormworkForm):
    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        widget=SearchSelect(
            search_fields=["name", "country__name"],
            search_decorator=login_required,
        ),
    )
```

#### Making the class available to Tailwind

The class you pass in `selected_toggle_class` only styles the trigger if it exists in your compiled CSS. DaisyUI v5 (and Tailwind) generate rules on demand, so an arbitrary class exists only when Tailwind sees the token.

- **DaisyUI `select-*` colors** (the `priority` example above) need nothing extra: `formwork.css` already safelists every `{select,input,textarea}-{color}` modifier, so `select-success` / `select-warning` / `select-error` are guaranteed to compile in any app that imports it. This is the same library safelist behind [Color variants](#color-variants).
- **Other literal class names** written out in full in Tailwind-scanned source (a template, a `views.py`, a form definition) are picked up automatically by the content scan. No safelist needed as long as the exact token appears somewhere Tailwind reads.
- **Interpolated or computed class names**, where the full token never appears in source (e.g. `f"select-{level}"` or a `badge-{{ status }}` template expression), are invisible to the content scan. Only these need a safelist: add them to your app's Tailwind entrypoint with `@source inline("...")`, the same way `badge-*` colors are safelisted elsewhere in this codebase.

**Requires Alpine.js and htmx** (for server-side search).

---

## ComboBox

**Parent class:** `forms.TextInput`

Text input with autocomplete suggestions. The submitted value is whatever the user typed (free text), not a key from a list — suggestions are hints only.

In multiple mode (`multiple=True`), accepts comma-separated values and filters suggestions for the segment currently being typed.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `suggestions` | `list[str] \| list[tuple[str, list[str]]] \| None` | `None` | Static suggestions, either flat or grouped as `(group, items)` |
| `multiple` | `bool` | `False` | Accept comma-separated values; suggestions filter per segment |
| `icons` | `dict[str, str] \| None` | `None` | Map of `suggestion text → icon HTML` |
| `descriptions` | `dict[str, str] \| None` | `None` | Map of `suggestion text → description text` |
| `search_decorator` | `Callable \| None` | *(required if the form provides `search_choices_<fieldname>`)* | Auth decorator for the auto-registered endpoint |

### Usage

```python
# Static suggestions:
tags = forms.CharField(
    widget=ComboBox(suggestions=["Python", "JavaScript", "Go"]),
)

# Multiple mode:
tags = forms.CharField(
    widget=ComboBox(
        suggestions=["pizza", "pasta", "sushi"],
        multiple=True,
    ),
)

# Auto-registered server-side suggestions:
class TagForm(FormworkForm):
    tags = forms.CharField(widget=ComboBox(search_decorator=login_required))

    def search_choices_tags(query, request):
        return [{"label": t.name} for t in Tag.objects.filter(name__icontains=query)[:20]]
```

**Requires Alpine.js** and htmx (for server-side suggestions).

---

## DataList

**Parent class:** `forms.TextInput`

Text input with native `<datalist>` browser suggestions. No JavaScript required — the browser provides the autocomplete dropdown natively.

The submitted value is free text typed by the user, not a key from the list.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `datalist` | `list[str] \| None` | `None` | Suggestion strings rendered in the `<datalist>` element |

### Usage

```python
browser = forms.CharField(
    widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
)
```

No JavaScript dependencies.

---

## FileDropZone

**Parent class:** `forms.FileInput`

Drag-and-drop file upload zone. Replaces the standard file input with a styled drop zone that accepts dragged files or click-to-browse. Uses Alpine.js for drag state and file list display.

Client-side file size validation is performed when `max_size` is set — oversized files are rejected before upload.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes, e.g. `accept`, `multiple` |
| `max_size` | `int \| None` | `None` | Maximum file size in bytes; client-side only |

### Usage

```python
# Single file:
attachment = forms.FileField(widget=FileDropZone)

# Multiple files with type and size restrictions:
docs = forms.FileField(
    widget=FileDropZone(
        attrs={"multiple": True, "accept": ".pdf,.doc,.docx"},
        max_size=10 * 1024 * 1024,  # 10 MB
    ),
)
```

**Requires Alpine.js.**

!!! note "Server-side validation"
    `max_size` only blocks uploads in the browser. Always validate file size server-side as well.

---

## ImageDropZone

**Parent class:** `forms.FileInput`

Drag-and-drop image upload with thumbnail preview. Like `FileDropZone` but restricted to images (`accept="image/*"` by default) and shows a preview thumbnail after selection using `FileReader`.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes; merged over `{"accept": "image/*"}` |
| `max_size` | `int \| None` | `None` | Maximum file size in bytes; client-side only |

### Usage

```python
avatar = forms.ImageField(widget=ImageDropZone)

# With size limit:
photo = forms.ImageField(
    widget=ImageDropZone(max_size=5 * 1024 * 1024),  # 5 MB
)
```

**Requires Alpine.js.**

!!! note "Server-side validation"
    `max_size` only blocks uploads in the browser. Always validate file size server-side as well.

---

## DatePicker

**Parent class:** `forms.DateInput`

Text input with an Alpine.js calendar dropdown. Submits a date string in `YYYY-MM-DD` format.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<input>` element |
| `format` | `str \| None` | `"%Y-%m-%d"` | Output format passed to `DateInput` |

### Usage

```python
due_date = forms.DateField(widget=DatePicker)
```

**Requires Alpine.js.**

---

## InputNumber

**Parent class:** `forms.NumberInput`

Number input with increment/decrement buttons. Wraps `<input type="number">` with +/- buttons; Alpine.js drives the stepping.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes, e.g. `min`, `max`, `step` |

### Usage

```python
quantity = forms.IntegerField(widget=InputNumber(attrs={"min": "1", "max": "99"}))
```

**Requires Alpine.js.**

---

## InputMask

**Parent class:** `forms.TextInput`

Text input with a fixed-format mask. Alpine.js enforces the pattern as the user types. Mask tokens: `#` = digit, `A` = letter, `*` = any character.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<input>` element |
| `mask` | `str` | `""` | Mask pattern, e.g. `"(###) ###-####"` |

### Usage

```python
phone = forms.CharField(widget=InputMask(mask="(###) ###-####"))
zip_code = forms.CharField(widget=InputMask(mask="#####"))
```

**Requires Alpine.js.**

---

## OTPInput

**Parent class:** `forms.TextInput`

One-time password / PIN code input. Renders N single-character inputs that auto-advance on typing; the submitted value is the concatenated string.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the per-character `<input>` elements |
| `length` | `int` | `6` | Number of single-character inputs |

### Usage

```python
code = forms.CharField(widget=OTPInput(length=6))
```

**Requires Alpine.js.**

---

## ValidatedTextarea

**Parent class:** `forms.Textarea`

Textarea with server-side validation and word highlighting. When `validate_url` is provided, htmx sends the text to the server after a debounce. The server returns highlighted HTML (with `<mark>` tags around errors) that overlays the textarea, plus error messages via out-of-band swap.

Without `validate_url`, renders as a normal textarea.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<textarea>` element |
| `validate_url` | `str \| None` | `None` | URL for the server-side `FormworkValidateView` subclass |

### Usage

```python
content = forms.CharField(
    widget=ValidatedTextarea(validate_url=reverse_lazy("spell-check")),
)
```

See [`FormworkValidateView`](views.md#formworkvalidateview) for implementing the server-side view.

Server-side validation errors (from `validate_url`) always render in the
widget's own built-in tooltip, regardless of the form's
[`error_display`](forms.md#error_display) setting. On `error_display =
"inline"` forms, a field-level validation error (e.g. `required`) still
renders inline below the widget as usual, so the two error surfaces can
appear at the same time. There's no fix planned; avoid pairing
`ValidatedTextarea` with `error_display = "inline"` if that overlap matters
for your layout.

**Requires htmx.**

---

## `search_decorator` parameter

`SearchSelect`, `MultiSelect`, and `ComboBox` accept a `search_decorator` parameter that protects the auto-registered endpoint. It's required as soon as a registration path is in use — either `search_fields` on the widget, or `search_choices_<fieldname>` on the form. Omitting it raises `ImproperlyConfigured` at registration time; formwork refuses to silently expose an unauthenticated search endpoint.

```python
from django.contrib.auth.decorators import login_required, permission_required

# Require login:
widget=SearchSelect(
    search_fields=["name"],
    search_decorator=login_required,
)

# Require a specific permission:
widget=SearchSelect(
    search_fields=["name"],
    search_decorator=permission_required("myapp.view_city"),
)

# Public endpoint (explicit opt-in):
widget=SearchSelect(
    search_fields=["name"],
    search_decorator=None,
)
```

The decorator is applied to the `FormworkAutoSearchView.dispatch` method for each registered endpoint. To skip auto-registration entirely and write your own endpoint, see [`FormworkSearchView`](views.md#formworksearchview).
