# Admin

`django_formwork.admin` is a Django admin built on formwork forms, django-filter, htmx
and Jinja2, styled with DaisyUI. It keeps the names, options, hooks, URL names and
permissions of `django.contrib.admin`, so most `admin.py` modules port by changing one
import:

```python
# from django.contrib import admin
from django_formwork import admin


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["subject", "requester", "status", "priority"]
    list_filter = ["status", "opened_at"]
    search_fields = ["subject", "requester__email"]
    inlines = [ReplyInline]
```

![The ticket list with a status filter set](../img/admin/changelist.webp)

The classes are its own. A `ModelAdmin` does not subclass Django's, so an admin class
written for `django.contrib.admin` that calls into Django's internals needs changes.

!!! warning "Experimental"
    The admin is new and its API can change in any release before 1.0.

## Setup

### 1. Install

```bash
pip install "django-formwork[admin]"
```

The `admin` extra installs django-filter and Jinja2.

### 2. Settings

```python
INSTALLED_APPS = [
    ...,
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.forms",
    "django_iconx",
    "django_formwork",
    "django_formwork.admin",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    ...,
]
```

`django.contrib.admin` is not needed: the admin keeps its history in its own table. The
admin pages render through a private Jinja2 engine, so `TEMPLATES` needs no Jinja2
backend.

Run `manage.py migrate` after you add the app.

`manage.py check` reports a missing app or middleware, and checks every registered
`ModelAdmin` for the mistakes Django's admin checks catch, under the same numbers:
`formwork_admin.E108` for an unknown `list_display` entry, `formwork_admin.E116` for a
broken `list_filter` entry, and so on.

### 3. URLs

```python
from django.urls import include, path

from django_formwork.admin import site

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("admin/", site.urls),
]
```

`django_formwork.urls` serves the relation search of the dropdowns. The site's URL
names match Django's, so `reverse("admin:helpdesk_ticket_change", args=[ticket.pk])` works as
before. To run Django's admin next to this one, give one of the two sites another
`name`, since both use the `admin` namespace by default.

### 4. CSS

Import `admin.css` after `formwork.css` in your Tailwind entry and build it as in
[Installation](../getting-started/installation.md#4-build-the-css):

```css
@import "path/to/site-packages/django_formwork/static/formwork/formwork.css";
@import "path/to/site-packages/django_formwork/admin/static/formwork_admin/admin.css";
@import "./static/iconx/icons.css" layer(components);
```

`admin.css` registers the admin's templates with `@source`, so Tailwind finds their
classes. Then point the site at the built file:

```python
# myproject/admin_site.py
from django_formwork.admin import AdminSite


class MyAdminSite(AdminSite):
    site_header = "Helpdesk"
    stylesheets = ("dist.css",)
```

```python
# settings.py
FORMWORK_ADMIN_SITE = "myproject.admin_site.MyAdminSite"
```

The navigation and the actions use Lucide icons, so run `manage.py formwork install`
once, as for the widgets.

### 5. Scripts

The site loads htmx 4, its Alpine bridge and Alpine.js from a CDN. To serve them
yourself, override `scripts` (htmx and the bridge) and `alpine_script` on your site
class.

## The site

`django_formwork.admin.site` is the default site. `FORMWORK_ADMIN_SITE` names its class,
and every app's `admin` module is imported at startup (`FORMWORK_ADMIN_AUTODISCOVER`
changes the module name). Attributes of `AdminSite` that Django's site does not have:

