# Widget Reference

All widgets are in `django_formwork.widgets`. Their names follow Django's and
shadow `django.forms` on purpose, so import the module:

```python
from django import forms

from django_formwork import widgets

country = forms.ChoiceField(choices=[("de", "Germany"), ("fr", "France")], widget=widgets.Select)
```

`TextInput`, `Textarea`, `PasswordInput`, `DateInput`, `CheckboxInput`,
`CheckboxSelectMultiple`, `Select` and `SelectMultiple` are drop-ins for the
Django widgets of the same name: validation is unchanged. Formwork never
overrides a built-in widget template, so Django's own widgets keep their
markup and get their DaisyUI look from `formwork.css`.

DaisyUI component-layer classes (`alert`, `btn`, `loading`, `dropdown-content`) appear directly in
widget templates. Only the utility-layer DaisyUI classes (`.input`, `.select`)
are applied via `@apply` in `formwork.css`, because they live in
`@layer utilities` and would otherwise beat user component-layer overrides.

---

## Color variants

Every form-control widget accepts DaisyUI color modifiers through its `class`
attr. This works the same on the widgets that are not real `<select>` elements
(`Select` and `SelectMultiple` render a `<details>`/`<summary>`, `ComboBox`
renders a text `<input>`). The modifiers are safelisted in `formwork.css`, so
they compile even though the class is injected at render time and never appears
in a template that Tailwind scans.

The color class is keyed to the underlying DaisyUI base, not the widget name:

| Base | Widgets | Example class |
|---|---|---|
| `select-*` | `Select`, `SelectMultiple`, native `<select>` | `select-accent`, `select-soft` |
| `input-*` | `ComboBox`, `TextInput`, `DataList`, native text inputs | `input-accent`, `input-soft` |
| `textarea-*` | `Textarea`, `ValidatedTextarea`, native `<textarea>` | `textarea-accent`, `textarea-soft` |

`ComboBox` is an `.input`, so it takes `input-accent` / `input-soft`, not the
`select-` prefix, even though it behaves like a select.

### Border color (DaisyUI built-in)

The eight DaisyUI colors tint the control's border:

```python
city = forms.ChoiceField(
    widget=widgets.Select(attrs={"class": "select-accent"}),
    choices=CITIES,
)
```

### Soft fill (`-soft`)

`formwork.css` adds a `-soft` variant (DaisyUI ships none for form controls)
that colors the whole control: a light tinted background with colored text,
mirroring DaisyUI's `btn-soft` / `alert-soft` look. It composes with the color
modifiers:

```python
widgets.Select(attrs={"class": "select-soft select-accent"})
widgets.ComboBox(attrs={"class": "input-soft input-accent"})
```

`-soft` also follows the validation state: an `aria-invalid` control (or an
explicit `select-error`) renders a red-tinted fill, because both the error state
and `-soft` flow through the same `--input-color` variable. Used on its own (no
color modifier), `-soft` gives a readable neutral fill.

---

## Floating labels

**Widgets:** `TextInput`, `Textarea`, `PasswordInput`, `Select`, `SelectMultiple`

