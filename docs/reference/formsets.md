# Formsets and Editable Tables

`formwork_modelformset_factory` and `formwork_inlineformset_factory` build model
formsets on top of Django's. They validate uniqueness with one query per check
instead of one per row, and they render as an editable table. Every name on this
page is importable from `django_formwork`.

## Factories

```python
from django_formwork import formwork_inlineformset_factory, formwork_modelformset_factory

TaskFormSet = formwork_modelformset_factory(Task, fields=["title", "status"], extra=0)
LineFormSet = formwork_inlineformset_factory(Order, OrderLine, fields=["product", "quantity"])
```

Both take the arguments of Django's `modelformset_factory` and
`inlineformset_factory`. Three defaults differ:

| Argument   | Default                                                  |
|------------|----------------------------------------------------------|
| `form`     | `FormworkModelForm`                                      |
| `formset`  | `FormworkBaseModelFormSet` / `FormworkBaseInlineFormSet` |
| `renderer` | `FormworkRenderer()`                                     |

To add formset behavior, subclass the base class and pass it as `formset`:

```python
from django.core.exceptions import ValidationError

from django_formwork import FormworkBaseModelFormSet, formwork_modelformset_factory


class TaskBaseFormSet(FormworkBaseModelFormSet):
    def clean(self):
        super().clean()
        if sum(form.cleaned_data.get("hours", 0) for form in self.forms) > 40:
            raise ValidationError("More than 40 hours in one week.")


TaskFormSet = formwork_modelformset_factory(Task, formset=TaskBaseFormSet, fields=["title", "hours"])
```

## Uniqueness validation

Django validates uniqueness one form at a time: each row runs one query per unique
check, so 50 rows with 3 checks make 150 queries. A Formwork formset takes these
checks from its forms and runs one query per distinct check for all rows. The
errors, their messages and their placement (on the field or in `__all__`) are the
same as Django's. Only the query count changes.

One query covers all rows for:

- `unique`, `unique_together` and `unique_for_date` / `unique_for_month` /
  `unique_for_year`.
- A `UniqueConstraint` on fields only, with no `condition`, the default
  `violation_error_message` and `nulls_distinct` not set to `False`.
- Every `CheckConstraint`.

These still run per row, through Django's own `constraint.validate()`:

- A `UniqueConstraint` with a `condition`, expressions, a custom message or
  `nulls_distinct=False`.
- A `UniqueConstraint` over a `GeneratedField` or a field with a `db_collation`.

The database checks run in the formset's `full_clean()`, before `validate_max` and
`clean()`, as Django runs them in each form's `full_clean()`. A `clean()` override
without `super()` skips only the check between the submitted rows, as in Django.
Rows marked for deletion are checked too, and the formset drops their errors, as
Django does.

A plain `ModelForm` passed as `form` keeps Django's per-form checks.

### Known differences

Two cases compare values in Python where Django compares them in SQL:

- A `unique` or `unique_together` field with a case-insensitive collation (MySQL
  `*_ci`, `db_collation="NOCASE"`, PostgreSQL `citext`). The batched check can miss
  a duplicate that differs only in case. The database then rejects the save with an
  `IntegrityError`.
- `unique_for_date` (or month, year) against a `DateTimeField` with a `TIME_ZONE`
  other than UTC. The batched check keys rows by the stored UTC date, Django by the
  local date, so a row near midnight can miss its duplicate.

## Editable tables

`formset.as_rows(save_url)` renders the formset as one `<table>`, with a header row
from the formset's `empty_form`. `form.as_row(save_url)` renders one `FormworkForm`
or `FormworkModelForm` as a `<tbody>`, with one cell per visible field and the
hidden inputs in the first cell.

With a `save_url`, each row posts its own fields to that URL 400 ms after a change
and morphs the response in place. Without one, the rows are static.

A disabled field shows as text: the instance's `get_<field>_display()`, else the
instance's value (a comma-separated list for a many-to-many field), else the labels
of the chosen values.

`as_rows()` does not render the management form. Add
`{{ formset.management_form }}` if the table is also submitted as a whole formset.

### Templates

| Template                     | Renders                       | Set per class on         |
|------------------------------|-------------------------------|--------------------------|
| `formwork/tables/table.html` | `as_rows()`: the `<table>`    | the formset, `template_name_table` |
| `formwork/tables/row.html`   | `as_row()`: one `<tbody>`     | the form, `template_name_row`      |

To override one for the whole project, put a template at the same path in a
directory of your `TEMPLATES` setting.

## Saving a row

`FormworkRowSaveMixin` is the view behind `save_url`. It saves the posted row and
answers with the row rendered again.

```python
# views.py
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from django_formwork import FormworkRowSaveMixin


class TaskRowSave(FormworkRowSaveMixin, View):
    form_class = TaskRowForm
    http_method_names = ["post"]

    def get_queryset(self, request):
        return Task.objects.filter(owner=request.user)


def task_list(request):
    formset = TaskFormSet(queryset=Task.objects.filter(owner=request.user))
    return render(request, "tasks/list.html", {"table": formset.as_rows(reverse("task_row_save"))})
```

```python
# urls.py
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path("tasks/row/", login_required(TaskRowSave.as_view()), name="task_row_save"),
]
```

On each post the view:

1. Reads the form prefix and the row's primary key from the post.
2. Looks the row up in `get_queryset(request)`. A missing or malformed key, or a
   row outside the queryset, gets a 404.
3. Binds `form_class(request.POST, request.FILES, instance=row, prefix=prefix)`.
4. Saves the form if it is valid, and answers with the row, errors included.

`queryset` or `get_queryset()` is required. It holds the rows a user can change, so
a user cannot post another user's primary key and edit that row. Without either,
the view raises `ImproperlyConfigured`. Set `queryset = Task.objects.all()` only if
every user can change every row. The mixin does no other access check: protect the
view as you protect any other.

| Method                     | Default                                  |
|----------------------------|------------------------------------------|
| `get_queryset(request)`    | `queryset.all()`                         |
| `get_form_kwargs()`        | `{}`, extra arguments for `form_class`   |
| `get_prefix(request)`      | the posted `_formwork_prefix`            |
| `get_save_url(request)`    | `request.path`                           |
| `render_row(request, form)`| `form.as_row(self.get_save_url(request))`|

The form validates every field of `form_class` against the post: a required field
the row does not post fails, and an optional one can be saved empty. Give the row
form only the columns the table shows.

### Hand-authored rows

To lay a row out yourself, render it from your own template and override
`render_row()` to render the same template. Put `{{ form.row_hidden_inputs }}` in
the row: it carries the prefix and the primary key the view reads. The
[full example](https://github.com/oliverhaas/django-formwork/tree/main/examples/full)
renders its task list this way.

## `FORMWORK_FORCE_ASYNC`

Django's formsets have no async API: they validate and save their forms through the
sync methods. The forms that a Formwork formset builds are therefore exempt from
`FORMWORK_FORCE_ASYNC`. In an async view, run the formset's methods in a worker
thread:

```python
from asgiref.sync import sync_to_async

if await sync_to_async(formset.is_valid)():
    await sync_to_async(formset.save)()
```

Because these forms validate through the sync path, an async `clean_<field>()` or
`clean()` on them is not awaited. Keep those methods sync on a formset's form.

A Django formset (`modelformset_factory`) with a `FormworkModelForm` gets no
exemption: with the setting on, its `is_valid()` raises `RuntimeError`. Build it
with `formwork_modelformset_factory` instead.
