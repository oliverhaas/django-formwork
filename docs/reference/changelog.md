# Changelog

## Unreleased

### Breaking changes

- formwork needs Django 6.1. Projects on Django 6.0 can keep `django-formwork==0.1.0a3`
  until they upgrade Django.
- `DateRangeInput` and its `formwork/widgets/date_range.html` template are removed, so a
  form that uses `widgets.DateRangeInput` fails at import. `DateRangeField` takes
  Django's own `MultiWidget`, and two `DateInput`s in one show the same native inputs
  side by side:

  ```python
  period = DateRangeField(
      widget=forms.MultiWidget(
          [
              widgets.DateInput(attrs={"aria-label": _("From")}),
              widgets.DateInput(attrs={"aria-label": _("To")}),
          ]
      ),
  )
  ```

- A `Select`, `SelectMultiple`, `DatePicker`, `DateTimePicker`, `DateRangePicker` or
  `DateTimeRangePicker` starts its Alpine component on first use: a press, focus, a
  key, or its list opening. A script that calls `Alpine.$data()` on such a widget
  before then gets no component, and a write to its `data-value` or `data-selected`
  does not show until the widget starts. Dispatch `formwork:start` on the widget's
  root first, as the [widget reference](widgets.md#requirements) shows. If you
  override one of the widget templates, copy it again for the `data-formwork-lazy`
  attribute. Without it, the widget starts on load as before.

- `formset.as_rows()` renders the formset's management form. Remove a
  `{{ formset.management_form }}` that a template adds next to the table: the form
  counts would post twice, and Add another changes only the table's own.
- An overridden `formwork/tables/table.html` or `formwork/tables/row.html` gets a new
  context: `headers` and `rows` in place of `header_fields` for the table, and for a
  row its `cells` are the bound fields and `hidden` holds the hidden inputs.
  `form.row_cells()` is removed, and `form.get_row_context()` takes keyword arguments.
  Copy the templates again from the package, or extend `row.html` and override its
  blocks. `form.row_id` and `form.row_hidden_inputs` stay for hand-authored rows.
- `form.as_row()` without an argument renders a row that does not save. It no longer
  reads a `save_url` that an earlier `as_rows(save_url)` set on the form, so pass the URL:
  `form.as_row(save_url)`.
- A project template under `templates/formwork/` or `templates/django/forms/` no longer
  overrides formwork's or Django's form templates. Formwork's form, field, widget and
  table templates, and the admin's `formwork_admin/widgets/` templates, are Jinja2
  templates now, and `FormworkRenderer` renders them and Django's built-in widget
  templates with a Jinja2 engine of its own. To keep an override of a formwork template,
  convert a fresh copy of the package's template to Jinja2 and put it at the same path in
  the `jinja2/` directory of an app listed before `django_formwork`. Django's built-in
  widget templates cannot be overridden this way. The fresh copy has new context names,
  such as `widget.max_size_text` and `table.empty_text`, because `makemessages` finds no
  text in a Jinja2 `{% trans %}` block. `TEMPLATES` needs no `DjangoTemplates` entry for
  formwork, and `jinja2` moves from the `admin` extra to the package's dependencies.
- Code that rendered the option rows of a select with
  `formwork/widgets/select.html#option_list` fails with `TemplateDoesNotExist`. The rows
  are templates of their own, `formwork/widgets/partials/select_options.html`,
  `select_multiple_options.html` and `combo_box_options.html`, which each widget names in
  `option_list_template_name`.
- In a table, the selects of a column with the same choices in every row open empty if
  your project overrides `formwork/tables/table.html`, the admin's
  `formwork_admin/change_list_results.html`, `formwork/widgets/select.html` or
  `select_multiple.html`. Copy them again from the package: the table templates render
  `{{ option_lists }}` and `{{ cl.option_lists }}`, and the select templates leave out
  their option rows when `widget.options_template_id` is set.

### Added

- `MultipleFileField` for several uploads in one field. A plain `FileField` with a
  `multiple` `FileDropzoneInput` failed validation with "No file was submitted" as soon
  as a file was picked. `MultipleFileField` uses that drop area by default and cleans to
  a list of files.
- `DateRangePicker`: a start and an end date in one control, typed or picked in a
  calendar with two months side by side. The days between the two picks fill in, and the
  footer counts them. A typed date can be in the format the input shows, in a
  `DATE_INPUT_FORMATS` format or ISO, and month names can be short or lowercase.
  `presets=True` adds Today, Past 7 days, This month and This year buttons, and a
  function of today gives other ranges. `choices` adds options that are not a range,
  such as No date, posted as a third value. `DateTimeRangePicker` adds a start and an
  end time under the calendar.
- `DateTimeRangeField`, which cleans to a `DateTimeRange(start, end)` of two datetimes
  and uses `DateTimeRangePicker`.
- `DateTimePicker`: a day and a time in one text input for a `DateTimeField`, picked in a
  calendar with a time input under it, with Now, Clear and Done buttons. The input shows
  `SHORT_DATETIME_FORMAT` or the `format` you pass and reads typed text in that format
  and in `DATETIME_INPUT_FORMATS`. A hidden input posts `YYYY-MM-DDTHH:MM` in the
  current time zone, which `DateTimeField` reads as it is.
- `ClearableFileInput`: a file upload in one row, as high as a text input. It shows the
  stored file as a link with an icon for its type, a Browse or Replace button, and a ×
  button that clears the stored file, with a second button to keep it before the save.
  It posts the same fields as Django's widget, so `widget=widgets.ClearableFileInput`
  is the only change a form needs.
- `Select` and `SelectMultiple` take `badges=True`, which shows each option as a badge in
  the `color` of its `ChoiceLabel`, in the list and in the closed trigger. The admin
  sets it for a field with `choices`, so a form's select and a list filter show a
  value as the list's column does, in the colors of `list_badges`.
- `Select` and `SelectMultiple` take `search_label`, a `callable(obj, **params)` that
  labels the rows of a server search, so a search that several fields reuse can label
  its rows by the params of each field.
- `Select` and `SelectMultiple` take `counts`, a mapping of option values to numbers.
  Each option shows its number in a badge at the end of the row, as a faceted filter
  does, and an option with 0 is dimmed.
- `data-formwork-dirty` marks a changed field outside a fieldset, such as a widget in a
  table cell: put `data-formwork-field` on the element around it. A field that the
  server renders with `data-formwork-changed` stays marked, so the page can start from
  posted values after a failed save. The form sends a `formwork:dirty` event with the
  number of changed fields. See [Forms](forms.md#changed-field-highlight).
- After a failed save, a form with `data-formwork-dirty` keeps the marks on the fields
  the user changed, also on a field with an error, so the count includes them and
  leaving the page still asks first. The error color covers the accent. Formwork's
  field template sets `data-formwork-changed` on each changed field, except a file
  field. If you override `formwork/forms/field.html`, copy it again.
- `--formwork-dirty-color` and `--formwork-dirty-content` set the color of the
  changed-field marks, accent by default. See
  [Forms](forms.md#changed-field-highlight).
- `django_formwork.admin` (experimental): a Django admin on formwork forms,
  django-filter, htmx and Jinja2, styled with DaisyUI. It keeps the options, hooks, URL
  names and permissions of `django.contrib.admin`, so an `admin.py` ports by importing
  `from django_formwork import admin`. Install it with `django-formwork[admin]` and see
  [Admin](admin.md) for the setup. A list exports to CSV, Excel or JSON, and a long list
  exports in a background task, so run `migrate` after you add the app. With
  `import_formats` set, a list also imports CSV, Excel or JSON files: a preview shows
  the new, changed and invalid rows before anything is saved. Columns that do not fit
  the width of a list hide behind a button that shows them all. A long list scrolls with
  the page, and its toolbar and header stick under the top bar. In a list with `list_editable`, a field
  shows its box only in the row under the pointer or with the focus, so the list reads
  as a table, and a changed cell shows in the accent color. The toolbar above the table
  counts the changes and saves or discards them. A cell's error shows in a tooltip, here
  and in a `TabularInline`, so a failed save keeps the height of the rows. With
  `django.contrib.auth` installed, the admin has pages for users and groups, with the
  password page of Django's user admin. A list's first three filters follow its search
  box in one row, and a More menu holds the others and Clear all filters. The Export
  menu and the add button end that row, next to the list. A Show counts switch
  in that menu shows the number of rows for each filter option, as `show_facets` does in
  Django. Dates are
  typed in the language's first `DATE_INPUT_FORMATS`, in a calendar dropdown, and a
  datetime field picks its day and time in one calendar, typed in the first
  `DATETIME_INPUT_FORMATS` without the seconds. The buttons next to a relation add a row
  or change the chosen one in a dialog, where Django's admin opens a popup window. A
  `form` must subclass `FormworkModelForm`, and a system check names one that does not.
  Django's admin widgets on a `form` render as formwork's. An inline shows its saved
  rows in pages of `per_page`, 10 in a table and 5 in a stack by default, with a pager
  next to Add another. The rows of a list or an inline load the choices of a relation
  once for all rows. A form or formset that can change them per row needs
  `share_choices`, which system check `formwork_admin.E504` reports. The rows of a page
  load a relation that they read with one query for all rows, through Django's
  `FETCH_PEERS` fetch mode, which `fetch_mode` on an admin or an inline changes.
  `list_select_related` is not needed and not read. `annotate` on `@admin.display`
  computes a column's count or sum for the rows of the page only, where an annotation
  in `get_queryset()` computes it for every row that the filters keep. Generic inlines
  come from `django_formwork.admin.contenttypes`.
  A `class Media` on an admin or an inline loads its files, without Django's jQuery. `@admin.action` takes Django 6.1's `location` and
  `description_plural`, and the change form shows its actions in an
  Actions menu. The other ways to save sit in a menu next to Save, and the way an add or
  change form of a model was last saved becomes its main button. The delete pages group
  the related objects per model and list the first few of each, and they build the name
  and link of the listed objects only. A list that the search
  or the filters leave empty offers to clear them. The change form shows the history of
  the object next to its fields, with the values before and after each change. The admin
  keeps that history in its own table, so it does not need `django.contrib.admin`, and
  with `history = PghistoryHistory()` on the site it reads the events of
  django-pghistory. Each model also gets a history list of all changes of its rows,
  with filters and the export, which `history_admin` sets up with a `HistoryAdmin`
  subclass. The recent actions on the dashboard list each object once, with what
  its saves changed. The toolbar above a list's table holds the selected count, the
  actions and the save, and stays in view while the list scrolls. `list_top` and `list_bottom` methods
  show HTML of their own above and under a list, such as counts or a chart, and
  `change_top` and `change_bottom` do the same on a change page.
  `@admin.slot(lazy=True)` loads a slot after its page, with a skeleton until then.
  A button next to a list's title hides its top slot and shows it again. The session
  keeps the choice for each list, and a hidden slot does not run.
  With `choice_description` on a model's admin, the dropdown of every relation to that
  model shows those values under each row's name, such as a job title and a department
  under an employee.
- A widget can put links at the end of its field's label row, for example a Generate link
  next to a slug, with a `label_links(name, value, renderer=None)` method that returns
  HTML. The field template renders them after the label, not inside it, so they stay out
  of the field's accessible name. The admin puts a relation's Edit and Add links there.
- `formset.as_rows()` edits a whole formset in one table, as the admin's tabular inline
  does. Add another appends a row from the formset's `empty_form`, a new row has Remove,
  and with `can_delete` a saved row has a Delete toggle that fades the row and strikes it
  through. A required column has a red asterisk, and the help text shows in a tooltip on
  the column's header. A cell keeps its errors in a tooltip under the widget, so an
  invalid row keeps its height, and a changed cell shows the marks of
  `data-formwork-dirty`. `can_add = False` on the formset class removes Add another, and
  `as_rows(flush=True)` lays the table out to the edges of a card. The rows need
  `tables.js`, which `{% formwork_js %}` and `{{ formset.media }}` load. With a
  `save_url`, each row still saves by itself, without Add another, Remove or Delete.
  A formset method `row_url(form)` links each row to its own page.
  See [Templates](formsets.md#templates).
- `DisplayField` shows a value that a form never posts: a field, a method, a property or
  an annotation of the form's instance, or a function of the instance. It renders with
  the `Display` widget, and as text in a cell of `formset.as_rows()`. The field reads its
  value when the page renders it, so an annotation that the view adds after the post
  shows. A post that names the field changes nothing, because formwork's forms leave it
  out of `cleaned_data`. See [DisplayField](forms.md#displayfield).
- An admin list renders the `Select`, `SelectMultiple`, `ComboBox`, `ComboBoxMultiple`,
  `DatePicker`, `DateTimePicker`, `DateRangePicker` and `DateTimeRangePicker` of each
  saved row of its editable columns as a stub: the closed widget with its value. When the
  pointer rests on a stub, or the stub takes the focus or a press, the full widget loads
  from the new `cells/<field>/` view (URL name `<app_label>_<model_name>_cell`) and takes
  over the focus, the typed text and the press. The view builds the row with the list's formset, so the row keeps
  the choices that a hook gives it. After a failed save, only the fields with an error
  render in full. `list_editable_stubs = False` on the `ModelAdmin` renders the full
  widgets. The saved rows of a `TabularInline` render the same stubs on a change form,
  also for a relation field next to its add and change buttons. They load from the new
  `<object_id>/cells/<field>/` view (URL name
  `<app_label>_<model_name>_change_cell`); `stubs = False` on the inline renders the
  full widgets. Outside the admin, `formset.as_rows(cell_url=...)` renders the same
  stubs, with the new `FormworkCellMixin` as the view behind `cell_url`. Tests that read
  the options of a select in a list or an inline from the rendered page request the cell
  instead, or turn the stubs off. See
  [Widgets that load on use](admin.md#widgets-that-load-on-use) and, for `as_rows()`,
  [Widgets that load on use](formsets.md#widgets-that-load-on-use).
- `makemessages` reads a template in a `jinja2` directory with Jinja's parser, so it
  collects the text of the admin's pages and of your own Jinja2 templates. Django's
  command reads every template with the Django template lexer, which finds no text in a
  Jinja2 `{% trans %}` block or in a `_()` call with arguments. See
  [Translations](../getting-started/installation.md#translations).

### Changed

- Saving a model formset ran one query per row to find the row of its posted primary
  key, one per row and many-to-many field for the values the form starts from, and two
  per row and foreign key to find and check the posted row. A Formwork formset now runs
  each of them once for all rows: an admin list of 100 rows with two relation columns
  saves with 8 queries instead of 404. See [Formsets](formsets.md#loading-the-rows).
- A select whose option labels read a relation, such as
  `f"{city.name} in {city.region}"` in `label_from_instance`, ran one query per option.
  `Select`, `SelectMultiple` and the server search of every dropdown now load the rows
  with Django's `FETCH_PEERS` in place of the default `FETCH_ONE`, so the relation loads
  for all rows with one query. A queryset that sets another fetch mode, such as
  `FETCH_RAISE`, keeps it.
- `DateRangeField` shows one control with a range calendar instead of two native date
  inputs. It posts the same `<name>_0` and `<name>_1` ISO dates, so views and tests that
  post the form need no change. Browser tests that fill the two inputs do. To keep the
  native inputs, pass the `MultiWidget` from Breaking changes.
- The `DatePicker` calendar is larger and has a month and a year view, Today and Clear
  buttons and arrow-key navigation. The week starts on `FIRST_DAY_OF_WEEK` instead of
  Sunday. The picked day is filled in the primary color, and today's number is in
  primary text. The panel opens in the top layer, so a container with hidden overflow
  no longer clips it. If you override `formwork/widgets/date_picker.html`, copy it
  again.
- `ImageDropzoneInput` looks like `FileDropzoneInput` again: the same dashed area,
  height, "Drag and drop an image here or browse" prompt and round × remove button. The
  "Upload Image" button is gone, since a click anywhere on the area opens the file
  picker, and a click on the preview picks another image. The preview has a thin border,
  so a white image shows its edge, and the checkerboard behind transparent images is
  lighter. If you override `formwork/widgets/image_dropzone.html`, copy it again.
- Django's own `ClearableFileInput` took four lines: the stored file name, the clear box,
  "Change:", and the file input. It takes two now: the file name and a
  smaller clear box, and the file input under the name. If you override
  `formwork/forms/field.html`, copy it again.
- `FileDropzoneInput` shows an icon for the type of the picked file, such as a PDF,
  a spreadsheet or an image, where it showed the same file icon for every file. If you
  override `formwork/widgets/file_dropzone.html`, copy it again.
- A focused input, select or textarea draws its border and focus ring in the primary
  color, like its floating label. DaisyUI draws them in the text color, so focus showed
  as a black or white ring. This covers the built-in widgets and `.input`, `.select` and
  `.textarea` written in your own markup. A color modifier such as `input-error` or the
  accent of a changed field still wins.
- A link in a field's help text or error message is underlined. Tailwind's preflight
  showed it as plain text.
- With `data-formwork-dirty`, a changed group of checkboxes or radio buttons marks only
  the options whose checked state changed. Every option of the group took the accent
  color. A radio change marks the old and the new option. After a failed save, the
  field template sends the first checked options in `data-formwork-initial`, so checking
  them again drops the marks. If you override `formwork/forms/field.html`, copy it again.
- A `Select` or `SelectMultiple` with a server search loads its first page when its list
  opens, and shows a spinner until the rows arrive. The page held those rows from the
  start, so a form with many such selects was large and slow to start: on an admin list
  with 100 editable rows the HTML went from 3.9 MB to 2.9 MB. A list that fits one page
  keeps its rows in the page and filters them in the browser, and a selected option past
  the first page still comes with the page. The search endpoint takes `page_only=1` for
  this request, which leaves out the "more results" hint. The spinner row is
  `formwork/widgets/partials/pending_rows.html`. Tests that read the rows of a long list
  from the rendered page open the list first, or request the endpoint.
- The row that clears a `Select` or `SelectMultiple` with `allow_clear` shows the
  widget's placeholder in muted text, the way the empty control shows it. It showed
  Django's blank label, which Django 6.1 changed from "---------" to "- Select an
  option -" and which also widened the control. A field's own `empty_label`, such as
  "Unassigned", still shows as is. The admin's optional choice fields and relations get
  the placeholder. If you override `formwork/widgets/select.html` or
  `formwork/widgets/select_multiple.html`, copy it again for the muted row.
- An empty floating `Select` with `allow_clear` shows the label of its clearing row when
  the field sets one, such as an `empty_label` of "Unassigned". It showed "Select…",
  which it still shows for Django's blank label.
- The end of a long `Select`, `SelectMultiple` or `ComboBox` list shows a "Load more"
  row in the style of the option rows. The info alert with "Showing the first 20
  matches. Keep typing to narrow them down." and its button made a narrow dropdown
  wrap over three lines and widened it. The `shown` count is gone from the context of
  `formwork/widgets/partials/more_results_hint.html`; if you override that template,
  copy it again.
- A form with a `Select` or `SelectMultiple` that searches on the server renders faster
  when the list is longer than one page. The widget labels only its selected rows,
  because the browser loads the first page when the list opens. A
  `label_from_instance()` that counts its calls sees fewer of them.
- An admin list with editable columns was slow to render: the example Event list, 100
  rows with six editable columns, took about 390 ms on the server and sent 3.0 MB of
  HTML. The Jinja2 templates bring it to 240 ms. With the stubs from Added it takes
  110 ms and sends 0.65 MB, with the same seven queries.
- `formset.as_rows()` ran one query per row for each `Select`
  or `SelectMultiple` of a relation that lists all its choices: 100 rows with three such
  columns ran 203 queries. The rows now list the choices once, with 7 queries, and render
  in 207 ms instead of 282 ms. Rows whose form or formset defines a hook that can give a
  row choices of its own, such as `__init__` or `get_form_kwargs`, or whose field has a
  callable `limit_choices_to`, keep their query per row. In the admin, `share_choices`
  decides as before.
- A `DatePicker`, `DateTimePicker` or range picker translates its month and weekday names
  once per language, not once per widget, which saves about 12 ms on 100 rows.
- The selects of `formset.as_rows()`, of a tabular admin inline and of an editable admin
  list repeated every option in every row. A column whose rows list the same choices now
  renders them once, in a `<template>`, and each row's list copies them when it first
  opens. 100 rows with three such columns render in 122 ms instead of 205 ms and send
  2.0 MB of HTML instead of 5.3 MB. A column of a relation qualifies when its rows share
  their choices, as in the entry above. A column of fixed choices qualifies unless the
  form or formset has a hook that can change them. A list longer than one page, which
  loads from the server search, a stub and the row of Add another keep their own options.
- The hidden copy of the option labels that sizes a `Select`, `SelectMultiple` or
  `ComboBox` is one line of text per label, where it was one element per label. The
  widths stay the same, and the example Event list has 12% fewer elements for the
  browser to lay out. A badge select keeps one element per label. Overrides of
  `formwork/widgets/select.html`, `select_multiple.html` and `combo_box.html` keep
  working.

### Fixed

- An input inside a DaisyUI `<label class="input">` wrapper, such as a search field with
  an icon, drew a second border and padding inside the wrapper. Formwork's input styles
  now skip inputs inside the wrapper, and the wrapper takes the error border when its
  input is invalid.
- After a click on an option of a `SelectMultiple`, the focus left the widget for the
  page. Escape no longer closed the list, and the arrow keys no longer moved through
  it. The focus now stays in the widget. If you override
  `formwork/widgets/select_multiple.html`, copy it again.
- A click on the calendar button of a `DatePicker` left other dropdowns open, such as a
  `Select` or the calendar of a second `DatePicker`, so two panels could overlap. If you
  override `formwork/widgets/date_picker.html`, copy it again.
- A `size-*` class on an icon, such as `<i class="icon icon-x size-4">`, had no effect.
  Formwork's fallback size for icons was outside the cascade layers, so it beat every
  Tailwind utility. It is in `@layer base` now.
- The days of a `DatePicker` calendar sat at the left edge of the panel when the panel
  was wider than one month. They are centered now. If you override
  `formwork/widgets/partials/calendar.html`, copy it again.
- The × button of a `SearchInput` took clicks while the field was empty. It is dimmed
  and disabled until the field has text, also after an htmx swap changes the value.
- The × button in the search field of a `Select` or `SelectMultiple` dropdown cleared
  the search only on a mouse click. Enter and Space on it did nothing. If you override
  `formwork/widgets/partials/dropdown_search.html`, copy it again.
- The buttons inside a field showed no focus ring when reached with Tab: the × button
  of `SearchInput`, the reveal button of `PasswordInput`, the arrows of
  `StepperNumberInput` and the calendar button of `DatePicker`. Each draws a ring around
  its icon now. If you override `formwork/widgets/search_input.html` or
  `formwork/widgets/password_input.html`, copy it again.
- `DatePicker(format="%d.%m.%Y")` keeps its format after a pick in the calendar. The
  input showed `13.07.2026`, and a click on a day changed it to `2026-07-13`. A date in
  the widget's format also validates where the language has no such input format: on
  an English page, an unchanged `13.07.2026` failed with "Enter a valid date." The
  widget reads its format back and hands the field an ISO date. If you override
  `formwork/widgets/date_picker.html`, copy it again for the new `data-format`.
- The error icon next to a `pattern_hint` was blank after `manage.py formwork install`
  fetched Lucide 1.68 or later, which renamed `circle-alert` to
  `circle-exclamation-point`. The hint uses the new name. Run `formwork install` again
  if your icon set is older than 1.68. If you override
  `formwork/widgets/partials/pattern_hint.html`, copy it again.
- The label of a `RadioSelect`, a `CheckboxSelectMultiple` or a `MultiWidget` sat 4px
  higher than the label of a field next to it in the same row. The two line up now.
- After an htmx morph, a checkbox, a radio button, a native `<select>` or a text field
  kept the state that a click, typing or a script had given it, even when the server
  rendered another one. A list that gained a choice could show the wrong choice as
  checked and post it, and a field the server answered empty kept the typed text. The
  morph now applies the server's state to every control except the focused one, also
  where the server's HTML for the field is the same as before.
- An htmx morph of the form, such as an autosave, disturbed the dropdown of a `Select`,
  `SelectMultiple` or `ComboBox`. It replaced the results of a search through
  `search_url` with the options of the form's own render, dropped the option that the
  arrow keys had highlighted, and rebuilt the option rows and the hidden inputs of a
  `SelectMultiple`. When the server sends back the same choice, the dropdown now stays
  as the user left it. If you override `formwork/widgets/select.html`,
  `formwork/widgets/select_multiple.html` or `formwork/widgets/combo_box.html`, copy it
  again.
- A `RadioSelect` or `CheckboxSelectMultiple` inside a wrapper widget, one that holds it
  in its `widget` attribute like Django admin's `RelatedFieldWidgetWrapper`, rendered
  without the stacked choice list. `BoundField.widget_type` names the wrapped widget
  now.
- With `data-formwork-dirty`, a field kept its changed mark after an htmx morph of an
  element around the form, such as the page content, even when the server sent the
  saved value back. The marks compared against the values from before the morph. They
  now start again from the values the server sent.
- With `data-formwork-dirty`, a changed `ToggleInput` showed no mark, most visibly
  when it was turned off: DaisyUI's `toggle` class in its markup won over the changed
  color. The switch now takes the changed color, on or off.
- In a dark theme, the dropdown of a `Select`, `SelectMultiple` or `ComboBox` showed no
  hover on an option and no mark on the option the arrow keys reached. The option took
  `base-200`, which DaisyUI's dark theme draws almost like the panel. It now mixes 10%
  of `base-content` into the panel, as DaisyUI's menu does.
- In Chromium-based browsers, inside a focusable element such as a
  `<main tabindex="-1">` for a skip link, a press on the scrollbar of a `Select` or
  `SelectMultiple` closed the list, so the list could not be scrolled with the mouse. A
  press on an empty part of a `DatePicker` calendar closed the calendar too. The
  browser moved the focus to the element around the widget, and the widget took that
  for a move to another control. The panels stay open now, and a list keeps the focus
  in its search field. If you override `formwork/widgets/select.html` or
  `formwork/widgets/select_multiple.html`, copy it again.
- A form with many selects or date pickers, such as a formset with a hundred rows, froze
  the page for seconds while it loaded. Each option row of a `Select`, `SelectMultiple`
  or `ComboBox` had four Alpine bindings, and each date picker built its calendar on
  load. Each binding cost more the more controls the form held, because the browser
  drops its index of the form's controls after every change to the form. The rows
  of a list now share one effect, and a date picker builds its calendar when it first
  opens. With the lazy first page under Changed and the start on first use under
  Breaking changes, an admin list with 100 editable rows went from 7.9 s of script on
  load to 0.06 s. If you override
  `formwork/widgets/select.html`, `formwork/widgets/select_multiple.html`,
  `formwork/widgets/combo_box.html` or `formwork/widgets/partials/calendar.html`, copy
  it again: the row helpers `matches()`, `isHighlighted()`, `optionClass()` and
  `optionId()` are gone.

## 0.1.0a3 (2026-11-06)

### Breaking changes

- **Widget, search and setup rework.** Every project needs code changes for this
  upgrade. Rename the widgets, move server-side search onto the widget, add
  `"django.forms"` to `INSTALLED_APPS`, and load htmx's alpine-compat extension. If you
  override formwork templates, copy them again from the new paths.
    - Rename the widgets: `SearchSelect` → `Select`, `MultiSelect` → `SelectMultiple`,
      `ComboBox(multiple=True)` → `ComboBoxMultiple`, `Toggle` → `ToggleInput`,
      `PasswordReveal` → `PasswordInput` (the show button is on by default,
      `reveal=False` drops it), `InputNumber` → `StepperNumberInput`, `FileDropZone` →
      `FileDropzoneInput`, `ImageDropZone` → `ImageDropzoneInput`. `ComboBox` takes
      `ChoiceLabel` suggestions in place of its `icons=` and `descriptions=` dicts.
    - Rename the Alpine components: `formworkSearchSelect` → `formworkSelect` and
      `formworkMultiSelect` → `formworkSelectMultiple`. `OTPInput` renders one input with
      `length` slots and needs no JavaScript.
    - Rename the templates: `django/forms/formwork.html` → `formwork/forms/div.html` and
      `django/forms/formwork_field.html` → `formwork/forms/field.html`. Each widget
      template is named after its widget module: `search_select.html` → `select.html`,
      `multi_select.html` → `select_multiple.html`, `input_number.html` →
      `stepper_number.html`, `password_reveal.html` → `password_input.html`,
      `drop_zone.html` → `file_dropzone.html` and `image_upload.html` →
      `image_dropzone.html`. The dropdown root classes are `formwork-select` (was
      `search-select`), `formwork-select-multiple` (was `multiselect`) and
      `formwork-combobox` (was `combobox`), so update CSS that targets the old classes.
    - `FormworkRenderer` is a `TemplatesSetting` renderer, so a template in your
      project overrides the formwork one. It needs `"django.forms"` in
      `INSTALLED_APPS` and a `DjangoTemplates` backend that finds app templates. See
      [Installation](../getting-started/installation.md).
    - A `Select`, `SelectMultiple`, `ComboBox` or `ComboBoxMultiple` searches on the
      server when it gets `search_queryset`, a callable that takes the request and returns
      the rows. `search_fields` names the columns to match, and `search_decorator` (an
      auth decorator, or `None` for a public search) is required. A `FormworkForm` or
      `FormworkModelForm` class registers the search when Python creates it, and the app
      imports the `forms` module of every installed app at startup. The endpoint returns
      20 rows, the dropdown adds a "Load more" button, and no `COUNT` query runs.
      `search_ranked=True` orders matches by quality on PostgreSQL (pg_trgm) and raises
      `ImproperlyConfigured` on other databases. `search_key` with `search_params` reuses
      one registered search for fields built in `__init__`. `FormworkSearchView` is
      final, and an anonymous request for an unknown key redirects to `LOGIN_URL`. See
      [Server-side search](views.md#server-side-search).
    - Load htmx, then `dist/ext/hx-alpine-compat.min.js`, then `{% formwork_js %}`,
      then Alpine with `defer`. Without alpine-compat a morph strips the state that
      Alpine bindings wrote into the page. An `htmx.config.extensions` whitelist must
      list `alpine-compat` and `formwork-morph`, plus `formwork-sections` on a page with
      section forms. A morph cannot open or close a `<details>` or `<dialog>`, because
      `open` is in `htmx.config.morphIgnore`.
    - The Jinja2 support is removed (`FormworkJinja2Renderer`, `FormworkJinja2Form`,
      `FormworkJinja2ModelForm`, `formwork_jinja2_environment` and the `jinja2/`
      templates). So are the `search_choices_<field>` form methods,
      `FormworkAutoSearchView` and the `widget_type` tokens, and
      `FormworkModelChoiceField`, `FormworkModelMultipleChoiceField` and
      `FormworkModelChoiceIterator` with the `icon_from_instance` and
      `description_from_instance` arguments of the fields. Return a
      `ChoiceLabel` from a plain `ModelChoiceField.label_from_instance()` instead.
      `ChoiceLabel` lives in `django_formwork.widgets.select`, and you can import it from
      `django_formwork` and `django_formwork.widgets`.
    - The new widgets are `SuffixNumberInput`, `DateInput`, `DateRangeInput` with
      `DateRangeField` and `DateRange` (in `django_formwork.fields`, and importable from
      `django_formwork`), `Display` for read-only values, `CardRadioSelect`,
      `CardCheckboxSelectMultiple`,
      `CheckboxInput(text=...)`, `CheckboxSelectMultiple(columns=...)`,
      `ComboBoxMultiple` and `PatternHintMixin`. `TextInput` takes `input_type=`,
      `Textarea` takes `floating=`, and `SearchInput` takes `show_spinner`, `show_clear`
      and `filter_items`. `Select` and `SelectMultiple` take `allow_clear` and
      `floating`. See [Widgets](widgets.md).
    - `section_forms()` and the `{% formwork_section %}` tag let several forms on one
      page autosave their own fields of one row. Load `{% formwork_sections_js %}` after
      htmx on those pages, and give each form
      `hx-sync="closest [data-section-forms]:queue all"`. See
      [Section forms](forms.md#section-forms).
    - `Meta.mandatory` marks a field that a save accepts empty but a later step needs.
      Its label gets the red `*` and its widget gets `aria-required`, as on a required
      field. A string in place of a list, or a name that is not a field of the form,
      raises `ImproperlyConfigured` when Python creates the form class.
    - Every string formwork shows goes through Django's translation functions, plurals
      included. Formwork ships no catalog, so run `makemessages` in your project. The
      JavaScript reads its texts from `data-*` attributes and needs no JavaScript
      catalog. The CSS takes the `[more]`/`[less]` label of the help-text toggle from the
      `data-more` and `data-less` attributes of its `<summary>`, so an override of
      `formwork/forms/field.html` must keep them.
    - Some widgets look different. `error_display = "auto"` is the default, so a field
      with help text shows its error inline and a field without help text shows it in a
      tooltip. To keep one style, set `"inline"` or `"tooltip"` in `Meta` or pass
      `error_display=`. `ToggleInput` puts its label beside the switch, dimmed while off.
      Checkbox and radio groups render as a plain stacked list, each label as wide as its
      text. A disabled dropdown trigger is greyed out. The open panel is at most 288px
      high and shrinks to stay inside the viewport, and the caret points up while it is
      open. The dropdown search box has a magnifier and a clear button, and shows past 10
      options instead of from 20. The password button shows the current state: an open eye
      while the password is visible. `ImageDropzoneInput` shows the field label and an
      "Upload Image" button. `OTPInput` is one `<input>` drawn as digit slots, in place
      of one input per digit.
    - Required fields keep the red `*` and optional fields get no marker. The dropdowns
      keep their caret, compact rows and "Select…" placeholder, and the closed
      `SelectMultiple` keeps the option icons.

- **`django_formwork.widgets.combobox` renamed to `django_formwork.widgets.combo_box`.**
  Importing `ComboBox` from `django_formwork.widgets` is unaffected. The rework removes
  the widget-type tokens (`"search_select"`, `"multiselect"`, `"combobox"`),
  `SearchRegistration.widget_type`, `FormworkSearchView.widget_type` and the
  `SEARCH_SELECT_TEMPLATE`, `MULTISELECT_TEMPLATE` and `COMBOBOX_TEMPLATE` attributes,
  and it changes the dropdown root classes.
- **The 0.1.0a2 search registry is gone.** `django_formwork.registry`, `make_key`,
  `make_choices_key`, `register`, `get_registration`, `get_registry` and
  `SearchRegistration` are removed. The public surface is the `search_queryset` argument
  of the widgets, the `django_formwork.search` module and `include("django_formwork.urls")`
  (see the rework above).
- **Help text is escaped.** A plain `help_text` string with HTML tags shows the tags as
  text. Formwork 0.1.0a2 rendered it as HTML, and Django's own templates still do. Build
  help text that needs markup with `format_html()` or `mark_safe()`. A help text built
  from user data cannot inject markup. See [Forms](forms.md#help-text).

### Added

- **Editable tables.** `as_row()` renders a `FormworkForm`/`FormworkModelForm` as a
  table `<tbody>`, and `as_rows()` renders a formset as one editable `<table>`. Pair
  them with the new `FormworkRowSaveMixin` view mixin for per-row htmx autosave: each
  row posts only its own changes (keyed on the posted pk) and re-renders in place. The
  view needs `queryset` or `get_queryset(request)` with the rows the user can change, and
  a pk outside it gets a 404. The form gets `request.FILES`, and the view takes URL
  kwargs. Override the markup at `formwork/tables/row.html` and
  `formwork/tables/table.html`.
- **Model formsets that check uniqueness in one query per check.**
  `formwork_modelformset_factory` and `formwork_inlineformset_factory` build formsets
  whose `unique`, `unique_together` and `unique_for_date` checks against the database run
  once for all rows, not once per row. The errors, their messages and their placement
  match Django's. The forms they build are exempt from `FORMWORK_FORCE_ASYNC`: in an
  async view, wrap `formset.is_valid()` and `save()` in `sync_to_async`. See
  [Formsets](formsets.md).
- **System checks for the setup.** `manage.py check` reports `django_formwork.E001` when
  a form declares a server-side search but the URLconf does not include
  `django_formwork.urls`, and `django_formwork.E002` when `"django.forms"` is missing
  from `INSTALLED_APPS`. Both mistakes used to show up only on the first search or
  render.
- **Django 6.1 support.** CI runs the suite on Django 6.0 and 6.1.
- **Native `<select multiple>` keeps Django's rendering.** A plain
  `forms.SelectMultiple` rendered through the formwork renderer stays a native
  `<select multiple>`. Use `widgets.SelectMultiple` for the dropdown.
- **`error_display` Meta option for field error rendering.** `FormworkForm` and
  `FormworkModelForm` accept `error_display = "auto"` (default), `"inline"` or
  `"tooltip"`. `"inline"` renders the error below the widget in the error color, with
  the icon and the toggle of the help text. `"tooltip"` uses the DaisyUI tooltip, and
  `"auto"` picks inline when the field has help text and the tooltip otherwise. The
  collapsed line shows only the truncated error, and the `[more]` toggle expands the
  full error and the help text. Another value raises `ImproperlyConfigured` when Python
  creates the form class. See [Forms](forms.md#error_display).
- **`ImageDropzoneInput` shows the stored image.** The widget previews the field's
  stored file, or `preview_url` when set. On an optional field its remove button posts
  `clear_<name>`, so the field cleans to `False` and a model form empties it, as with
  `ClearableFileInput`. After a remove the drop area comes back, and a file picked there
  replaces the stored one. See [Widgets](widgets.md#imagedropzoneinput).
- **Uniform top-level import surface.** The form and formset base classes and factories,
  `section_forms`, `DateRangeField` and `DateRange`, `ChoiceLabel`, `FormworkBoundField`,
  `FormworkRenderer`, `FormworkSearchView`, `FormworkValidateView`,
  `FormworkRowSaveMixin`, `FormworkModel` and the async mixins import from
  `django_formwork`. The widgets stay in `django_formwork.widgets`. A module-level
  `__getattr__` imports each name on first access, so `import django_formwork` works
  without configured settings or a ready app registry. Submodule imports keep working,
  and the docs show the top-level imports.
- **`validate_dirty_only` skips validation of unchanged fields.** Set it in `Meta` or pass
  it to the form. A field the user did not change skips its validators, its
  `clean_<field>()` method and the model checks, and keeps its stored value. On a
  `FormworkModelForm` the model needs `get_dirty_fields()`: inherit the new abstract
  `FormworkModel`, or mix in `filthyfields.DirtyFieldsMixin`. The package adds a
  dependency on `django-filthyfields`. A model form whose model lacks
  `get_dirty_fields()` raises `ImproperlyConfigured` when Python creates the form class.
  See [Forms](forms.md#validate_dirty_only).

### Security

- **No template value reaches an Alpine expression.** Alpine evaluates the attribute after
  the browser decodes its HTML entities, so Django's autoescaping does not protect a value
  inside `x-data` or another expression. In 0.1.0a2 a field value could run as script in
  `date_picker.html` (when a form with a validation error rendered again), `otp_input.html`
  and `input_number.html`, and a user-editable label or `to_field_name` value could do the
  same in the `SEARCH_SELECT_TEMPLATE` and `COMBOBOX_TEMPLATE` search responses. The
  templates pass values through autoescaped `data-*` attributes, and the search rows
  render through the `option_list` partial of each widget template.
- **Each form field gets its own search registration.** In 0.1.0a2 two forms that searched
  the same model with the same `search_fields` got one registry key, and the form that
  registered last won. A public form could drop the `search_decorator` of another form or
  replace its scoped queryset with an unfiltered one. The key comes from the module,
  the class and the field name of the form, and from where `search_queryset` and
  `search_decorator` are defined, so forms that a factory builds over one model keep
  their own search. `search_queryset` must be a callable that filters through the
  request it gets. A second form of the same name whose `search_queryset` closes over
  other values raises `ImproperlyConfigured`, and so does a `search_queryset` that is not
  callable (the message names the field).
- **The search endpoint renders only formwork's own row templates.** The `widget` query
  parameter must be `select`, `select_multiple` or `combo_box`, and the endpoint returns
  404 for any other value. The `type` parameter and the
  `FormworkSearchView.VALID_WIDGET_TYPES` attribute are removed.
- **`FormworkValidateView` takes a `validate_decorator` and caps the text length.**
  `validate_decorator` wraps the view, as `search_decorator` does for the search view.
  `MAX_TEXT_LENGTH` (default `50_000` characters) truncates the posted text before
  validation, as `MAX_QUERY_LENGTH` does for a search query.

### Changed

- **Targets the stable htmx 4.0.1 release.** The installation guide, the full example, and
  the e2e harness load `htmx.org@4.0.1` (was `4.0.0-beta3`). If you load htmx yourself,
  bump your pin; formwork's templates and `formwork-core.js` need no changes. npm still
  tags htmx 2 as `latest`, so pin `@4.0.1` explicitly instead of loading an unversioned
  `htmx.org` URL.
- **`{% formwork_css %}` is deprecated and goes away in 0.2.0.** The tag links
  `formwork.css` as it ships, but the file is Tailwind input, so the browser applies none
  of its styles. Import `formwork.css` from your Tailwind input and link the built CSS.
  The tag raises a `DeprecationWarning`.
- **`django_formwork.FormworkChoiceLabel` from 0.1.0a2 still imports.** It resolves to
  `ChoiceLabel` with a `DeprecationWarning` and goes away in 0.2.0. Use `ChoiceLabel`.
- **`DatePicker` and `InputMask` bind to shipped Alpine.data components.** If you override
  their widget templates, copy them again: `x-data` holds only the component name. The
  components are `formworkDatePicker` and `formworkInputMask` in
  `formwork/widgets/date_picker.js` and `input_mask.js`. They read their configuration from
  autoescaped `data-*` attributes: `data-value` (`DatePicker`) and `data-mask`
  (`InputMask`). Each widget class declares the module in its `Media`, so
  `{% formwork_core_js %}` with `{{ form.media }}` loads it. The templates drop their
  `escapejs` filters, because no value passes through a JavaScript expression any more.
  `OTPInput` needs no JavaScript.
- **`StepperNumberInput`, `PasswordInput` and `ValidatedTextarea` bind to shipped
  Alpine.data components.** If you override their widget templates, copy them again:
  `x-data` holds only the component name. The components are `formworkStepperNumber`,
  `formworkPasswordInput` and `formworkValidatedTextarea` in
  `formwork/widgets/stepper_number.js`, `password_input.js` and `validated_textarea.js`.
  `StepperNumberInput` reads `data-min` and `data-integer` and takes `max` and `step` from
  its `<input>`. `ValidatedTextarea` reads `data-has-errors`, and `PasswordInput` takes no
  configuration. Each widget class declares its module in `Media`.
- **`FileDropzoneInput` and `ImageDropzoneInput` bind to shipped Alpine.data components.**
  If you override `file_dropzone.html` or `image_dropzone.html`, copy them again: `x-data`
  holds only the component name. The components are `formworkFileDropzone` and
  `formworkImageDropzone` in `formwork/widgets/file_dropzone.js` and `image_dropzone.js`.
  They read the size limit from `data-max-size`, and the template leaves the attribute out
  when the widget has no limit. Each widget class declares its module in `Media`. The
  server does not repeat the type and size checks of the browser, so validate the upload
  in the form. No widget template has an `x-data` object literal, and `formwork.js`
  imports every widget module, so `{% formwork_js %}` and a bundler import of
  `django_formwork/static/formwork/formwork.js` load the new files.
- **`manage.py formwork install` writes the generated icon CSS into your project's static
  directory.** In 0.1.0a2 it wrote into the installed `django_formwork` package, which
  fails on a read-only install (containers, system-wide pip, Nix). The file lands at
  `<first STATICFILES_DIRS entry>/iconx/icons.css`, or at `BASE_DIR/static/iconx/icons.css`
  when `STATICFILES_DIRS` is not set. The new `--output DIR` option sets the directory.
  `formwork.css` does not import `../iconx/icons.css` any more, so add
  `@import "./static/iconx/icons.css" layer(components);` (with your static directory)
  next to the formwork import in your Tailwind input. The layer lets the `size-*`
  utilities override the 1em icon size. The installation guide and the `full` example
  show the recipe.
- **The installation guide lists every required step.** These are `django_iconx` in
  `INSTALLED_APPS`, `manage.py formwork install` with its `--output` option, and a
  Tailwind input that imports `formwork.css` and the generated icon CSS, without a second
  import of Tailwind or DaisyUI. `formwork.css` registers the package templates, widgets
  and scripts with `@source`, so your Tailwind input lists only your own sources.
- **A type checker accepts only a callable or `None` for `search_decorator`** on `Select`,
  `SelectMultiple`, `ComboBox` and `ComboBoxMultiple` (was `Callable | object`). Runtime
  behavior is unchanged: a form with a `search_queryset` widget and no `search_decorator`
  raises `ImproperlyConfigured` when Python creates the form class.
- **Help text renders as one truncated line with a leading info icon.** When the text
  overflows, a `[more]`/`[less]` toggle at the end of the line expands or collapses it.
  If you override `formwork/forms/field.html`, copy it again: the help text sits in a
  `<details class="formwork-disclosure">`, and its `<summary>` carries the `data-more` and
  `data-less` labels.

### Fixed

- **`ValidatedTextarea` posts only its text to the validate endpoint.** htmx 4 has no
  `hx-params`, so each check while typing posted every field of the enclosing form,
  with any files picked in it. It posts `text`, `field_name` and `errors_id` only.
- **Screen readers name the `FileDropzoneInput` by its field label.** The keyboard
  focus went to a drop area named only "Choose files", while the field label, help text
  and error state sat on a hidden file input. The file input takes the focus, and the
  drop area shows the focus ring.
- **Dropdowns close on any click outside.** `Select` and `SelectMultiple` close when a
  click lands anywhere outside the open panel, including the trigger of another dropdown,
  so opening a second dropdown closes the first.
- **The dropdown placeholder stays muted on focus.** The "Select…" placeholder of
  `Select` and `SelectMultiple` keeps its muted color when the trigger has focus.
- **Dropdown option rows invert on press, and the closed trigger keeps its border.**
  A pressed option shows its active state, and the trigger keeps its border while the
  panel is open.
- **Dropdown widgets keep Django's `aria-describedby`.** `Select` and `SelectMultiple`
  render it on the `<summary>` trigger and `ComboBox` on the combobox input, so a screen
  reader reads the help text and the error message that Django 6 links to the field, in
  addition to `aria-invalid`.
- **Screen readers announce a rejected drop.** The client-side error `<p>` in
  `FileDropzoneInput` and `ImageDropzoneInput` has `role="alert"`, so a screen reader
  reads the "too large" and "wrong type" messages.
- **`StepperNumberInput` renders empty for an unbound or `None` value** in place of `0`.
  The buttons round to the decimals of the step, so stepping `0.2` by `0.1` gives `0.3`,
  not `0.30000000000000004`.
- **`FormworkValidateView` emits no empty `<mark>`** when an error span lies entirely
  outside the submitted text. The view drops a span that clamps to nothing.
- **`FormworkValidateView` works behind a URL with kwargs.** A validate view routed as
  `validate/<field>/` raised a `TypeError` on every post. The URL kwargs reach the view
  as `self.kwargs`.
- **`ais_valid()` runs a sync `clean_<field>()` or `clean()` that queries the
  database.** Such a method raised `SynchronousOnlyOperation`, because `ais_valid()`
  called it inside the event loop. Sync methods run in a worker thread, and async ones
  are still awaited.
- **Your own `<details class="dropdown">` keeps its behavior.** `formwork.css` laid a
  full-page click overlay over every open DaisyUI `details.dropdown` and removed the
  focus ring of every input inside a `.dropdown-content`. Both rules apply only to the
  formwork `Select` and `SelectMultiple` now. A project dropdown that relied on the
  overlay to close on an outside click needs its own handler, for example
  `@click.outside="$el.open = false"` with Alpine.
- **`InputMask` keeps its text through a morph.** A morph emptied the visible text of
  every `InputMask` without focus. Backspace after a literal removes the character
  before it, typing in the middle shifts the rest, and a `+1` mask no longer reads its
  own `1` as a typed digit.
- **Typing fast sends the last keystrokes.** Text typed into the search box of a
  `Select`, into a `ComboBox` or into a `ValidatedTextarea` while a request was pending
  never reached the server, so the list showed the results of an older query. The newest
  request now waits in a queue and runs after the pending one.
- **A `Select` or `SelectMultiple` takes the server's answer to a pick.** After a pick
  the widget turned away every morph whose value differed from the pick, so a server
  that changed or reset the value was ignored. Only the answer to a request sent before
  the latest pick is turned away now.
- **Escape closes only the dropdown.** Escape in an open `Select`, `SelectMultiple`,
  `ComboBox` or `DatePicker` panel inside a `<dialog>` closed the dialog too. It closes
  the panel and puts the focus back on the trigger. Moving the focus to another control
  closes the panel.
- **Screen readers announce the picked and the highlighted option.** `aria-selected` sits
  on the option row, and the search box of a `Select` and the `ComboBox` input point at
  the highlighted row with `aria-activedescendant`. A `Select` with its own `id` in
  `attrs` is named by its label and its value; it pointed `aria-labelledby` at an id no
  element had.
- **Labels name the `DatePicker` and the floating `PasswordInput` alone.** Screen readers
  read "Due date Toggle calendar" and "Password Show password", because the toggle
  button sat inside the label.
- **A `Select` keeps the attrs you pass.** `data-*`, `hx-*`, `autofocus`, `title` and
  other attrs were dropped. `data-*` and `hx-*` go on the hidden input that holds the
  value and fires `change`; the rest go on the trigger.
- **A `SelectMultiple` with one malformed past-page key keeps its other selections.**
  The bad key hid every selection past the first page. A `Select` no longer posts a value that no option holds behind the placeholder, so an
  optional field can be saved again.
- **A `Select` on a `ModelChoiceField` without a blank choice runs one query.** Django's
  required-attribute check ran the queryset a second time.
- **`TextInput(attrs={"type": "email"})` renders `type="email"`.** The widget and
  subclasses that set `input_type` rendered `type="text"`.
- **`ValidatedTextarea` keeps a leading blank line.** The value lost it on every render,
  and autosave posted the shorter text.
- **`DatePicker(format="%d/%m/%Y")` opens the calendar on the stored date.** It opened on
  the current month with no day picked.
- **The `StepperNumberInput` buttons leave a readonly value alone**, and a decimal `min`
  works under a locale with a decimal comma.
- **`Rating` can go back to unrated.** The clear radio never rendered checked and stayed
  enabled on a disabled field. The stars get `required`, `aria-invalid`, `aria-required`
  and a caller class.
- **`SuffixNumberInput` keeps a caller `style`.** The prefix padding replaced it.
- **`ComboBox` sends the typed text as `q` only.** The request also carried it under the
  field name, so a field named like a search param broke the search. A `(value, label)`
  pair in the suggestions raises `ImproperlyConfigured`; it rendered as a group with one
  suggestion per letter.

### Removed

- **`PhoneInput` widget.** Bundling a country dial-code table (with flag emoji) and a bespoke
  prefix picker put application data in the framework, and it emitted a non-normalized
  `"+1 5551234"` string with no validation. Real phone handling belongs to a dedicated library
  such as `django-phonenumber-field`. The `full` example has a local `PhoneInput` that
  shows how a project builds one. The country and dial-code dataset
  (`django_formwork/data.py`) is removed with it.
- **`CountryInput` widget and `country_choices()`.** The country selector was a thin wrapper
  over `SearchSelect` with an ISO 3166-1 list, and it never validated: the choices sat on
  the widget, not the field, so the form rejected every submitted value. Country lists are
  application data. Build a `forms.ChoiceField(choices=..., widget=widgets.Select())` from
  your own list or from a package such as `django-countries`. The `full` example shows the
  pattern.
- **The dead `AsyncModelFormMixin._apost_clean` override.** The dirty-only model form
  mixin shadowed it in the MRO of `FormworkModelForm`, so nothing called it. If you
  combine `AsyncModelFormMixin` directly with a plain `ModelForm` (unsupported), supply
  your own `_apost_clean`.

## 0.1.0a2 (2026-05-18)

### Added

- Documentation for six widgets that already shipped in 0.1.0a1 but were missing from the reference: `CountryInput`, `DatePicker`, `InputMask`, `InputNumber`, `OTPInput`, `PhoneInput`.

### Changed

- Tightened support window to Python 3.14 and Django 6.0 (was Python 3.12+ / Django 5.2+ in 0.1.0a1). Pin `django-formwork==0.1.0a1` if you need the wider range.
- **`formwork.js` is now an ES module** — `{% formwork_js %}` emits `<script type="module" src="...">` so the file's internal imports of `formwork-core.js` and `widgets/*.js` resolve. Users who reference `formwork.js` directly (without using the template tag) must add `type="module"` to their `<script>` tag.
- **Page-global core split into `formwork-core.js`** — the htmx morph extension, dirty-tracking, and native-validation disabling now live in their own file, loaded via the new `{% formwork_core_js %}` template tag. `{% formwork_js %}` still works exactly as before (it imports `formwork-core.js` plus the three widget modules); the split lets users on `{{ form.media }}` load only the core they need.
- **Per-widget `Media.js`** — `SearchSelect`, `MultiSelect`, and `ComboBox` now declare `class Media: js = ...` so their Alpine.data component code is included automatically via `{{ form.media }}`. Three loading paths now coexist: `{% formwork_js %}` (one-tag bundle), `{% formwork_core_js %}` + `{{ form.media }}` (per-form), or `import "django-formwork/formwork.js"` from a JS bundler (django-vite, webpack, esbuild). ES module URL dedup makes the paths safely composable.
- **Migrated to htmx 4** — The package now targets htmx 4 (currently beta). The standalone `idiomorph-ext.min.js` dependency is gone (htmx 4 has morph in core). User-facing changes:
    - Form templates now use `hx-swap="outerMorph"` (was `hx-swap="morph:outerHTML"` + `hx-ext="morph"`)
    - Bundled examples and the e2e harness load `htmx.org@4.0.0-beta3` (was `@2`)
    - `formwork.js` registers a `formwork-morph` htmx extension instead of monkey-patching `Idiomorph.morph()`
    - All `hx-on::` attribute event names switch from dash to colon (`config-request` → `config:request`, etc.); `hx-on::send-error` consolidates into `hx-on::error`
    - `htmx:afterSwap` / `htmx:afterSettle` event listeners renamed to `htmx:after:swap` / `htmx:after:settle`
- Users on htmx 2 should pin the previous django-formwork version.

### Fixed

- **Failed server-side searches no longer flash response body / stale prerender into the listbox.** Two related fixes:
    - htmx 4 (beta) changed its `noSwap` default to `[204, 304]`, so 4xx/5xx responses started getting swapped into the swap target — for our dropdowns that meant the Django debug HTML (or any error body) briefly painted in the listbox before our `hasError` handler hid it. Each dropdown's htmx-enabled input now cancels the swap on `before:swap` when `event.detail.ctx.response.status >= 400`.
    - The `hasError = false` reset on `before:request` made the listbox visible again between request and a failed response, briefly re-showing the prerendered "No results" alert. That reset moved into `before:swap` (for status < 400 only), so `hasError` now stays `true` across consecutive failures and only clears when a successful swap actually happens.

## 0.1.0a1 (2026-03-15)

First alpha release.

### Added

- **FormworkRenderer** — Custom form renderer that applies DaisyUI-styled templates to all forms via `FORM_RENDERER` setting
- **FormworkForm / FormworkModelForm** — Convenience base classes for per-form styling
- **Form template** (`formwork.html`) — Renders each field inside `<fieldset class="fieldset">` with labels, help text, and error tooltips
- **Field template** (`formwork_field.html`) — Single source of truth for field rendering with DaisyUI tooltip errors
- **CSS architecture** — All DaisyUI classes applied via `@apply` in `formwork.css` (inside `@layer components`), not in Python or templates
- **Template tags** — `{% formwork_css %}` and `{% formwork_js %}` for including static assets
- **Custom widgets:**
    - `Toggle` — Checkbox as DaisyUI toggle switch
    - `Range` — HTML5 range slider
    - `Rating` — Star rating with radio inputs (with optional clear button)
    - `PasswordReveal` — Password input with show/hide toggle (Alpine.js)
    - `SearchSelect` — Single-select dropdown with text search (static or htmx)
    - `MultiSelect` — Multi-select dropdown with checkboxes (static or htmx)
    - `ComboBox` — Text input with autocomplete suggestions (static or htmx, single or multiple)
    - `DataList` — Text input with native `<datalist>` suggestions
    - `FileDropZone` — Drag-and-drop file upload with size/type validation
    - `ImageDropZone` — Drag-and-drop image upload with preview
    - `ValidatedTextarea` — Textarea with server-side validation and word highlighting
- **Server-side views:**
    - `FormworkSearchView` — Base view for dropdown search endpoints
    - `FormworkValidateView` — Base view for textarea validation with `<mark>` highlighting
- **htmx morph integration** (`formwork.js`) — Registers a `formwork-morph` extension that preserves Alpine.js state, `<details>` open state, `x-text`/`x-html` content, focused-input values, and `x-for`/`x-if` generated nodes during htmx morph swaps
- Django 5.2, 6.0 support; Python 3.12, 3.13, 3.14
