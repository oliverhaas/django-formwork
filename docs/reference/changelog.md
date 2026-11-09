# Changelog

## Unreleased

### Breaking changes

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
  function of today gives other ranges. `DateTimeRangePicker` adds a start and an end
  time under the calendar.
- `DateTimeRangeField`, which cleans to a `DateTimeRange(start, end)` of two datetimes
  and uses `DateTimeRangePicker`.
- `ClearableFileInput`: a file upload in one row, as high as a text input. It shows the
  stored file as a link with an icon for its type, a Browse or Replace button, and a ×
  button that clears the stored file, with a second button to keep it before the save.
  It posts the same fields as Django's widget, so `widget=widgets.ClearableFileInput`
  is the only change a form needs.

### Changed

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

### Fixed

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
