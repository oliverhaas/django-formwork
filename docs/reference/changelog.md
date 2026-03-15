# Changelog

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
- **Idiomorph integration** (`formwork.js`) — Preserves Alpine.js state, `<details>` open state, `x-text`/`x-html` content, and `x-for`/`x-if` generated nodes during htmx morph swaps
- Django 5.2, 6.0 support; Python 3.12, 3.13, 3.14
