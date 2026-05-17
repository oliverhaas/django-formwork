# Changelog

## Unreleased

### Fixed

- **Failed server-side searches no longer flash response body / stale prerender into the listbox.** Two related fixes:
    - htmx 4 (beta) changed its `noSwap` default to `[204, 304]`, so 4xx/5xx responses started getting swapped into the swap target — for our dropdowns that meant the Django debug HTML (or any error body) briefly painted in the listbox before our `hasError` handler hid it. Each dropdown's htmx-enabled input now cancels the swap on `before:swap` when `event.detail.ctx.response.status >= 400`.
    - The `hasError = false` reset on `before:request` made the listbox visible again between request and a failed response, briefly re-showing the prerendered "No results" alert. That reset moved into `before:swap` (for status < 400 only), so `hasError` now stays `true` across consecutive failures and only clears when a successful swap actually happens.

### Changed

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
