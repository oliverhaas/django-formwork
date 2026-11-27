# Forms

`FormworkForm` and `FormworkModelForm` bundle the DaisyUI renderer with
behaviours plain Django forms do not have: search registration, a choice of
error placement, mandatory fields, dirty-only validation, and async validation
and saving.

With `FORM_RENDERER = "django_formwork.FormworkRenderer"` set, every form in
the project renders styled, including plain `forms.Form`. Reach for the base
classes when you want the behaviours below, or formwork styling on individual
forms without the global renderer.

Everything documented here is importable from the package root:

```python
from django_formwork import DisplayField, FormworkForm, FormworkModel, FormworkModelForm
```

## Base classes

| Class | Use with |
|---|---|
| `FormworkForm` | any data |
| `FormworkModelForm` | a model; subscript it for typed `instance` and `save()`: `FormworkModelForm[Book]` |

Both render with `FormworkRenderer` and use `FormworkBoundField`. It adds
`aria-required` to a [mandatory field](#required-and-mandatory-fields), and
`aria-labelledby` to a dropdown trigger that `<label for>` cannot target.

For icons, descriptions or a trigger class on model choices, return a
[`ChoiceLabel`](widgets.md#choicelabel) from `label_from_instance`:

```python
from django import forms

from django_formwork import ChoiceLabel


class MemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return ChoiceLabel(obj.name, description=obj.email)
```

## Layouts

`{{ form }}` and `as_div()` render one field group after another. Django's
other layouts render formwork markup too, also for a plain `forms.Form` that
`FormworkRenderer` renders:

| Method | Renders |
|---|---|
| `as_p()` | what `as_div()` renders, since a `<p>` cannot hold a field group |
| `as_ul()` | each field group in an `<li>`; the page writes the `<ul>` |
| `as_table()` | a row per field, with the label in a `<th>` and the rest of the field group in a `<td>`; the page writes the `<table>` |

The form's own errors come first, in an alert. `{{ formset }}` renders its
forms with `as_div()`.

To place the fields yourself, render `{{ field.as_field_group() }}` for each
one. `{{ field.as_control() }}` renders only the widget and its error tooltip,
for a layout that shows the label somewhere else, such as a column header:

```html+jinja
<table>
  <tr>{% for field in form %}<th>{{ field.label }}</th>{% endfor %}</tr>
  <tr>{% for field in form %}<td>{{ field.as_control() }}</td>{% endfor %}</tr>
</table>
```

The control keeps the field's name for a screen reader: the widget gets an
`aria-label`, and a radio or checkbox list becomes a named group. It also
carries the [changed-field mark](#changed-field-highlight).

## Search registration

A field whose widget (`Select`, `SelectMultiple`, `ComboBox` or
`ComboBoxMultiple`) has a `search_queryset` registers its search when Python
creates the form class.
Formwork imports the `forms` module of every installed app at startup, so the
search exists in every worker before the first request. A single
`include("django_formwork.urls")` serves all of them. Registration raises
`ImproperlyConfigured` for a widget without `search_decorator`: pass an auth
decorator such as `login_required`, or `None` for a public endpoint. A bad `Meta`
option fails the same way, when Python creates the class: an `error_display`
other than `"auto"`, `"inline"` or `"tooltip"`, a `mandatory` that is a string or
names a field the form lacks, and `validate_dirty_only` on a model without
`get_dirty_fields()`. See
[Views](views.md#server-side-search) for the endpoint and the
[quickstart](../getting-started/quickstart.md#server-side-search) for a worked
example.

## Required and mandatory fields

A required field shows a red `*` after its label, and the widget carries
`aria-required="true"`. A disabled field shows no asterisk. Formwork marks no
optional field.

`Meta.mandatory` names fields that a save accepts empty but a later step needs,
for example a draft that the user publishes later. They get the asterisk and
`aria-required` too, and they still validate as optional:

```python
class ListingForm(FormworkModelForm):
    class Meta:
        model = Listing
        fields = ["title", "price", "description"]
        mandatory = ["price", "description"]
```

`Meta.mandatory` seeds the set `self.mandatory`. Add a name that depends on the
data after `super().__init__()`:

```python
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.category == "vehicle":
            self.mandatory.add("mileage")
```

## Help text

Formwork escapes help text. Django's own templates render it as HTML, so a
plain string with tags that showed as markup there shows the tags as text here.
Build markup with `format_html()` or `mark_safe()`:

```python
from django.utils.html import format_html

email = forms.EmailField(
    help_text=format_html('See the <a href="{}">privacy policy</a>.', "/privacy/"),
)
```

## Label links

A widget with a `label_links()` method puts links at the end of its field's label row.
The method gets the field's HTML name, its value and the form's renderer, and returns
HTML. The field template renders the links after the label, not inside it, so they stay
out of the field's accessible name and come before the widget in the tab order. The label
row sets the size and color of the links and puts their text on the label's baseline; an
icon in a link centers on its text.

```python
from django.utils.html import format_html

from django_formwork import widgets


class SlugInput(widgets.TextInput):
    def label_links(self, name, value, renderer=None):
        return format_html('<a href="#" class="link link-hover" data-generate="{}">Generate</a>', name)
```

The admin's relation widget uses it for its Edit and Add links.

## error_display

`error_display` picks where field errors render:

| Value | Placement |
|---|---|
| `"auto"` (default) | inline when the field has help text, in a tooltip when it has none |
| `"inline"` | inline under every field |
| `"tooltip"` | in a DaisyUI tooltip on every field |

Set it on the Meta class or per instantiation:

```python
class ContactForm(FormworkForm):
    class Meta:
        error_display = "tooltip"


# or
form = ContactForm(request.POST, error_display="tooltip")
```

An inline error uses the pattern of the help text: a small icon below the
widget, in error color, with the message truncated to one line and a `[more]`
toggle when it overflows. `[more]` reveals the full error and the help text
together; `[less]` collapses both. While collapsed, the help text is
present for screen readers but visually hidden. A tooltip error is more
compact, but a user can miss it in a dense layout such as a table row.

Use `"inline"` for inline table-row editing, dense multi-column layouts, or
forms where the help text must stay reachable while an error shows, and
`"tooltip"` for fields with room around them. A plain `forms.Form` rendered by
`FormworkRenderer` uses `"auto"`.

## validate_dirty_only

On an edit form, validators added after a record was saved can reject stored
values the user never touched. `validate_dirty_only` skips validation for
fields the submission did not change. Enable it on the Meta class or per
instantiation:

```python
class TicketEditForm(FormworkModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "priority", "description"]
        validate_dirty_only = True


# or
form = TicketEditForm(request.POST, instance=ticket, validate_dirty_only=True)
```

For a field the user did not change:

- field validators and the `clean_<field>` method do not run
- model field validation, unique checks, and constraint checks exclude it
- the stored value is carried into `cleaned_data` and left untouched on the
  instance, so an unchanged relation is never re-assigned

A field that the post leaves out counts as unchanged, so a form that posts
only its changed fields validates only those. Changed fields validate as usual,
and the form-wide `clean()` method always runs. `Form.changed_data` decides whether a field counts as
changed: it compares the posted value against the initial data of the form,
and with `instance=` bound, the initial data is what the database holds. The
model-level exclusions apply only to existing instances. On create, the
`full_clean()` of the instance covers every field.

On a `FormworkModelForm` the flag requires the model to provide
`get_dirty_fields()`. Inherit [`FormworkModel`](#formworkmodel), or mix
`filthyfields.DirtyFieldsMixin` into the model directly; the form raises
`ImproperlyConfigured` otherwise. Plain `FormworkForm` supports the flag too,
where it covers the field-level skips.

The [cookbook](../cookbook.md#step-6-skip-validation-for-unchanged-fields)
walks through a legacy-data example.

## Changed-field highlight

`data-formwork-dirty` on a `<form>` marks each field whose value differs from
the value the page loaded with. The field's border and focus ring take the
accent color, and typing the old value back removes the mark. In a group of
checkboxes or radio buttons, only the options whose checked state changed take
the color, through the `formwork-dirty-option` class. It works on any form,
bound to a formwork form or not:

```html
<form method="post" data-formwork-dirty>
  {% csrf_token %}
  <div class="grid gap-2">{{ form }}</div>
  <button type="submit" class="btn btn-primary">Save</button>
</form>
```

The browser compares the values; the server is not asked. A few attributes
and an event adapt it to markup that is not a field group:

| Name | On | Effect |
|---|---|---|
| `data-formwork-field` | any element around a control | Gets the mark, as a field group's `fieldset` does. A table cell with an input is the usual case |
| `data-formwork-changed` | a `fieldset` or a `data-formwork-field` element | Keeps the mark from the server. Set it when a failed save renders a value the user changed, since that value is the page's value now |
| `data-formwork-initial` | an element with `data-formwork-changed` | A JSON list of the option values a checkbox, radio or switch field had checked at first. The page then marks each changed option, and drops the mark when the user checks the first options again |
| `formwork:dirty` | dispatched on the form, bubbles | `event.detail.count` is the number of marked fields, sent after each change. A save bar can show it |

A morph of the form, or of an element around it, makes the new values the ones
to compare against, and keeps only the marks that the server set. The
[admin](admin.md#editable-columns) marks the changed cells of a list with
`list_editable` this way.

After a failed save, the page shows the posted values and keeps the user's
changes marked. Formwork's field template sets `data-formwork-changed` on
each field of a bound form that is in `changed_data`, and
`data-formwork-initial` on such a field with checkboxes or radio buttons. A field
with an error keeps its mark too, as its value is still a change to save, and the
error color covers the accent. A file field is left out, as its input renders
empty again.

Two CSS variables set the color of the marks. A theme or a page can set them:

| Variable | Default | Colors |
|---|---|---|
| `--formwork-dirty-color` | `var(--color-accent)` | The border and focus ring of a changed field, a changed radio button, switch or range, and the box of a changed checkbox |
| `--formwork-dirty-content` | `var(--color-accent-content)` | The check in a changed checkbox and the thumb of a changed range |

```css
:root {
  --formwork-dirty-color: var(--color-info);
  --formwork-dirty-content: var(--color-info-content);
}
```

The error colors win over the changed colors, so an invalid field shows its
error first.

## Async validation and saving

`ais_valid()`, `afull_clean()`, and `asave()` are async counterparts to
Django's sync methods. `clean_<field>()` and `clean()` can be sync or async in
the same form. Formwork detects the async ones and awaits them, so validation
can use the async ORM without `sync_to_async` wrappers.

```python
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from django_formwork import FormworkForm


class SignupForm(FormworkForm):
    email = forms.EmailField()

    async def clean_email(self):
        email = self.cleaned_data["email"]
        if await User.objects.filter(email__iexact=email).aexists():
            raise ValidationError("Already registered.")
        return email


async def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if await form.ais_valid():
            ...
```

`asave(commit=True)` mirrors `ModelForm.save()`: it awaits the instance's
`asave()` and then saves many-to-many relations. With `commit=False` it
returns the unsaved instance and exposes `asave_m2m` as an async callable;
call `await form.asave_m2m()` after saving the instance. Calling the sync
`save_m2m` hook on a form saved with `asave(commit=False)` raises
`RuntimeError` that points to `asave_m2m()`.

Set `FORMWORK_FORCE_ASYNC = True` in settings to make the sync entry points
(`is_valid()`, `full_clean()`, `save()`) raise `RuntimeError`. Use it to keep
accidental sync calls out of an async codebase.

Without the setting, a form with an async `clean_<field>()` or `clean()` that
validates through the sync `is_valid()` stores the un-awaited coroutine in
`cleaned_data` and skips the check. Enable `FORMWORK_FORCE_ASYNC` in a project
that defines async validators and touches forms from sync code, including a
template that reads `form.errors`. The sync call then raises `RuntimeError`.

Formwork's model formsets validate their forms through the sync path, so their
forms are exempt from the setting; see [Formsets](formsets.md#formwork_force_async).
`FormworkRowSaveMixin` calls the sync `is_valid()`, so a row save fails while the
setting is on.

## Several forms on one page

A page can show one row in several forms, each of which saves its own fields
on change, without a submit button. The pattern needs no formwork API: a
hidden input names the form, the view binds only that form, and htmx
attributes post the form and morph the answer in.

```python
def edit_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    posted = request.POST.get("section")
    general = ProjectGeneralForm(request.POST if posted == "general" else None, instance=project)
    extras = ProjectExtrasForm(request.POST if posted == "extras" else None, instance=project)
    for form in (general, extras):
        if form.is_bound and form.is_valid():
            form.save()
    return render(request, "project_edit.html", {"general": general, "extras": extras})
```

```html
<form id="general_form" novalidate class="grid gap-2"
      hx-post="{{ request.path }}" hx-trigger="change, submit"
      hx-select="#general_form" hx-swap="outerMorph" hx-sync="body:queue all">
  {% csrf_token %}
  <input type="hidden" name="section" value="general">
  {{ general }}
</form>
<form id="extras_form" novalidate class="grid gap-2"
      hx-post="{{ request.path }}" hx-trigger="change, submit"
      hx-select="#extras_form" hx-swap="outerMorph" hx-sync="body:queue all">
  {% csrf_token %}
  <input type="hidden" name="section" value="extras">
  {{ extras }}
</form>
```

Give the hidden input another name than `form`. htmx finds the form it posts
through the `form` property of the element, and on a form element an input
named `form` takes that property over.

The attributes decide what reaches the database:

- `hx-trigger="change, submit"` saves each change when the user commits it.
  A change event comes once per edit, so it needs no delay. A trigger on
  `input` saves while the user types and needs one, for example
  `input changed delay:500ms`. The browser submits a form with one text field
  when the user presses Enter, and with `submit` in the trigger htmx sends that
  submit as a save instead of a page load.
- `hx-sync="body:queue all"` puts the saves of every form on the page in one
  queue, so they run one at a time in the order of the changes. `form.save()`
  writes every column of the row, so two saves that run at the same time can
  undo each other's changes. Only `queue all` sends every change: `drop` and
  the default `queue first` drop changes, and `replace` aborts a save in the
  browser that the server still runs next to the new one.
- Each form posts all its fields, and the view saves the form with
  `form.save()`. The answer renders the form from what it posted, with its
  errors.

When the forms of a page save different rows, one queue per row is enough:
give the forms of one row a common container and
`hx-sync="closest .project:queue all"`.

`formwork-core.js` keeps the user's work while the saves run:

- When the user changes a form again before the answer to its save arrives,
  the morph keeps the value of every field that the user edited after the save
  collected the form, as it keeps the focused field. The next save in the queue
  carries the edit.
- The browser asks before it leaves the page while a save waits in a
  `queue all` queue. A save that is on its way finishes on the server.

A request that replaces the forms, such as a tab, can run before the saves
in the queue. They still go out, and htmx drops their answers because the
forms are gone. To let the tab wait for the saves, give it the same
`hx-sync="body:queue all"`.

## DisplayField

`DisplayField` shows a value that the form never posts: a field, a method, a property
or an annotation of the form's instance. It renders with the
[`Display`](widgets.md#display) widget, and as text in a cell of
[`formset.as_rows()`](formsets.md#editable-tables).

```python
from django_formwork import DisplayField, FormworkModelForm


class EventForm(FormworkModelForm):
    kind = DisplayField()
    venue = DisplayField()
    seats = DisplayField(source=lambda event: event.capacity or "No limit")

    class Meta:
        model = Event
        fields = ["title", "starts_at", "ends_at"]
```

`source` is the name of an attribute or a method of the instance, or a function of the
instance. It defaults to the field's name. A field with choices shows its label, from
`get_<name>_display()`, and a relation shows its related rows. An unsaved instance
shows no related rows. A form without an instance shows the field's `initial` value.

The field reads its value when the page renders it, not when the form validates. An
annotation that the view adds to the instance after the post therefore shows. A post
never changes the value: `FormworkForm` and `FormworkModelForm` leave the field out of
`cleaned_data` and `changed_data`, also when the post has a value with its name. A
`DisplayField` with the name of a model field keeps that field out of `save()`. A plain
Django form puts `None` in `cleaned_data` for it, so use a formwork form.

`max_lines` cuts a long value to that many lines, from 1 to 10, in its box and in a
table cell. A `[more]` toggle under the last line shows the rest. The toggle shows only
when the value has more lines, and keeps its room either way, so the column keeps its
width:

```python
class EventForm(FormworkModelForm):
    notes = DisplayField(max_lines=3)
```

## FormworkModel

`FormworkModel` is an abstract model base that mixes in
`filthyfields.DirtyFieldsMixin`, providing the `get_dirty_fields()` that
`validate_dirty_only` needs, and adds one helper for `clean()` rules:

```python
class Ticket(FormworkModel):
    status = models.CharField(max_length=10)
    closed_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.fields_dirty("status") and self.status == "closed" and not self.closed_at:
            raise ValidationError("Closing a ticket requires closed_at.")
```

`fields_dirty(*names)` is `True` if any of the named fields changed since the
instance was loaded from the database. New instances always return `True`, so
cross-field rules fire fully on create.