| Attribute | Default | Description |
|---|---|---|
| `stylesheets` | `("formwork/formwork-dist.css",)` | Static paths of the built CSS. |
| `scripts` | htmx 4 and `hx-alpine-compat` | Scripts loaded before the admin's own. |
| `alpine_script` | Alpine.js 3.15 | Loaded last, with `defer`. |
| `themes` | `("light", "dark")` | The DaisyUI themes the theme menu offers. The first is the default. |
| `history` | `ModelHistory()` | Where the history goes; see [History](#history). |

`site_title`, `site_header`, `index_title`, `site_url`, `empty_value_display`,
`enable_nav_sidebar`, `final_catch_all_view`, `login_form`, `password_change_form`, the
`*_template` attributes, `each_context()`, `get_app_list()`, `admin_view()`,
`has_permission()`, `catch_all_view()`, `add_action()` and `disable_action()` work as in
Django. As in Django, any unknown URL under the admin sends a signed-out visitor to the
login page, so the URLs do not show which models are registered.

![The deal list in the dark theme](../img/admin/changelist-dark.webp)

## ModelAdmin

The list, add, change, delete and history pages read the same options as Django's
admin: `list_display`, `list_display_links`, `list_filter`, `list_select_related`,
`list_per_page`, `list_max_show_all`, `list_editable`, `search_fields`,
`search_help_text`, `date_hierarchy`, `ordering`, `sortable_by`, `fields`, `exclude`,
`fieldsets`, `readonly_fields`, `prepopulated_fields`, `radio_fields`,
`autocomplete_fields`, `raw_id_fields`, `formfield_overrides`, `form`, `inlines`,
`actions`, `save_as`, `preserve_filters`, `view_on_site`, the
`has_*_permission()` methods, and the `get_*()`, `save_model()`, `save_formset()`,
`delete_model()` and `response_*()` hooks.

`save_on_top` is accepted and does nothing: the save buttons stay in the bar at the bottom
of the page, which stays in view while the form scrolls.

The delete pages list at most `delete_confirmation_max_display` objects, counted over
all levels as Django counts them. The default is 100, where Django's is `None`. `None`
lists every object, and `0` lists none and keeps only the count per model.

The forms are formwork forms, so every field renders with formwork's widgets and
templates. A relation gets a `Select` or `SelectMultiple`, a date field a `DatePicker`,
and a datetime field a `DatePicker` with a time input next to it. As in Django's admin,
a date is typed in the first format of the language's `DATE_INPUT_FORMATS`, for example
`10.01.2026` in German, and the date filter writes its dates the same way. Lists and
read-only fields show `DATE_FORMAT` and `DATETIME_FORMAT`.

After a failed save, each field error shows under its field, as in Django's admin. A
`form` whose `Meta.error_display` is set keeps that display.

A `form` must subclass `FormworkModelForm`, where Django's admin takes any `ModelForm`.
A system check reports a `form` or an `add_form` that does not. To build on another of
Django's forms, list `FormworkModelForm` after it, so the clean steps of that form run:
`class StaffForm(UserChangeForm, FormworkModelForm)`.

A form or `formfield_overrides` that names one of Django's admin widgets, such as `AdminDateWidget`, `AutocompleteSelect` or
`FilteredSelectMultiple`, gets the formwork widget for the same field. The widget keeps
its attrs, without the classes that only Django's admin CSS reads. `AdminSplitDateTime`
still posts the day and the time apart, so a `SplitDateTimeField` cleans as before. A
subclass of a Django admin widget is kept, with its own markup and scripts. Those scripts
need Django's admin CSS and its `jsi18n/` translations, which this site does not load,
and a subclass of `AutocompleteSelect` raises `NoReverseMatch`, as this site has no
`autocomplete/` URL. Give such a field a formwork widget instead, for example through
`autocomplete_fields`.

A `class Media` on a `ModelAdmin` or an inline adds its CSS and JavaScript to the pages
of that admin, as in Django. Django's admin also loads jQuery on these pages, and this
admin does not, so a script that uses `django.jQuery` does not run here.

![The change form of an employee](../img/admin/change-form.webp)

Options this admin adds:

| Option | Description |
|---|---|
| `icon` | The Lucide icon next to the model in the navigation and the page title. Unset, the model gets a placeholder shape, see below. |
| `list_badges` | Badge colors per value, by column: `{"status": {"active": "success", "archived": "warning"}}`. |
| `list_only_fields` | Load only these columns on the list page. |
| `list_defer_fields` | Skip these columns on the list page, for a large JSON or text column that no column shows. |

`list_only_fields` is opt-in. A `__str__` that reads a deferred field runs one query per
row.

A model without an `icon` gets a plain shape instead: a circle, triangle, square, diamond,
pentagon, hexagon or star. The shape comes from a hash of the model's label, so it stays
the same across restarts, and the models of one app get different shapes while there
are no more than seven of them. Set `icon` on the models you want to tell apart at a
glance and leave the rest to the shapes.

### Related objects

Next to a relation, the change form has buttons that open the related model's admin in
a dialog. Django's admin opens a popup window for the same buttons. They show next to
any widget of the relation: the dropdown, the radio buttons of `radio_fields`, or a
widget from `formfield_overrides`, such as checkboxes or a native select. A hidden
widget gets no buttons, as in Django's admin.

- **Add another** (plus) adds a row. After the save, the dialog closes and the field
  chooses the new row. Every other field that can choose the row lists it too, also in
  inline rows added later.
- **Change selected** (pencil) edits the chosen row, and the field shows its new name.
  With only the view permission, the button is an eye and shows the row. Without a
  chosen row, the button stays in place, dimmed. A many-to-many field has no such
  button.

Each button shows only with the matching permission on the related model's admin. There
is no delete button: delete a row in its own admin.

A relation in the dialog opens the next dialog on top. <kbd>Esc</kbd> or the close
button closes a dialog, and the browser asks first when its form has unsaved changes.
A click with <kbd>Ctrl</kbd> or <kbd>Cmd</kbd>, or with the middle button, opens the
page in a new tab instead.

The dialog loads Django's popup URLs, with `_popup=1` and `_to_field`, so a
`response_add()`, `response_change()` or `response_delete()` that checks for `_popup`
keeps working. A save in the dialog ends on `popup_response_template`, by default
`formwork_admin/popup_response.html`. An override keeps the element with the id
`formwork-admin-popup-response`: the dialog reads the saved row from its
`data-popup-response` attribute.

After a save in the dialog, the change form posts its values to its own URL with
`_refresh` added, and htmx morphs the page with the response. For such a POST,
`changeform_view()` renders the form as posted and saves nothing. Field errors show
only when the page showed them before. An override of `changeform_view()` that acts on
a POST checks for `_refresh` first.

### Filters

The filter bar is a django-filter `FilterSet` that the admin builds from `list_filter`.
An entry can be:

- a field name. Choices, booleans and relations get a dropdown, dates a range picker.
  Its calendar has the ranges of Django's date filter: Today, Past 7 days, This month
  and This year. A nullable date adds No date and Has date.
- a `SimpleListFilter` subclass, as in Django.
- a tuple such as `("field", admin.EmptyFieldListFilter)` or
  `("category", admin.RelatedOnlyFieldListFilter)`.
- a `django_filters.Filter` with its `field_name` set, for any lookup django-filter
  supports. A `django_filters.RangeFilter` shows a min and a max input in one field,
  which post `field__gte` and `field__lte`.

A nullable relation and a many-to-many relation also offer the rows without a related
row, under the admin's `empty_value_display`. A nullable boolean offers Unknown. A
relation lists its rows in the order of the related model's admin and leaves out the rows
that the field's `limit_choices_to` excludes, as Django's filter does.

The filters sit in a row under the search box, in the order of `list_filter`. The
Filters button opens the row and shows how many filters are active. The row is open
when the page loads with an active filter. A list without `list_filter` keeps the button
in the same place, and its row says that the list has no filters.

The search box filters the same way, through `get_search_results()`, so `^`, `=` and `@`
prefixes in `search_fields` work as in Django. A filter on a many-to-many relation picks
one row, as Django's related filter does.

The list updates as the user types or picks, and the URL keeps every filter, the
search, the sort and the page.

The URL uses the parameters of Django's list filters, so a link filters the same rows in
both admins:

| Filter | Parameters |
|---|---|
| Choices and booleans | `status__exact=draft`, `is_active__exact=1`, `field__isnull=True` |
| Relations | `owner__id__exact=3`, `owner__isnull=True` |
| Dates | `created__gte=2026-01-01&created__lt=2026-02-01`, `created__isnull=True` |
| `EmptyFieldListFilter` | `website__isempty=1` |
| `SimpleListFilter` | its `parameter_name` |

A date filter also reads `__lte` and the `__year`, `__month` and `__day` of
`date_hierarchy`. A parameter that no filter reads narrows the list as in Django, such as
`?name__startswith=A`, and stays while the filters change. `lookup_allowed()` refuses a
lookup through a relation that `list_filter` does not name with a 400 response. A lookup
that the list cannot apply returns to the list with `?e=1` and a warning that the list
shows all rows.

With `show_facets` at its default, `admin.ShowFacets.ALLOW`, the filter row has a Show
counts switch. The switch adds `_facets` to the URL, as Django's link does, and each
option then shows how many rows it matches, in a badge at the end of the option. An
option that matches no rows shows 0, dimmed. The count applies the search and the other
filters, but not the filter of the option itself. `ShowFacets.ALWAYS` shows the counts
without the switch, and `ShowFacets.NEVER` removes both.

```python
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_filter = ("status", "owner")
    show_facets = admin.ShowFacets.ALWAYS
```

Each filter with counts runs one more query. Date and number ranges have no counts. A
relation filter that searches its rows on the server shows counts only while all rows
fit on its first page of 20.

### Columns

A click on a column header sorts by that column, and a second click reverses it. The
columns sorted before stay as later sort keys, and with more than one sorted column each
header shows its place in the order. The × next to a sorted header removes its column from
the sort. When the last sorted column goes, the rows follow the admin's `ordering` again
and no header shows a sort, as in Django. The `o` parameter numbers the columns as Django's
does, so a sorted link opens the same order in both admins. `o=2.-1` sorts by column 2,
then by column 1 descending. While the list has actions, the checkbox is column 0. A
column outside `sortable_by` is left out of the sort.

When the columns of `list_display` do not fit the width of the list, the list hides
columns from the right and shows a "+N" button at the end of the header. The checkbox,
the first column and the columns of `list_display_links` always show. The tooltip of
the button names the hidden columns.

The button shows all columns. The table then scrolls sideways, and the checkbox and the
first column stay in view. The browser stores the choice per model, so the list opens
the same way next time.

A `list_editable` error in a hidden column shows all columns and scrolls the first error
into view. Without JavaScript, the table scrolls sideways as in Django's admin.

In a window at least 40rem wide, a long list fits the window: the rows scroll under the
header, and the footer with the page links stays in view. A short list keeps its height.
In a narrow window, in a dialog, or when less than 288 pixels are left for the rows, the
page scrolls as usual.

### Editable columns

The columns in `list_editable` show their fields in each row, as in Django's admin. A cell
whose value differs from the saved one gets the accent color, and a bar at the bottom of
the window counts the changed cells. Save changes saves the rows, and Discard loads the
saved values again. After a failed save, each error shows under its cell, and the cells
with valid changes stay marked.

While cells have unsaved changes:

- the actions wait, and their buttons are disabled until the changes are saved.
- a sort, a filter, a search or another page asks before it replaces the changed cells.
- the browser asks before it leaves the page.

The marks come from formwork's [changed-field highlight](forms.md#changed-field-highlight).

### Info dialog

The info button next to the list's title opens a dialog about the model:

- the row count, from the same paginator as the list, so a large PostgreSQL table
  shows its estimate.
- every entry of `search_fields` with its label and how a word matches: contains,
  starts with, is or full text. `search_help_text` shows above them.
- every field with its type, the related model and flags such as unique, indexed or
  null, and the list's default order.

A superuser also sees the table: its name, the database and its version, the model
and admin classes, the indexes and constraints the database has, and the size of the
rows and the indexes on PostgreSQL, MySQL and on SQLite builds with the `dbstat`
table. The dialog loads from the
`info/` URL the first time it opens, so the list page runs no extra queries. Override
`formwork_admin/change_list_info.html` to change what it shows.

### Actions

`@admin.action` takes two more arguments:

```python
@admin.action(description="Archive selected tickets", icon="archive", danger=True)
def archive(self, request, queryset): ...
```

`icon` names a Lucide icon for the action bar, and `danger` draws the button in the
error color. Actions run as in Django: a function gets `(modeladmin, request, queryset)`
and a name resolves to a method of the admin. The bar appears when a row is selected,
and shift-click selects a range.

The other arguments are Django 6.1's, and they also work on Django 6.0. `location`
puts an action in the list, on the change form or both, and the list labels it with
`description_plural` when given:

```python
from django_formwork.admin import ActionLocation


@admin.action(
    description="Close this ticket",
    description_plural="Close selected tickets",
    location=[ActionLocation.CHANGE_LIST, ActionLocation.CHANGE_FORM],
)
def close(self, request, queryset): ...
```

The change form lists its actions in an Actions menu next to its title. An action there
runs on the saved row: the page reloads with the action's message, or shows the response
the action returns, such as a confirmation page or a file. While the form has unsaved
changes, the menu waits until they are saved. The menu does not show on the add page or
in a related-object dialog.

`get_actions()` and `get_action_choices()` take Django's `action_location`. An override
of `get_actions()` without it keeps working for the list and gives the change form no
actions, as in Django. An action with `permissions` shows when the user has any one of
them.

### Inlines

`TabularInline` and `StackedInline` take Django's options (`extra`, `min_num`,
`max_num`, `fk_name`, `can_delete`, `show_change_link`, `classes`, `form`, `formset`).
Rows are added and removed in the browser, and the formset indexes stay contiguous. An
inline's `form` subclasses `FormworkModelForm`, as the `ModelAdmin`'s does.

