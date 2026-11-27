# Formsets and Editable Tables

`formwork_modelformset_factory` and `formwork_inlineformset_factory` build model
formsets on top of Django's. They validate uniqueness with one query per check
instead of one per row, and they render as an editable table. Every name on this
page is importable from `django_formwork`.

## Factories

```python
from django_formwork import formwork_inlineformset_factory, formwork_modelformset_factory

TaskFormSet = formwork_modelformset_factory(Task, fields=["title", "status"], extra=0)
LineFormSet = formwork_inlineformset_factory(Invoice, InvoiceLine, fields=["description", "quantity"])
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

## Loading the rows

Django runs more queries for each row of a model formset: one that finds the row of
the posted primary key, one for each many-to-many field that the form shows, and two for
each foreign key: one in the form field that finds the posted row, and one in the
model's own check that the row exists. A Formwork formset runs each of them once for all
rows. These keep Django's own query and its error:

- a primary key that the formset cannot read from the post, for example through a
  custom widget;
- a posted value that no row of the batch matches, or that the key cannot take;
- a choice field whose rows can get choices of their own, through one of the hooks in
  [Shared choices](admin.md#shared-choices), or a `ModelChoiceField` subclass that
  changes `to_python()`;
- a foreign key with a callable `limit_choices_to`, or a subclass that changes
  `clean()` or `validate()`.

## Editable tables

`formset.as_rows()` renders a formset as one editable `<table>`: the management form,
a header row from the formset's `empty_form`, one `<tbody>` per form, and a button to
add a row. Put it in a `<form>` and save it as any other formset:

```python
def task_edit_all(request):
    formset = TaskFormSet(request.POST or None, queryset=Task.objects.filter(owner=request.user))
    if request.method == "POST" and formset.is_valid():
        formset.save()
        return redirect("task_list")
    return render(request, "tasks/edit_all.html", {"formset": formset})
```

```html
<form method="post" data-formwork-dirty>
  {% csrf_token %}
  {{ formset.as_rows }}
  <button class="btn btn-primary">Save</button>
</form>
```

- **Header.** Each column has the field's label, a red asterisk for a required field,
  and the help text in a tooltip on an info icon.
- **Cells.** A row has one cell per visible field. A disabled field shows as text:
  the instance's `get_<field>_display()`, else the instance's value (a
  comma-separated list for a many-to-many field), else the labels of the chosen
  values. A [`DisplayField`](forms.md#displayfield) shows its value as text, a list
  comma-separated. The text is the bound field's `display_value`, so a field with a
  `bound_field_class` of its own can change it.
- **Errors.** A cell keeps its errors in a tooltip under the widget. The tooltip shows
  while the pointer is on the cell or the focus is in it, so the row keeps its
  height. The errors of a whole row show above the row, the formset's own errors
  above the table.
- **Changed values.** In a bound formset, a cell whose value differs from the initial
  one carries the same marks as a changed field of a form. `data-formwork-dirty` on
  the `<form>` shows them.
- **Rows.** Add another appends a row from the formset's `empty_form`, and a new row
  has Remove. With `can_delete`, a saved row has a Delete toggle instead: the row
  fades and is struck through until the save deletes it. Add another hides at
  `max_num`, Remove at `min_num`, and the indexes of the rows stay contiguous.
  `can_add = False` on the formset class, or `edit_only=True`, removes Add another.
  A formset method `row_url(form)` that returns a URL gives the row an Open link in
  its last column.
- **Row details.** A formset method `row_details(form)` that returns HTML gives the
  row a chevron in a last column of its own. A click on the chevron, or anywhere on the
  row outside its inputs, links and buttons, opens the HTML under the row. The details
  take the table's width, never the width of a column. `form.instance` holds the row's
  object:

  ```python
  class TaskFormSet(FormworkBaseModelFormSet):
      def row_details(self, form):
          return render_to_string("tasks/row_details.html", {"task": form.instance})
  ```

  A `SafeString`, as `render_to_string()` and `format_html()` return, shows as HTML,
  any other string as text. `None` gives the row no chevron. A table with a
  `save_url` shows no details: a row that saves by itself renders again without the
  formset.
- **Empty table.** Without rows, the table shows "No *tasks* yet.", with the model's
  `verbose_name_plural`.
- **Choices.** A `Select` or `SelectMultiple` of a relation loads its choices with one
  query for all rows. A row loads its own when the form or the formset can give it
  other choices, as [Shared choices](admin.md#shared-choices) lists. When the rows of
  a column list the same choices, the table renders the option rows once, and a row's
  list copies them when it opens.

`as_rows(flush=True)` is for a table in a card: the table runs to the card's edges,
and its first and last columns take the card's padding.

The rows need `tables.js`. `{% formwork_js %}` loads it, and so does
`{{ formset.media }}` after `{% formwork_core_js %}`.

### Saving row by row

`formset.as_rows(save_url)` saves each row by itself: a row posts its own fields to
`save_url` on each change and morphs the response in place. The saves of one row
wait in a queue and run in the order of the changes, so a change made while a save
runs is sent after it. A row is saved the moment it changes, so this table has no
Add another, Remove or Delete.
`form.as_row(save_url)` renders one `FormworkForm` or `FormworkModelForm` the same
way, as one `<tbody>`. [Saving a row](#saving-a-row) describes the view behind
`save_url`.

### Widgets that load on use

`formset.as_rows(cell_url=...)` renders each `Select`, `SelectMultiple`, `ComboBox`,
`ComboBoxMultiple`, `DatePicker`, `DateTimePicker`, `DateRangePicker` and
`DateTimeRangePicker` of the saved rows as a stub: the closed widget with its value, and
inputs that post the value as the full widget does. When the pointer rests on a stub, or
the stub takes the focus or a press, the full widget loads from `cell_url` and takes its
place with the focus, the typed text and the press. The stubs of a select load the
labels of their rows with one query for all rows. A field with an error renders the full
widget.

`FormworkCellMixin` is the view behind `cell_url`. The query names the `field`, the
row's `pk` and its form `prefix`, and holds the stub's inputs under their names, so a
changed value stays changed. The view builds the row with `formset_class`, so the row
gets the choices that a hook of the form or of the formset gives it.

```python
from django_formwork import FormworkCellMixin


