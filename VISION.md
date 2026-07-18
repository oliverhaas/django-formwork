# django-formwork: Design Vision

Most web apps are mostly forms plus some display views. Django's `django.forms` is the
right abstraction but got stuck in time about a decade back. formwork extends it into a
modern UI layer: server-rendered request/response, htmx + Alpine for interactivity, the
best of both MPA and SPA. Built 100% on htmx 4, DaisyUI 5, and Tailwind 4.

## The ten points

1. **Django forms, but better.** A formwork form is a Django form: same fields,
   `clean()`, `is_valid()`, ModelForm `Meta`. Set `FORM_RENDERER` once and `{{ form }}`
   just works. Almost never any manual wiring: rendering and functionality work like
   normal Django forms, just better and more modern.
   - Layout (fieldsets, rows, tabs, sections) declared on the form class. Opinionated
     styling out of the box with few explicit options; templates/CSS as the manual but
     possible escape hatch.
   - Everything is a form: filters are GET-bound forms, wizard steps are forms, confirm
     dialogs are one-button forms, inline cell edits are bound fields (maybe just one),
     inline tables are formsets.
   - The same form definition renders read-only for detail views (with styling
     improvements), so edit and show never drift.

2. **Nothing plain breaks.** Basic Django widgets and fields are styled automatically.
   No plain Django forms usage may look bad, render wrong, or break in any way.

3. **Styled by default, DaisyUI-native.** One design system, full DaisyUI support in
   every regard, theming through DaisyUI themes. Styling lives partly in global CSS and
   partly in widget templates, whichever is DaisyUI-, Django-, and Tailwind-idiomatic
   for that piece. (Maybe: non-breaking DaisyUI extensions, e.g. finer border-radius
   variables.)
   - **Never override Django's built-in widget templates.** Widget rendering resolves
     through the project's `FORM_RENDERER`, so shadowing `django/forms/widgets/*.html`
     leaks into Django admin and every third-party app, swapping markup out from under
     the JS those widgets rely on (see "the admin stays untouched" below). Built-in
     widgets are improved with **global CSS only**. Widget templates are exclusively for
     formwork's own widgets, which a developer opts into by setting the widget (point 4).
     Never an automatic swap of a built-in.
   - **The one deliberate exception is `SearchInput`.** `django/forms/widgets/search.html`
     is shadowed to wrap the control in a DaisyUI `.input` with a leading magnifier. It
     earns the exception only because it clears every bar the rule guards against: the
     widget carries no JavaScript, the shadow keeps the `<input>` (name, value, attrs)
     structurally intact, and the addition is purely a presentational search affordance.
     A magnifier next to a search box is what "styled by default" should mean, and CSS
     alone cannot inject the icon element. Any future shadow of a built-in must clear the
     same bar; when in doubt, use global CSS.

4. **More widgets with modern functionality.** Real `forms.Widget` subclasses built on
   htmx + Alpine: server-side search selects, multi-select, date picker, drop zones,
   and so on.

5. **Server-side validation, swapped in cleanly.** Validation lives in `Form.clean()`,
   never duplicated in JS. On submit by default (Django-typical), optionally on change.
   The response renders validation errors back, as typical Django, and htmx morph swaps
   them in so inputs, focus, and client-side behavior are preserved.

6. **Partial saves.** A model form can save the fields that validated while returning
   errors for the ones that didn't (name and phone save; the address error comes back).

7. **htmx and Alpine over plain JavaScript, modern HTML and CSS over both.** State
   lives mostly in plain HTML without fancy tricks, so everything stays reliable and
   hard to break.

8. **Opinionated about forms, not about views.** formwork owns form rendering,
   functionality, and styling. How a view produces the form is not its business.

9. **django-filter compatible.** Filters are GET-bound forms; target 100%
   django-filter compatibility, ideally with proper a11y.

10. **Examples are the spec.** Very extensive examples showing how formwork is supposed
    to be used, plus (maybe) a dev-mode gallery rendering every widget in every state.

## Open questions

- Conditional fields (`visible_when=`, `depends_on=`) would be nice but are easy to
  build fragile. Only if we find a design that holds up.
- Partial response handling beyond validation swaps, and `django.contrib.messages`
  under partial updates: unclear. To be settled by prototyping in the examples first,
  written down after.

## Ideas

- Automatic fast skeleton view rendering for forms.
- Tables and list views for almost full applications.

## Non-goals

The admin stays untouched. No auth, no JSON API or React/Vue story, no websockets in
core, no no-JS fallbacks, no other CSS frameworks, no CRUD resource layer, no magic.

## The sweet spot

Old-school Django, finished. Request/response over ordinary forms and links, so the
mental model, testing, auth, and the back button all work the way a Django developer
expects. formwork removes what pushed people to SPAs: hand-written JS, round-trip
friction, unstyled defaults.
