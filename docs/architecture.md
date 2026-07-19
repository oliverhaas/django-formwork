# Architecture

## Design constraints

Django forms render at three levels:

- **Form** (`{{ form }}`): all fields with labels, errors, help text.
- **Field** (`{{ field.as_field_group }}`): one field with label, errors, help text.
- **Widget** (`{{ field }}`): just the bare `<input>`, `<select>`, etc.

Django admin only renders at the widget level. This means:

1. Overriding form or field level rendering is admin-safe.
2. Formwork never overrides a built-in widget template: it would reach admin
   and third-party forms. Built-ins are styled by CSS only; formwork's own
   widgets are opt-in.
3. CSS is independent: admin and frontend load separate stylesheets.
4. CSS styles all form elements globally: standalone inputs get
   DaisyUI styling without needing `{{ form }}`.
5. CSS must be easily overridable: use `@layer components` so users
   can override with utility classes or unlayered CSS.