With `"collapse"` in `classes`, the inline folds behind its title and row count, as a
fieldset with `"collapse"` does. It starts open when one of its rows has an error.

For a model that points at its parent through a `GenericForeignKey`, import
`GenericTabularInline` or `GenericStackedInline` from `django_formwork.admin.contenttypes`.
They take `ct_field` and `ct_fk_field` as Django's do. An inline class from
`django.contrib.admin` or `django.contrib.contenttypes.admin` fails the system check, and
the error names the class to import instead.

### Export

The Export menu next to the add button writes the list as a CSV, Excel or JSON file. The
file holds every row that the filters and the search let through, in the list's sort
order, not only the current page.

```python
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    export_fields = ["id", "subject", "requester__email", "status", "opened_at", "age"]
    export_formats = ("csv", "xlsx")
```

| Option | Default | Description |
|---|---|---|
| `export_fields` | every field | The columns: field names, `__` lookups, admin methods and callables, as in `list_display`. |
| `export_formats` | `("csv", "xlsx", "json")` | The formats the menu offers. An empty tuple hides the menu. |
| `export_background_threshold` | `5000` | Above this many rows the export runs as a task. `None` keeps every export in the request. |

A foreign key exports the primary key of the related row, a many-to-many field the
sorted primary keys. Excel keeps numbers, dates and booleans as such. JSON writes dates
and decimals as text, as `DjangoJSONEncoder` does. A JSON field stays structured in JSON
and becomes JSON text in CSV and Excel. Excel shows
a datetime in the site's time zone, since Excel has no time zones. The CSV file starts
with a byte order mark, so Excel reads it as UTF-8.

