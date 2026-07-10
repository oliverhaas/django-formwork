# Changelog

## Unreleased

### Breaking changes

- **Widget-type tokens are snake_case everywhere.** The tokens carried by
  `SearchRegistration.widget_type` and `FormworkSearchView.widget_type` renamed:
  `"multiselect"` → `"multi_select"` and `"combobox"` → `"combo_box"` (`"search_select"` is
  unchanged). The response-template class attributes follow suit: `MULTISELECT_TEMPLATE` →
  `MULTI_SELECT_TEMPLATE` and `COMBOBOX_TEMPLATE` → `COMBO_BOX_TEMPLATE`. The widget module
  `django_formwork.widgets.combobox` renamed to `django_formwork.widgets.combo_box`
  (importing `ComboBox` from `django_formwork.widgets` is unaffected). Widget class names
  stay PascalCase and the DOM CSS classes (`combobox`, `multiselect`, `search-select`) are
  unchanged, so no stylesheet or template overrides break.
- **The auto-search registry is now internal.** `django_formwork.registry` renamed to
  `django_formwork._registry`; `make_key`, `make_choices_key`, `register`,
  `get_registration`, `get_registry`, and `SearchRegistration` are no longer public API.
  The registry key format and registration machinery may change without notice; the public
  surface is the auto-registration behavior on `FormworkForm` / `FormworkModelForm` plus
  `FormworkAutoSearchView` and `include("django_formwork.urls")`.

### Added

- **Uniform top-level import surface.** Every documented public name now resolves lazily
  from the package root: form and formset base classes and factories, fields, view base
  classes, renderers, the async mixins, and `FormworkModel` (whose documented
  `from django_formwork import FormworkModel` previously raised `ImportError`). Imports
  stay lazy via a module-level `__getattr__`, so `import django_formwork` still works
  without configured settings or a ready app registry. Submodule imports keep working;
  the docs now show top-level imports as canonical.

### Security

- **JS-escape every value interpolated into an Alpine `x-data` / expression context.** Alpine
  evaluates the HTML-entity-decoded attribute, so Django's autoescaping alone does not defend.
  Fixed the unescaped interpolations in `date_picker.html` (XSS on validation-error redisplay),
  `otp_input.html` and `input_number.html` (both template engines; `InputNumber` now
  interpolates the value as a quoted, JS-escaped string instead of a raw expression), and in the
  `SEARCH_SELECT_TEMPLATE` / `COMBOBOX_TEMPLATE` htmx response fragments (stored XSS when
  `to_field_name` or labels contain user-editable data).
- **Search registry keys now include the form class and field name** (mirroring choices-backed
  keys). Previously two forms searching the same model + `search_fields` shared one registration
  last-writer-wins, so a public form could silently drop another form's `search_decorator` or
  replace its scoped queryset with an unfiltered one. `make_key()` now takes `form_cls` and
  `field_name` as its first two arguments.
- **`FormworkAutoSearchView` renders with the widget type from the server-side registration**
  (or the subclass attribute) and ignores the client-supplied `?type=` parameter. Widget
  templates no longer send `type` with search requests, and the now-unused
  `FormworkSearchView.VALID_WIDGET_TYPES` attribute was removed.
- **`FormworkValidateView` hardening:** new `validate_decorator` hook (the same access-control
  pattern the search side exposes via `search_decorator`) and a `MAX_TEXT_LENGTH` cap (default
  `50_000` characters, mirroring `MAX_QUERY_LENGTH`) that truncates POSTed text before
  validation.

### Changed

- **`manage.py formwork install` now writes the generated icon CSS into your project's static
  directory** instead of into the installed `django_formwork` package, which failed on
  read-only installs (containers, system-wide pip, Nix). The file lands at
  `<first STATICFILES_DIRS entry>/iconx/icons.css`, falling back to
  `BASE_DIR/static/iconx/icons.css` when `STATICFILES_DIRS` is not set; a new `--output DIR`
  option overrides the directory. Consequently **`formwork.css` no longer imports
  `../iconx/icons.css`**: add `@import "./static/iconx/icons.css";` (adjusted to your static
  dir) next to the formwork import in your Tailwind input. The installation guide and both
  example apps show the updated recipe.
- **Rewrote the installation guide so a fresh install actually works.** It now documents the
  previously missing required steps: `django_iconx` in `INSTALLED_APPS`,
  `manage.py formwork install` (including the new `--output` option), importing only
  `formwork.css` (not Tailwind/DaisyUI a second time) plus the generated icons CSS, and the
  `@source "path/to/django_formwork/"` directive without which Tailwind 4 tree-shakes the
  widget classes and widgets render unstyled.
- **`search_decorator` is typed `Callable | None`** on `SearchSelect`, `MultiSelect`, and
  `ComboBox` (was `Callable | object`). Runtime behavior is unchanged: omitting the argument
  still raises `ImproperlyConfigured` when server-side search is registered.

### Fixed

- **Dropdown widgets no longer drop Django's `aria-describedby`.** `SearchSelect` and
  `MultiSelect` render it on the `<summary>` trigger and `ComboBox` on the combobox input
  (both template engines), so assistive tech now hears the help text and error message that
  Django 6 auto-wires, not just `aria-invalid`.
- **Drop-zone rejection feedback is announced.** The client-side error `<p>` in
  `FileDropZone` and `ImageDropZone` has `role="alert"` (both engines), so "file(s) too
  large" / "wrong type" feedback reaches screen readers.
- **`InputNumber` renders empty for an unbound/`None` value** instead of `0`, and the
  stepper's `inc()`/`dec()` round to the step's decimal precision (stepping `0.2` by `0.1`
  yields `0.3`, not `0.30000000000000004`).
- **`FormworkValidateView` no longer emits a stray empty `<mark>`** when an error span lies
  entirely outside the submitted text (spans clamped to nothing are now dropped).

### Removed

- **`PhoneInput` widget.** Bundling a country dial-code table (with flag emoji) and a bespoke
  prefix picker put application data in the framework, and it emitted a non-normalized
  `"+1 5551234"` string with no validation. Real phone handling belongs to a dedicated library
  such as `django-phonenumber-field`. The `full` example now ships a local `PhoneInput` that
  shows how a project builds one. Removing it also let the bundled country/dial-code dataset
  (`django_formwork/data.py`) be deleted.
- **`CountryInput` widget and `country_choices()`.** The country selector was a thin wrapper
  over `SearchSelect` pre-loaded with an ISO 3166-1 list, and it never validated (choices sat
  on the widget, not the field, so every submitted value was rejected). Country lists are
  application data, not framework data: build a `forms.ChoiceField(choices=...,
  widget=SearchSelect())` from your own list (or a package like `django-countries`). The
  example apps show the pattern.
- **The dead `AsyncModelFormMixin._apost_clean` override.** It was shadowed by the dirty-only
  model form mixin in the MRO of `FormworkModelForm` / `FormworkJinja2ModelForm` and never
  called. Anyone composing `AsyncModelFormMixin` directly with a plain `ModelForm`
  (unsupported) must supply their own `_apost_clean`.

## 0.1.0a2

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
