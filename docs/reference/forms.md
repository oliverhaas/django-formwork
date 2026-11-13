# Forms

`FormworkForm` and `FormworkModelForm` bundle the DaisyUI renderer with
behaviours plain Django forms do not have: search registration, a choice of
error placement, mandatory fields, dirty-only validation, and async validation
and saving. `section_forms()` builds the forms of a page that saves one row in
several sections.

With `FORM_RENDERER = "django_formwork.FormworkRenderer"` set, every form in
the project renders styled, including plain `forms.Form`. Reach for the base
classes when you want the behaviours below, or formwork styling on individual
forms without the global renderer.

Everything documented here is importable from the package root:

```python
from django_formwork import FormworkForm, FormworkModel, FormworkModelForm, section_forms
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
only its changed fields (a section form with `data-send-changed`) validates
only those. Changed fields validate as usual, and the form-wide `clean()`
method always runs. `Form.changed_data` decides whether a field counts as
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
accent color, and typing the old value back removes the mark. It works on any
form, bound to a formwork form or not:

```html
<form method="post" data-formwork-dirty>
  {% csrf_token %}
  {{ form }}
  <button type="submit" class="btn btn-primary">Save</button>
</form>
```

The browser compares the values; the server is not asked. A few attributes
and an event adapt it to markup that is not a field group:

| Name | On | Effect |
|---|---|---|
| `data-formwork-field` | any element around a control | Gets the mark, as a field group's `fieldset` does. A table cell with an input is the usual case |
| `data-formwork-changed` | a `fieldset` or a `data-formwork-field` element | Keeps the mark from the server. Set it when a failed save renders a value the user changed, since that value is the page's value now |
| `formwork:dirty` | dispatched on the form, bubbles | `event.detail.count` is the number of marked fields, sent after each change. A save bar can show it |

A morph of the form, or of an element around it, makes the new values the ones
to compare against, and keeps only the marks that the server set. The
[admin](admin.md#editable-columns) marks the changed cells of a list with
`list_editable` this way.

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

## Section forms

A section form saves its own fields of one row, without a submit button: it
posts on every change and morphs itself back from the response. Several
section forms on one page share a request queue, so their saves run in order.

`section_forms(request, sections, **kwargs)` builds every section's form and
binds only the one that the POST names. The keyword arguments go to each form,
for example `instance=`. A POST that names no known section raises
`BadRequest`.

```python
from django_formwork import section_forms


def edit_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    sections = section_forms(
        request,
        {"general": ProjectGeneralForm, "extras": ProjectExtrasForm},
        instance=project,
    )
    for form in sections.values():
        if form.is_bound and form.is_valid():
            form.save()
    return render(request, "project_edit.html", {"sections": sections})
```

```html
{% load formwork %}
<div data-section-forms>
  <form id="general_form" data-section-form novalidate
        hx-post="{{ request.path }}" hx-trigger="change delay:300ms"
        hx-select="#general_form" hx-swap="outerMorph"
        hx-sync="closest [data-section-forms]:queue all">
    {% csrf_token %}{% formwork_section "general" %}
    {{ sections.general }}
  </form>
  <form id="extras_form" data-section-form data-send-changed novalidate
        hx-post="{{ request.path }}" hx-trigger="change delay:300ms"
        hx-select="#extras_form" hx-swap="outerMorph"
        hx-sync="closest [data-section-forms]:queue all">
    {% csrf_token %}{% formwork_section "extras" %}
    {{ sections.extras }}
  </form>
</div>
```

Load `{% formwork_sections_js %}` after htmx. The formwork bundle leaves it
out, and it does not need Alpine.

- `{% formwork_section "name" %}` writes the hidden `_formwork_section` input
  that names the section.
- Every section form needs `hx-sync="closest [data-section-forms]:queue all"`.
  A dropped or replaced save leaves its change unsent, and a request that
  waits for that save then never runs.
- A response to a save that is older than the latest change leaves the form
  alone; the queued request after it carries that change.
- A request that replaces section forms (a tab switch, for example) waits
  until their saves are answered. Leaving the page during a save asks for
  confirmation.
- `data-send-changed` on a form posts only the fields that differ from the last
  valid render, plus `csrfmiddlewaretoken` and `_formwork_section`. With a
  value, `data-send-changed="<prefix>"` also posts every field whose name
  starts with `<prefix>`, changed or not. Pair it with `validate_dirty_only`,
  so the fields the post leaves out keep their stored values.
- `data-section-indicator="<selector>"` on a field wrapper shows that indicator
  while a save the field started runs.

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
