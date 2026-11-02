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

## Rendering

`FormworkRenderer` is a `TemplatesSetting` renderer. It renders `{{ form }}`
with `formwork/forms/div.html` and each field group with
`formwork/forms/field.html`, and it loads every template through the project's
`TEMPLATES`. A full render and an htmx swap of the search results therefore
resolve the same template, and a project overrides any formwork template from
its own template directories. Formwork uses its own template paths: shadowing
`django/forms/div.html` from inside an app would change every form in every
project that installs formwork.

## Widget design rules

These rules keep each widget in one place and each fix in one file. Follow
them for a new widget and for a change to an existing one.

| # | Rule | Reason |
|---|---|---|
| R1 | A widget has one class, one template, and at most one Alpine component. Add no fourth place. | Python builds the context, the template holds the markup, and the JS module holds the behaviour. |
| R2 | Check `field.widget_type` in no template except `field.html`. Add a branch there only when the widget cannot do the work. | Django takes the field wrapper from `Field.template_name` or the renderer, never from the widget. So only the wrapper can branch (single checkbox, toggle). |
| R3 | A widget template has no `<script>`, not even a small one. Register the behaviour with `Alpine.data(name, …)` in an `alpine:init` listener, import the module in `formwork.js`, and list it in the widget's `Media`. The template only names it: `x-data="formworkSelect"`. | A template that needs `document.currentScript`, a `window.load` listener, or a global from another library has its behaviour in the wrong file. |
| R4 | Follow Django's hierarchy. Subclass for the data contract, share the template, and override only the block that differs. `SelectMultiple` is a thin subclass over the shared `SearchableSelectMixin`. A domain variant, such as a project's own country select, subclasses `Select` and changes only the choices. When only the look of an option differs, return a `ChoiceLabel` and add no widget. | Django's own `SelectMultiple` is three lines over `Select`. |
| R5 | Declare a widget by class, never with a `multiple=True` kwarg. | `Meta.widgets` and `ModelMultipleChoiceField.widget` name a class, so the class is the contract. |
| R6 | Factor out shared behaviour and markup. Do not copy it. A variant extends the base template and overrides one block. The shared dropdown mechanics live once in `dropdownBase()` in `widgets/_helpers.js`. | Each fix then goes in one place. |
| R7 | An inline Alpine attribute is one call: `onToggle()`, `onNav($event, 1)`, `matches($el)`. Move the value into the module if it contains `;`, `const`, `new …`, or a JS literal built from `{{ }}`. Put a repeated attribute block in one `x-bind` object on the shared base. Pass values through `data-*` attributes. | `'{{ v\|escapejs }}'` inside an expression parses only if escapejs escaped every quote. Bad: `x-show="!search \|\| '{{ option.label\|escapejs }}'.toLowerCase()…"`. Good: `x-show="matches($el)" data-label="{{ option.label }}"`. |
| R8 | Use native HTML first, Alpine second, and a library last: `<details>`/`<summary>` for a dropdown, `<input type=search>` for a filter, `<button>` for an action. | The browser gives keyboard support and accessibility. |
| R9 | Put the `id` on the focusable control. A hidden input that has the field `id` is a bug. | `<label for>` must point to an element that the user can click. |
| R10 | Keep server concerns in Python. A template builds no URL and no query parameter. Option markup goes through the `#option_list` partial. | htmx swaps and full renders then use one code path. |
| R11 | The look of a widget is in its template, not in the Python class. A caller's `attrs={"class": …}` is only for a one-off variant. Add a CSS component class only after the same variant appears on a third page, and restate every hover and focus state in it. | DaisyUI state rules win over a plain component class. |
| R12 | Name a widget after the primitive. Use Django's name for a drop-in replacement. Add a prefix only when two widgets coexist for one primitive. Do not name the library, the look, or a behaviour that is automatic. | See [Widget names](#widget-names). |

## Widget names

| Name | Reason |
|---|---|
| `Select`, `SelectMultiple` | Django's names. Search appears past `search_threshold`, so it is not part of the name. |
| `TextInput`, `PasswordInput`, `DateInput` | Drop-in replacements, so no prefix. |
| `StepperNumberInput`, `SuffixNumberInput` | Two number inputs coexist, so both have a prefix. |
| `CardRadioSelect`, `CardCheckboxSelectMultiple` | The form is a card. "Big" would be subjective. |
| `ToggleInput` | The semantic. "Pill" would name the skin. |
| `SearchInput`, `ComboBox` | `input type=search` and the ARIA term. |
| `CountrySelect` | A domain choice set, not a rendering variant. Formwork ships no domain widgets; a project builds one from `Select`. |
| ~~`CalendarDateInput`~~ | Rejected: names the calendar library. |
| ~~`ComponentCheckboxSelectMultiple`~~ | Rejected: "Component" says nothing. |

The names shadow `django.forms` on purpose. Widget modules write
`forms.Select`, and callers write `from django_formwork import widgets` and
`widgets.Select`.

## Adding a widget

1. Subclass the closest Django widget and set `template_name`.
2. Compute the context in `get_context`. Keep the classes and the copy in the template.
3. If the widget needs behaviour, add one `Alpine.data` module.
4. For a variant, extend the base template and override one block.
5. For server search, build on `SearchableSelectMixin`, so the form registers the search and `FormworkSearchView` serves it. Write no URL and no view.