Excel files need openpyxl. Without it, the menu leaves Excel out.

Whoever can see the list can export it. `has_export_permission()` changes that, and
`get_export_fields()`, `get_export_queryset()` and `get_export_formats()` take the
request like the other `get_*()` hooks. A new format subclasses `formats.FileFormat`,
implements `write()` and `read()`, and goes into `formats.FORMATS` under its `name`.

#### Large exports

Above `export_background_threshold`, the admin saves an `ExportJob` and queues it on
Django's task framework after the request's transaction commits. The list then shows a
message with a link to the Exports page. That page is in the account menu. It lists the
user's last 50 exports and refreshes while one still runs. The file goes to the default
storage under `formwork_admin/exports/`, and only the user who started the export can
download it.

The job runs as that user with the list's filters, search and sort, so a
`get_queryset()` that limits the rows per user limits the file too.

Django's default task backend, `ImmediateBackend`, runs the job inside the request, so
the file is ready when the list loads again. For a real background run, set `TASKS` to
a backend with a worker. To use another queue, override `enqueue_export()` on your site:

```python
from celery import shared_task

from django_formwork.admin import AdminSite
from django_formwork.admin.exports import run_export_job


@shared_task
def run_admin_export(job_id):
    run_export_job(job_id)


class MyAdminSite(AdminSite):
    def enqueue_export(self, job):
        run_admin_export.delay(job.pk)
```