Pass `floating=True` to reuse a control's placeholder as a
[DaisyUI floating label](https://daisyui.com/components/floating-label/): the
placeholder text sits inside the control when empty and floats above it on
focus or fill. The widget wraps the control in `<label class="floating-label">`
with a `<span>` that carries the label text, and that wrapper becomes the
accessible name, so CSS hides the redundant field legend. A floating widget
without a `placeholder` raises `ImproperlyConfigured`.

```python
nickname = forms.CharField(
    widget=widgets.TextInput(attrs={"placeholder": "Nickname"}, floating=True),
)
note = forms.CharField(
    widget=widgets.Textarea(attrs={"placeholder": "Note"}, floating=True),
)
role = forms.ChoiceField(
    choices=[("", ""), ("admin", "Admin"), ("user", "User")],
    widget=widgets.Select(attrs={"placeholder": "Role"}, floating=True),
)
```

On a select, the label always floats above the trigger.

---

## ChoiceLabel

`ChoiceLabel` is a choice label whose `str()` is its text. The extras are
presentation only, so validation and `cleaned_data` see a plain label. It is
importable from `django_formwork` and from `django_formwork.widgets`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `label` | `str` | | The option text |
| `icon` | `str` | `""` | HTML before the text; mark it safe |
| `description` | `str` | `""` | A second line under the text |
| `label_html` | `str` | `""` | HTML that replaces the text in the row and the trigger; mark it safe |
| `color` | `BadgeColor` | `"neutral"` | Badge color in `Display(badges=True)`: one of the eight DaisyUI colors |
| `selected_toggle_class` | `str` | `""` | Classes that `Select` puts on its closed trigger while this option is selected |

Use it in `choices`, or return it from `label_from_instance` for a model field:

```python
from django.utils.html import format_html

from django_formwork import ChoiceLabel


priority = forms.ChoiceField(
    choices=[
        ("low", ChoiceLabel("Low", selected_toggle_class="select-success")),
        ("mid", ChoiceLabel("Medium", selected_toggle_class="select-warning")),
        ("high", ChoiceLabel("High", selected_toggle_class="select-error")),
    ],
    widget=widgets.Select,
)


class MemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return ChoiceLabel(
            obj.name,
            icon=format_html('<span class="badge badge-ghost badge-sm">{}</span>', obj.initials),
            description=obj.email,
        )
```

`selected_toggle_class` applies on the first render, after a validation error,
and on every pick in the browser, with no round-trip. Formwork passes the
string through unchanged, so any class works.

The class only styles the trigger if it exists in your compiled CSS.
`formwork.css` safelists every `{select,input,textarea}-{color}` and
`badge-{color}` class. A literal class name in a template or a Python file that
Tailwind scans compiles too. A class name that your code builds at render time
(`f"select-{level}"`) needs an `@source inline("...")` line in your Tailwind
entry point.

---

## Dropdowns

### Select

**Parent class:** `forms.Select`

Single-select dropdown: a `<details>`/`<summary>` trigger with a popover panel.
A hidden input posts the value, so the submitted value is a key from the
choices. The panel is at most 288px tall and scrolls. The trigger shows
DaisyUI's caret, the selected option's icon, and "Select…" while nothing is
selected. A disabled field greys the trigger out.

A search box appears past `search_threshold` (10) options and filters the list
in the browser. With a `search_queryset`, the widget searches on the server
instead; see [Server-side search](views.md#server-side-search).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes; `class` goes on the trigger |
| `choices` | iterable | `()` | Choices, as for `forms.Select` |
| `show_search` | `bool \| None` | `None` | `True` or `False` forces the search box; `None` shows it past the threshold or when the list is truncated |
| `show_spinner` | `bool` | `True` | Spinner in the search box during a server search |
| `allow_clear` | `bool` | `False` | Offer the empty choice as a row that clears the value |
| `floating` | `bool` | `False` | [Floating label](#floating-labels) |
| `search_queryset` | `callable \| None` | `None` | `callable(request, **params)` that returns the rows to search |
| `search_fields` | `Sequence[str] \| None` | `None` | Field paths the query matches |
| `search_decorator` | `callable \| None` | required with `search_queryset` | Access rule for the search; `None` for a public endpoint |
| `search_ranked` | `bool` | `False` | Rank the results on PostgreSQL |
| `search_key`, `search_params` | | `None` | Reuse a registered search with its own params |

```python
city = forms.ChoiceField(choices=CITIES, widget=widgets.Select)

assignee = MemberChoiceField(
    queryset=Member.objects.all(),
    required=False,
    empty_label="Unassigned",
    widget=widgets.Select(
        search_queryset=lambda request: Member.objects.all(),
        search_fields=["name", "email"],
        search_decorator=login_required,
        allow_clear=True,
    ),
)
```

Option groups render as headings. For a domain choice set, such as a country
select with flag icons, subclass `Select` in your project and set the choices;
formwork ships no domain widgets.

### SelectMultiple

**Parent class:** `forms.SelectMultiple`

Multi-select dropdown with a checkbox per option. It takes every parameter of
`Select`, plus `open_icon`. The closed trigger lists the selected labels with
their icons. Past `summary_threshold` (3) selections it shows a count ("4
selected") instead. With a server search, hidden inputs post the selected
values, because the list holds only one page.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `open_icon` | `str \| None` | `None` | A Lucide icon name that replaces DaisyUI's caret on the trigger |

```python
languages = forms.MultipleChoiceField(
    choices=[("py", "Python"), ("js", "JavaScript")],
    widget=widgets.SelectMultiple,
)

tags = forms.ModelMultipleChoiceField(
    queryset=Tag.objects.all(),
    required=False,
    widget=widgets.SelectMultiple(
        search_queryset=lambda request: Tag.objects.all(),
        search_fields=["name"],
        search_decorator=login_required,
    ),
)
```

### ComboBox

**Parent class:** `forms.TextInput`

Text input with a suggestion dropdown. The submitted value is whatever the user
typed; the suggestions are hints.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the `<input>` |
| `suggestions` | sequence | `None` | Strings or `ChoiceLabel`s, flat or grouped as `[(group, [...])]` |
| `show_spinner` | `bool` | `True` | Spinner during a server search |
| `search_queryset`, `search_fields`, `search_decorator`, `search_ranked`, `search_key`, `search_params` | | | As on `Select`; the search fills the list on first focus and on typing |
| `label_from_instance` | `callable \| None` | `None` | Turns a searched row into the suggestion label when the field has no `label_from_instance` of its own, as on a `CharField`; `str()` otherwise |

```python
food = forms.CharField(
    widget=widgets.ComboBox(
        suggestions=[
            ChoiceLabel("Pizza", icon=PIZZA_ICON),
            "Pasta",
            ("Asian", ["Sushi", "Ramen", "Curry"]),
        ],
    ),
)
```

A picked suggestion's icon shows beside the text in the closed input.

### ComboBoxMultiple

**Parent class:** `ComboBox`

`ComboBox` for comma-separated free text. The suggestions apply to the segment
that the user types.

```python
tags = forms.CharField(widget=widgets.ComboBoxMultiple(suggestions=["pizza", "pasta", "sushi"]))
```

---

## Text

### TextInput

**Parent class:** `forms.TextInput`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `floating` | `bool` | `False` | [Floating label](#floating-labels) |
| `input_type` | `str` | `"text"` | The text-like type: `email`, `tel`, `url`, and so on |

`TextInput` mixes in [`PatternHintMixin`](#patternhintmixin).

### Textarea

**Parent class:** `forms.Textarea`. Takes `attrs` and `floating`.

### PasswordInput

**Parent class:** `forms.PasswordInput`

Password input with a button that shows the typed text.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `render_value` | `bool` | `False` | As on `forms.PasswordInput` |
| `floating` | `bool` | `False` | [Floating label](#floating-labels) |
| `reveal` | `bool` | `True` | `False` drops the show button |

### SearchInput

**Parent class:** `forms.TextInput`, with `input_type = "search"`

Search field with a leading magnifier, an htmx spinner while a request runs,
and a clear button. The default placeholder is "Search...".

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes |
| `show_spinner` | `bool` | `True` | Swap the magnifier for a spinner during an htmx request |
| `show_clear` | `bool` | `True` | Show the clear button |
| `filter_items` | `str` | `""` | CSS selector: typing hides the matching rows whose `data-label` misses the query |

```python
q = forms.CharField(
    required=False,
    widget=widgets.SearchInput(filter_items="#task-list [data-label]"),
)
```

### DataList

**Parent class:** `forms.TextInput`

Text input with native `<datalist>` suggestions. The browser draws the list, so
it needs no JavaScript. The submitted value is free text.

```python
browser = forms.CharField(widget=widgets.DataList(suggestions=["Chrome", "Firefox", "Safari"]))
```

### InputMask

**Parent class:** `forms.TextInput`

Text input with a fixed-format mask that Alpine enforces as the user types.
Mask tokens: `#` is a digit, `A` a letter, `*` any character. The placeholder
shows the mask.

```python
phone = forms.CharField(widget=widgets.InputMask(mask="(###) ###-####"))
```

### OTPInput

**Parent class:** `forms.TextInput`

One-time code of `length` digits (default 6) in a single input, drawn as one
box per digit. One real input keeps SMS autofill and paste working. It sets
`inputmode="numeric"`, `autocomplete="one-time-code"`, `maxlength` and a
`pattern`, and needs no JavaScript.

```python
code = forms.CharField(widget=widgets.OTPInput(length=6))
```

### ValidatedTextarea

**Parent class:** `forms.Textarea`

Textarea with server-side validation and highlighting. With `validate_url`,
htmx posts the text after a 500 ms pause in typing. The server returns
highlighted HTML (with `<mark>` tags around errors) that overlays the textarea,
plus the messages through an out-of-band swap. Without `validate_url`, it
renders a plain textarea.

The live validation needs an `id` on the textarea, because the htmx target
and the error area are built from it. A form field gets the `id` from the
form's `auto_id`. With `auto_id=False`, or when you render the widget yourself
without `attrs={"id": ...}`, the textarea sends no validation request.

```python
content = forms.CharField(
    widget=widgets.ValidatedTextarea(validate_url=reverse_lazy("spell-check")),
)
```

See [`FormworkValidateView`](views.md#formworkvalidateview) for the server
side. The live errors render in the widget's own tooltip, whatever the form's
[`error_display`](forms.md#error_display). A field-level error such as
`required` still renders where `error_display` puts it, so the two can show at
the same time.

---

## Numbers

### StepperNumberInput

**Parent class:** `forms.NumberInput`

Number input between a - and a + button that step it by its `step` attribute.
The value is clamped when the user commits it.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes, such as `step` and `max` |
| `integer` | `bool` | `False` | Drop the decimals |
| `min` | `float \| None` | `None` | Lower bound for the buttons, without a native `min` attribute |
| `trailing_buttons` | `bool` | `False` | Put both buttons after the input |

```python
seats = forms.IntegerField(widget=widgets.StepperNumberInput(integer=True, min=1))
```

### SuffixNumberInput

**Parent class:** `forms.NumberInput`

Number input with a static unit, currency or percent sign inside the field.

```python
weight = forms.DecimalField(widget=widgets.SuffixNumberInput(suffix="kg"))
price = forms.DecimalField(widget=widgets.SuffixNumberInput(prefix="€"))
```

### Range

**Parent class:** `forms.NumberInput`, with `input_type = "range"`

```python
volume = forms.IntegerField(widget=widgets.Range(attrs={"min": 0, "max": 100, "step": 5}))
```

---

## Dates

### DateInput

**Parent class:** `forms.DateInput`

Native date input. Django's own widget renders `type="text"` with a locale
format; the native control accepts only ISO, so `format` defaults to
`"%Y-%m-%d"`.

### DateRangePicker and DateRangeField

`DateRangePicker` shows a start and an end date in one control. A click
opens a calendar with two months side by side, one on a phone. The first
click on a day sets the start, the second the end, and the days in between
fill in while the pointer moves. A click before the start begins the range
again there. A click on the end date in the closed control opens the
calendar to change the end alone. The footer counts the days and has a
Clear button.

Use it through `DateRangeField`, which cleans to a `DateRange(start, end)`
and uses the picker by default:

```python
from datetime import timedelta

from django_formwork import DateRangeField

period = DateRangeField(
    max_span=timedelta(days=90),
    error_messages={"max_span": "Pick at most 90 days."},
)
```

`required` demands both dates. The field rejects a start after the end
(`start_after_end`) and, with `max_span`, a range longer than that
(`max_span`).

The widget posts each date as ISO in a hidden input (`period_0`,
`period_1`). `format` sets how the control shows them: a Django format
setting name or a format string, `DATE_FORMAT` by default. Month and
weekday names follow the active language, and the week starts on
`FIRST_DAY_OF_WEEK`.

```python
period = DateRangeField(widget=widgets.DateRangePicker(format="SHORT_DATE_FORMAT"))
```

`data-*` and `hx-*` attrs go on the end input, which fires one `change`
when a range is complete. The other attrs go on the button that opens the
calendar.

### DateTimeRangePicker and DateTimeRangeField

`DateTimeRangeField` cleans to a `DateTimeRange(start, end)` of two
datetimes and uses `DateTimeRangePicker`. The calendar works as above, with
a start time and an end time under it and a Done button that closes it. The
times start at 00:00 and 23:59. The inputs post `YYYY-MM-DDTHH:MM` in the
current time zone, and an aware value shows in it.

```python
from django_formwork import DateTimeRangeField

stay = DateTimeRangeField(max_span=timedelta(days=14))
```

`format` defaults to `DATETIME_FORMAT`.

### DateRangeInput

Two native `DateInput`s side by side under one field label, with "From" and
"To" names for screen readers. Pass it to `DateRangeField` to use the
browser's own date controls:

```python
period = DateRangeField(widget=widgets.DateRangeInput)
```

### DatePicker

**Parent class:** `forms.DateInput`

Text date input with an Alpine calendar dropdown, for a page where the native
`DateInput` does not fit. `format` sets how the input shows the date, both
when the server renders it and after a pick in the calendar, and the
placeholder shows that format. The widget reads the format back, and also
`YYYY-MM-DD`, so the field needs no matching `input_formats`.

```python
due_date = forms.DateField(widget=widgets.DatePicker)
delivery = forms.DateField(widget=widgets.DatePicker(format="%d.%m.%Y"))
```

A click on the month title switches to a month grid, and a click on the
year to a year grid. The arrow keys move a day or a week, Page Up and Page
Down a month, with Shift a year. The calendar follows the active language
and `FIRST_DAY_OF_WEEK`, like the range pickers, and has Today and Clear
buttons.

Month and weekday names (`%B`, `%b`, `%A`, `%a`) are the English ones that
Python's `strftime` writes.

---

## Choices

### CheckboxInput

**Parent class:** `forms.CheckboxInput`

Without `text`, the field label sits beside the box. With `text`, the field
label sits above the box and `text` beside it:

```python
terms = forms.BooleanField(
    label="Terms",
    widget=widgets.CheckboxInput(text="I accept the terms of service"),
)
```

### ToggleInput

**Parent class:** `forms.CheckboxInput`

Checkbox drawn as a DaisyUI toggle switch, with the field label beside it and
no background. The label turns full strength while the switch is on.

```python
dark_mode = forms.BooleanField(widget=widgets.ToggleInput(attrs={"class": "toggle-primary"}), required=False)
```

### CheckboxSelectMultiple

**Parent class:** `forms.CheckboxSelectMultiple`

Drop-in for Django's widget. Checkbox and radio groups render as plain stacked
rows with no background box. Pass `columns=2` for a two-column grid.

### CardRadioSelect and CardCheckboxSelectMultiple

**Parent classes:** `forms.RadioSelect`, `forms.CheckboxSelectMultiple`

Choices drawn as large selectable cards with the label text centered, stacked
on small screens and side by side from the `lg` breakpoint. The checked card
fills with the primary color.

```python
plan = forms.ChoiceField(
    choices=[("free", "Free"), ("pro", "Pro")],
    widget=widgets.CardRadioSelect,
)
```

### Rating

**Parent class:** `forms.RadioSelect`

Star rating with DaisyUI's rating component.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes for the radio inputs |
| `star_class` | `str` | `"mask-star-2"` | DaisyUI mask class for the star shape |
| `allow_clear` | `bool` | `False` | Add a hidden first radio that clears the rating |

`Rating.make_choices(max_stars=5)` returns `[("1", "1 star"), ("2", "2 stars"), ...]`.
Use it instead of writing the choices yourself; `choices` is a reserved
property name on `ChoiceWidget`.

```python
rating = forms.TypedChoiceField(
    choices=widgets.Rating.make_choices(5),
    coerce=int,
    widget=widgets.Rating(star_class="mask-heart", allow_clear=True),
)
```

---

## Files

### FileDropzoneInput

**Parent class:** `forms.FileInput`

Dashed drop area that takes dragged files or opens the file picker. `max_size`
(bytes) rejects larger files in the browser.

```python
docs = forms.FileField(
    widget=widgets.FileDropzoneInput(attrs={"accept": ".pdf"}, max_size=10 * 1024 * 1024),
)
```

For several files, use `MultipleFileField`. Its default widget is this drop
area with `multiple`, and it cleans to a list of files. A plain `FileField`
rejects the list that a `multiple` input sends.

```python
from django_formwork import MultipleFileField

attachments = MultipleFileField(required=False)
```

`required` demands at least one file, and each file gets the `FileField` checks,
such as the one for an empty file. No model field holds several files, so save
each one yourself, for example as a row of a related model. For other widget
options, pass `widget=widgets.FileDropzoneInput(attrs={"multiple": True, ...})`.

### ImageDropzoneInput

**Parent class:** `forms.FileInput`

Drop area that previews the stored image, with a button that clears it.
`accept` defaults to `image/*`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `attrs` | `dict \| None` | `None` | HTML attributes, merged over `{"accept": "image/*"}` |
| `max_size` | `int \| None` | `None` | Largest file in bytes, checked in the browser |
| `hint` | `str` | `""` | A line of text in the drop area |
| `preview_url` | `str \| None` | `None` | Replaces the stored file's URL; `""` hides the preview |

On an optional field, the clear button posts `clear_<name>`, and the field
cleans to `False`, which clears the stored file, as with `ClearableFileInput`.
After the clear, the drop area comes back, and a file picked there replaces the
stored one.

!!! note "Server-side validation"
    `accept` and `max_size` only guide the browser. Validate the file type and
    size on the server as well.

---

## Display

**Parent class:** `forms.Widget`

A value the user cannot change, in the box of a filled field. It posts nothing,
so put it on a `disabled` field. Each item is a string or a `ChoiceLabel`; with
`badges=True`, each item is a badge in its `color`.

```python
status = forms.Field(
    disabled=True,
    required=False,
    widget=widgets.Display(badges=True),
)
form = OrderForm(initial={"status": [ChoiceLabel("Paid", color="success")]})
```

---

## PatternHintMixin

Shows the class attribute `pattern_hint` under a text control while its value
misses the `pattern` attribute. CSS reads the browser's verdict, so it needs no
JavaScript. Pair it with a server-side validator.

```python
class PostcodeInput(widgets.TextInput):
    pattern_hint = _("Five digits, for example 10115")

    def __init__(self, attrs=None):
        super().__init__({"pattern": "[0-9]{5}", **(attrs or {})})
```

---

## Requirements

Every widget with a `Media` class needs Alpine.js on the page: `Select`,
`SelectMultiple`, `ComboBox`, `DatePicker`, `DateRangePicker`,
`DateTimeRangePicker`, `StepperNumberInput`, `PasswordInput`, `SearchInput`,
`FileDropzoneInput`, `ImageDropzoneInput`, `InputMask` and `ValidatedTextarea`.
A server search and `ValidatedTextarea` need htmx as well. The [installation guide](../getting-started/installation.md#5-htmx-and-alpinejs)
shows the script order.
