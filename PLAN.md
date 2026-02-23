# django-formwork

Better Django forms -- modern styling out of the box, then HTMX integration for dynamic behavior.

## Problem

Django's built-in form rendering is ugly and barebones. Every project either reaches for django-crispy-forms (heavy, template pack ecosystem, no HTMX) or writes custom templates for every form. Then adding HTMX for real-time validation and dependent fields requires more boilerplate on top. There's no single package that gives you good-looking forms with modern interactivity.

## Approach: two phases

### Phase 1: Better form rendering and styling

A form renderer / widget library that makes Django forms look good by default, without requiring per-form template work.

- Custom form renderer that outputs clean, semantic HTML -- no extra CSS classes needed on the markup
- **Global CSS approach**: style form elements via element selectors and structural pseudo-classes (`input[type="text"]`, `input:invalid`, `fieldset > div`, `.errorlist`, etc.) rather than requiring utility classes on every element. The first approach is a single CSS file that makes any Django form look good just by being included
- CSS is pluggable -- the renderer outputs semantic HTML, the stylesheet is a separate concern. Ship a default theme, but users can swap in their own CSS (Tailwind, Bootstrap, custom) without changing any Python code or templates
- Proper error display: inline per-field errors, styled error states, accessible aria attributes
- Field grouping and layout: horizontal, vertical, inline, fieldsets -- via simple Python API, not templates
- Widget improvements: better select, date picker, file upload, multi-checkbox -- all with modern UX
- Works with Django's built-in form rendering (template-based renderer, introduced in Django 4.0+)
- Zero JavaScript dependency in this phase -- pure server-rendered HTML + CSS

```python
# Goal: this just works and looks good
class ContactForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)

# In template:
{{ form }}  # Already styled, accessible, with proper error display
```

### Phase 2: HTMX integration

Build on the styled forms with HTMX 4 (beta) for server-side validation and dynamic behavior. The main goal is simplifying the server-side validation workflow -- HTMX makes it trivial to validate a field on blur by posting to the server and swapping the field's error display, but wiring this up in Django today is pure boilerplate.

**idiomorph** (HTMX's morphing extension, default in HTMX 4) is central to this -- it intelligently merges DOM changes rather than replacing them, which means we can re-render the entire form server-side and let idiomorph figure out what changed. No need for surgical partial HTML responses per field. This massively simplifies the server side: the view just re-renders the form, idiomorph handles the diff.

- Target HTMX 4 from the start (idiomorph built-in, cleaner attribute API)
- Server-side validation on blur: widget emits `hx-post` on blur, view validates the form, returns the full re-rendered form, idiomorph morphs only the changed parts (error messages, field states)
- View mixin that handles both full form submission and HTMX validation requests -- single view, no separate validation endpoints
- Dependent field updates (e.g. country -> city) -- same pattern: re-render full form, idiomorph handles the swap
- Loading indicators during validation (HTMX's built-in `hx-indicator`)
- Form submission with proper redirect-after-POST or idiomorph swap on validation errors
- Optional: Alpine.js for purely client-side interactivity (show/hide, character counters) where a server round-trip would be overkill

## Prior art

- `django-crispy-forms` (1.3M downloads/month) -- DRY form rendering with template packs (Bootstrap, Tailwind). Very popular but heavy, complex layout DSL, no HTMX. crispy-tailwind is effectively deprecated
- `django-widget-tweaks` (574K downloads/month) -- template-level widget customization. Simple but only adds CSS classes, doesn't change rendering fundamentally
- `django-htmx` -- HTMX middleware/utilities, no form integration
- `django-formify` -- young, limited scope
- `django-formset` -- tries to do everything (form collections, Tailwind, HTMX-ish), overly complex
- `django-cotton` -- component-based templates, could complement but doesn't solve forms specifically
- Django 4.0+ form rendering refactor -- template-based renderers exist now, making custom rendering much cleaner than it used to be

## Notes

Phase 1 is the real foundation and where most of the value is. If the forms look good and are easy to customize out of the box, phase 2 is a natural extension. Most projects would benefit from phase 1 alone.

The Django 4.0+ form renderer system is underappreciated -- it makes building a custom form rendering library much cleaner than the old `as_table()` / `as_p()` / crispy approach. We should build on that rather than fighting it.

idiomorph is the key insight for phase 2 -- it eliminates the need for per-field partial rendering endpoints. The server always returns a full form render, and idiomorph diffs the DOM. This keeps the server side dead simple (one view, one template, standard Django form validation) while the client side gets seamless inline validation. This is the pattern that HTMX 4 was designed for.