The admin does not delete old exports. `ExportJob.delete()` deletes the row and its
file.

### Import

Import is off by default. `import_formats` turns it on and adds an Import button next
to the Export menu:

```python
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    import_formats = ("csv", "xlsx")
    import_id_fields = ["email"]
```

| Option | Default | Description |
|---|---|---|
| `import_formats` | `()` | The formats the Import page reads. An empty tuple hides the button. |
| `import_fields` | the add form's fields | The fields a row sets. Unset, the fields of the add form without the read-only and file fields. |
| `import_id_fields` | the primary key | The fields that find the record a row changes. |

The import page checks a file before it saves anything. Pick a file and click Check
file. The preview counts the new, changed, unchanged and invalid rows, and a click on a
count shows only those rows. A changed cell shows the old and the new value, and an
invalid cell shows its error as in `list_editable`. Import saves the rows in one
transaction and goes back to the list with a summary. While a row has an error, the
Import button stays off: fix the file and check it again.

![The import preview of a contact list](../img/admin/import.webp)

How the file maps to records:

- A header matches a field by its name or its label, in any case. Other columns are
  listed as ignored, so a file exported from the list imports as it is.
- A row whose `import_id_fields` match a record changes that record. A row without a
  match, or with an empty key, adds a new one. Two rows for the same record are an
  error.
