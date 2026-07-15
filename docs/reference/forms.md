# Forms

`FormworkForm` and `FormworkModelForm` bundle the DaisyUI renderer with three
behaviours plain Django forms do not have: automatic search-endpoint
registration, dirty-only validation, and async validation and saving.

With `FORM_RENDERER = "django_formwork.FormworkRenderer"` set, every form in
the project renders styled, including plain `forms.Form`. Reach for the base
classes when you want the behaviours below, or formwork styling on individual
forms without the global renderer.

Everything documented here is importable from the package root:

```python
from django_formwork import FormworkForm, FormworkModel, FormworkModelForm
```

## Base classes

| Class | Renderer | Use with |
|---|---|---|
| `FormworkForm` | `FormworkRenderer` | Django templates |
| `FormworkModelForm` | `FormworkRenderer` | Django templates, model-backed |
| `FormworkJinja2Form` | `FormworkJinja2Renderer` | Jinja2 templates |
| `FormworkJinja2ModelForm` | `FormworkJinja2Renderer` | Jinja2 templates, model-backed |

The ModelForm variants upgrade auto-generated `ModelChoiceField` and
`ModelMultipleChoiceField` instances to their Formwork equivalents, so
`icon_from_instance` and `description_from_instance` callbacks can be attached
to fields that come from `Meta.fields`. Explicitly declared fields, including
custom subclasses, are left alone.

## Search endpoint registration

Fields rendered with `SearchSelect`, `MultiSelect`, or `ComboBox` register
their server-side search automatically when the form is instantiated; a single
`include("django_formwork.urls")` serves them all. Model-backed search needs
`search_fields` on the widget and a queryset on the field; choices-backed
search needs a `search_choices_<fieldname>(query, request)` method on the
form. Both require `search_decorator`: pass an auth decorator such as
`login_required`, or `None` for a public endpoint. See
[Views](views.md) for the endpoint machinery and the
[quickstart](../getting-started/quickstart.md#server-side-search) for worked
examples.

## error_display

Field errors render inline by default: the same visual pattern already used
for help text, a small icon below the widget, in error color, with the error
message truncated to one line and a `[more]` toggle when it overflows.
`error_display = "tooltip"` switches every field on the form to a DaisyUI
tooltip instead, which is more compact but easy to miss in a dense layout
like a table row, and leaves no room for the help text once an error
appears. Set it on the Meta class or per instantiation:

```python
class ContactForm(FormworkForm):
    class Meta:
        error_display = "tooltip"

# or
form = ContactForm(request.POST, error_display="tooltip")
```

Collapsed, only the truncated error shows, and the help text (if any) is
present for screen readers but visually hidden. Clicking `[more]` reveals
the full error message and the help text together; `[less]` collapses both
again. Errors and help text always share one expand/collapse state per
field.

Use `"inline"` (the default) for inline table-row editing, dense
multi-column layouts, or forms where the help text should stay reachable
even while an error is showing, and `"tooltip"` for fields with breathing
room where a compact tooltip is preferred.

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

Changed fields validate as usual, and the form-wide `clean()` method always
runs. Whether a field counts as changed is decided by the machinery behind
`Form.changed_data`, comparing the posted value against the form's initial
data; with `instance=` bound, initial data is what the database holds. The
model-level exclusions only apply to existing instances. On create, the
instance's `full_clean()` covers every field.

On a `FormworkModelForm` this requires the model to provide
`get_dirty_fields()`. Inherit [`FormworkModel`](#formworkmodel), or mix
`filthyfields.DirtyFieldsMixin` into the model directly; the form raises
`ImproperlyConfigured` otherwise. Plain `FormworkForm` supports the flag too,
where it covers the field-level skips.

The [cookbook](../cookbook.md#step-6-skip-validation-for-unchanged-fields)
walks through a legacy-data example.

## Async validation and saving

`ais_valid()`, `afull_clean()`, and `asave()` are async counterparts to
Django's sync methods. `clean_<field>()` and `clean()` may be sync or async in
the same form; async ones are detected and awaited, so the async ORM works in
validation without `sync_to_async` wrappers.

```python
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
`RuntimeError` so the mistake cannot silently skip M2M data.

Set `FORMWORK_FORCE_ASYNC = True` in settings to make the sync entry points
(`is_valid()`, `full_clean()`, `save()`) raise `RuntimeError`. Use it to keep
accidental sync calls out of an async codebase.

This matters because the failure is otherwise silent: a form with an async
`clean_<field>()` or `clean()` validated through the *sync* `is_valid()` stores
the un-awaited coroutine in `cleaned_data` instead of running the check, so
validation is skipped. Enable `FORMWORK_FORCE_ASYNC` in any project that defines
async validators and touches forms from sync code (including templates that read
`form.errors`) so the mistake fails loudly.

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