class TaskCell(FormworkCellMixin, View):
    formset_class = TaskFormSet
    http_method_names = ["get"]

    def get_queryset(self, request):
        return Task.objects.filter(owner=request.user)


def task_list(request):
    formset = TaskFormSet(queryset=Task.objects.filter(owner=request.user))
    table = formset.as_rows(reverse("task_row_save"), cell_url=reverse("task_cell"))
    return render(request, "tasks/list.html", {"table": table})
```

As for [saving a row](#saving-a-row), `queryset` or `get_queryset()` is required. A
row outside it, a malformed key, an unknown field or a disabled one gets a 404.
`get_formset_kwargs(request)` returns extra arguments for `formset_class`, such as the
`form_kwargs` that the page passes. The mixin does no other access check: protect the
view as you protect the page.

### Templates

| Template                     | Renders                    | Context                          | Set per class on                   |
|------------------------------|----------------------------|----------------------------------|------------------------------------|
| `formwork/tables/table.html` | `as_rows()`: the `<table>` | `formset.get_table_context()`    | the formset, `template_name_table` |
| `formwork/tables/row.html`   | `as_row()`: one `<tbody>`  | `form.get_row_context()`         | the form, `template_name_row`      |

The table context has the `headers`, the `rows`, the `empty_row` that Add another
copies and the `footer` markup at the right end of the Add another row, where the
admin puts the pager of an inline. Each row is the context of a row: the `form`, its
`cells` (the visible bound fields) and its `hidden` inputs. To change what a table
shows, override `get_table_context()` on the formset or `get_row_context()` on the
form. `render_table(context)` and `render_row(context)` render a context that you
changed. A form without these methods, such as a plain `ModelForm`, gets them from
the formset.

Both are Jinja2 templates. To override one for the whole project, put a template
at the same path in the `jinja2/` directory of an app listed before `django_formwork`.

To change part of a row, extend `formwork/tables/row.html` and override its blocks,
then set `template_name_row` to your template. A field's widget, its changed and
invalid marks and its errors stay the same.

| Block                                   | Holds                                                    |
|-----------------------------------------|----------------------------------------------------------|
| `row_attrs`                             | the attributes of the row's `<tbody>` after its `id`     |
| `errors_attrs`, `errors_span`           | the attributes and the `colspan` of the row's error line |
| `cells_attrs`                           | the attributes of the `<tr>` of the cells                |
| `leading_cells`                         | cells before the fields' cells, empty by default         |
| `cell_attrs`                            | a field cell's `class` and `data-field`                  |
| `display_cell`                          | what a cell shows for a field that posts nothing         |
| `trailing_cells`                        | the actions cell and the details toggle                  |
| `details_toggle`                        | the cell of the details toggle                           |
| `details_attrs`                         | the attributes of the details' `<tr>` after its `id`     |
| `details_leading_cells`, `details_span` | cells before the details' cell, and its `colspan`        |
| `details_content`                       | what the details show, `details` by default              |

`cell_attrs` and `display_cell` see the cell's bound field as `bf` and Jinja's `loop`.

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
the row: it carries the prefix and the primary key the view reads.

```html
{# tasks/row.html #}
<tbody id="{{ form.row_id }}"
       hx-post="{% url 'task_row_save' %}" hx-trigger="change" hx-sync="this:queue all"
       hx-target="this" hx-swap="outerMorph" hx-include="closest tbody">
  <tr>
    <td>
      {{ form.row_hidden_inputs }}
      <a href="{{ form.instance.get_absolute_url }}" class="font-medium">{{ form.instance.title }}</a>
    </td>
    <td>{{ form.status }}</td>
    <td>{{ form.assignee }}</td>
    <td>{{ form.due_date }}</td>
  </tr>
</tbody>
```

```html
{# tasks/list.html #}
<table class="table">
  <thead><tr><th>Task</th><th>Status</th><th>Assignee</th><th>Due</th></tr></thead>
  {% for form in formset %}{% include "tasks/row.html" %}{% endfor %}
</table>
```

```python
from django.template.loader import render_to_string


class TaskRowSave(FormworkRowSaveMixin, View):
    form_class = TaskRowForm
    http_method_names = ["post"]

    def get_queryset(self, request):
        return Task.objects.filter(owner=request.user)

    def render_row(self, request, form):
        return render_to_string("tasks/row.html", {"form": form}, request=request)
```

The row posts its own fields, `hx-include="closest tbody"`, because a `<tbody>`
cannot hold a `<form>`. A field the template leaves out is still part of
`form_class`, so give the row form the fields the row shows, as in
[Saving a row](#saving-a-row).

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