- A foreign key column holds the primary key, as the export writes it. A header such as
  `category__name` finds the record by that field instead. A many-to-many column holds
  the keys separated by commas, and `tags__slug` works the same way. A value that
  matches no record or several records is an error.
- A choice column takes the stored value or the label. A boolean column takes `true`
  and `false` or `yes` and `no`.
- A column the file leaves out keeps the record's value on a changed row and gets the
  field's default on a new row. Records the file does not mention stay as they are. An
  import never deletes.
- A row that matches its record is skipped: it is not saved and not logged.

Each row runs through the admin's form in a formwork model formset, so the form's
validation applies. Unique fields are checked across the whole file: two rows with the
same email get the error Django would give, with one query per check instead of one per
row. Saving goes through `save_form()`, `save_model()` and `save_related()`, so an
override that sets an owner still runs. Each saved row gets a history entry with the
values before and after.

The formats:

- CSV in UTF-8, with or without a byte order mark, or in Windows-1252. The delimiter is
  a comma, a semicolon or a tab, whichever the header row has most of. In a file with
  semicolons, a number can use a decimal comma, as a German Excel saves it.
- Excel reads the first sheet. It needs openpyxl.
- JSON reads a list of objects.

Whoever can add or change records can import. Each row is checked again: a new row
needs `has_add_permission()`, a changed row `has_change_permission()` on its record. A
row that fails gets an error. `has_import_permission()`, `get_import_formats()`,
`get_import_fields()`, `get_import_id_fields()` and `get_import_form()` take the request
like the other hooks.

The import keeps no copy of the file between the check and the import. Import sends the
file again, and the server checks it again. If the file or the records changed since the
check, the page shows the new preview instead of importing. The import runs in the
request, so a very large file is better split. The preview shows up to 1,000 rows:
the ones with errors first, then the changed and the new ones. The counts cover every
row.

## Users and groups

With `django.contrib.auth` installed, the site registers admins for `User` and `Group`,
as `django.contrib.auth.admin` does on Django's own site. They work as Django's do:

- Add user asks for a username and a password, or turns password-based authentication
  off. The save opens the change form of the new user for the other fields.
- The change form shows the algorithm and the parameters of the password hash. Its
  button opens a page that sets a new password or turns password-based authentication
  off.
- To add a user, the "Change user" permission is necessary too, because a user who can
  add users can add a superuser.
- The permissions of a group or a user are grouped by model.
- The list refuses a lookup on the password, such as `?password__startswith=pbkdf2`,
  with a 400 response, as a lookup on the hash could read it out.

When `AUTH_USER_MODEL` names another model, only `Group` is registered. For a model that
extends `AbstractUser`, subclass `UserAdmin`:

```python
from django_formwork import admin
from django_formwork.admin.auth import UserAdmin

from .models import Account


@admin.register(Account)
class AccountAdmin(UserAdmin):
    list_display = ("username", "email", "is_staff")
```

`User` and `Group` are registered before the `admin` modules of the apps are imported,
so an app can replace them:

```python
from django.contrib.auth.models import Group, User

from django_formwork import admin
from django_formwork.admin.auth import UserAdmin

admin.site.unregister(Group)
admin.site.unregister(User)


@admin.register(User)
class StaffUserAdmin(UserAdmin):
    list_filter = ("is_active",)
```

`django_formwork.admin.auth` also has `UserChangeForm`, `AdminUserCreationForm` and
`AdminPasswordChangeForm` for `form`, `add_form` and `change_password_form`, and
`GroupAdmin`. The forms are Django's, built on formwork's form classes. A form for a
custom user model subclasses them, as it would subclass Django's.
`change_user_password_template` names the template of the password page.

## History

The change form shows the history of the object to the right of its fields, or below
them on a narrow page. Each entry names the user and the time, and lists the changed
fields with their values before and after the save. A change to an inline row shows under
the row's name. The panel loads `history_per_page` entries at a time, 20 by default, and
its Show older button loads the next ones. The page at `<object_id>/history/` lists the
same entries without the form.

![The history next to the change form](../img/admin/history.webp)

The admin writes the entries to its own table, `formwork_admin.HistoryEntry`, through
`log_addition()`, `log_change()` and `log_deletions()`, as Django's admin writes
`LogEntry`. The dashboard lists the last ten entries of the user as recent actions.
`construct_change_message()` returns Django's list with a `values` key added to each
`changed` item, and `log_change()` still takes a plain text instead of the list.

A value is stored as the form showed it: the name of a related object, the label of a
choice, a localized date. A text longer than 300 characters is cut. A field with a
`PasswordInput` widget, or with `password` in its name, shows without its values.

### pghistory

[django-pghistory](https://django-pghistory.readthedocs.io/) records the changes of a
model with database triggers, so it also sees the changes made outside the admin. To
show its events in the panel, give the site the `PghistoryHistory` backend:

```python
from django_formwork.admin import AdminSite
from django_formwork.admin.history import PghistoryHistory


class MyAdminSite(AdminSite):
    history = PghistoryHistory()
```

For a model that pghistory tracks, the panel then lists the model's events with the
fields each event changed, as pghistory's `pgh_diff` has them. A foreign key shows the
name of the related object, and a choice its label. Each admin view runs inside
`pghistory.context()` with the user and the URL, so an event made through the admin names
its user without pghistory's middleware. A model that pghistory does not track keeps the
admin's own entries, and the recent actions on the dashboard still come from the admin's
table.

Another store needs a subclass of `django_formwork.admin.history.History` with `log()`,
`entries()` and `recent()`, and `context()` to wrap each admin view.

## Templates

Every page is a Jinja2 template under `formwork_admin/`, loaded from the `jinja2/`
directory of each installed app. To override one, put a template with the same path in
an app listed before `django_formwork.admin`:

```
myapp/jinja2/formwork_admin/change_list.html
```

`change_list_template`, `change_form_template` and the other `*_template` options name
Jinja2 templates of the same engine.

## Custom pages

A page of your own gets the admin's layout, navigation and login check. Add its URL in
`get_urls()`, wrap the view in `admin_site.admin_view()`, and render a Jinja2 template
that extends `formwork_admin/base.html`:

```python
from django.urls import path

from django_formwork import admin

from .models import Author


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    def get_urls(self):
        stats = self.admin_site.admin_view(self.stats_view)
        return [path("stats/", stats, name="myapp_author_stats"), *super().get_urls()]

    def stats_view(self, request):
        context = self.page_context(request, title="Author stats", count=Author.objects.count())
        return self.render(request, "myapp/author_stats.html", context)
```

```jinja
{# myapp/jinja2/myapp/author_stats.html #}
{% extends "formwork_admin/base.html" %}
{% import "formwork_admin/macros.html" as m %}

{% block breadcrumbs %}
{{ m.model_crumbs(site, opts, changelist_url) }}
<li class="font-medium">{{ title }}</li>
{% endblock %}

{% block content %}
{{ m.page_header(title, icon_name=model_admin.get_icon()) }}
<div class="card border border-base-300 bg-base-100 p-6">{{ count }} authors</div>
{% endblock %}
```

`page_context()` returns the site's `each_context()`, the model's `opts`,
`changelist_url` and permissions, and the keyword arguments. `render()` renders with
the admin's Jinja2 engine. Put the page's markup in the `content` block: a link inside
the admin swaps only that block. The URL reverses under the site's name, for example
`reverse("admin:myapp_author_stats")`. A page that belongs to no model goes in
`AdminSite.get_urls()`, rendered with `site.render()` and `site.each_context(request)`.

## Performance

- A foreign key column joins only its own relation. Django's admin calls
  `select_related()` without arguments for one, which follows every non-null relation
  five levels deep.
- A relation to a model whose admin has `search_fields` pages its rows from the server.
  The change form no longer loads the whole related table into a `<select>`.
- Without filters, the list counts a PostgreSQL table of more than 10,000 rows from the
  planner's estimate instead of `COUNT(*)`. Any filter or search counts exactly.
  `EstimatedCountPaginator.estimate_threshold` sets the limit.
- A search or filter that can return a row twice keeps the rows unique with a primary
  key subquery instead of `DISTINCT` over every column.
- The filter bar, the search and the paging swap only the list, without a full page
  load.

## Keyboard

| Keys | Action |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>K</kbd> | Filter the navigation |
| <kbd>/</kbd> | Focus the list search |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Save and continue editing |

## Not supported yet

- The raw ID lookup popup. A relation in `raw_id_fields` gets the searchable dropdown,
  with the add and change buttons.
- Prepopulated fields in inline rows.
