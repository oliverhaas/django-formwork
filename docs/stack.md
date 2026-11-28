# htmx, Alpine.js and DaisyUI

Formwork renders each form on the server and uses three libraries in the browser. htmx sends requests and puts the answers into the page. Alpine.js keeps the state that the server never sees. DaisyUI gives the markup its look. This page says why formwork uses these three, how they meet in one widget, and which one a change of your own belongs to.

## Why this stack

**The server keeps the form.** A Django form knows its fields, initial values, validation and errors, and it renders itself as HTML. Formwork keeps all of that in Python. With a JavaScript framework in the browser, the same form would need an API and a second copy of its rules in JavaScript. In formwork, the answer to a post is the form again, rendered by the same templates as the first page.

**htmx puts the server's answer into the page.** A form posts with `hx-post`, the view renders the form again, and htmx morphs it into the page. A morph changes only the nodes that differ, so the focus, the caret and the typed text stay where they were. Server search and live validation are htmx requests too. Search goes to a view that formwork serves, so a page needs no endpoint of its own for it.

**Alpine.js holds what the server never sees:** whether a dropdown is open, which option the arrow keys have reached, the month a calendar shows, whether a password is visible. A widget with behaviour registers one Alpine component, and its template names the component in `x-data`. `Select`, `SelectMultiple` and the date and time pickers start their component on first use, so a formset with a hundred dropdowns loads without starting a hundred components. Alpine needs no build step, and its attributes sit in the server's markup, so a morph and a component work on the same DOM.

**DaisyUI gives the markup its look.** It is a Tailwind plugin, and the templates write its component classes, such as `input`, `select`, `btn`, `fieldset` and `dropdown`, next to Tailwind utilities. A theme is a set of CSS variables, so a theme switch or a dark theme changes every widget without a change to any widget. Your Tailwind build compiles formwork's CSS together with your own, and a utility class on a widget overrides most of formwork's rules ([Architecture](architecture.md#design-constraints)).

**The costs.** The project needs a Tailwind build ([installation step 4](getting-started/installation.md#4-build-the-css)). Each change that the server must see is a request and a response. A morph keeps Alpine's state only with htmx's alpine-compat extension, so the scripts must load in a fixed order; `{% formwork_head %}` does that ([installation step 5](getting-started/installation.md#5-htmx-and-alpinejs)).

## One widget, all three

A `Select` with server search, in a form that posts with htmx:

1. The server renders the widget: a `<details class="dropdown">` with the selected label in its `<summary>`, styled by DaisyUI classes. The page shows the widget as it is before any script runs.
2. The user focuses or opens it. That first event starts the `formworkSelect` Alpine component, which handles the keys from then on.
3. The user types. After a pause of 300 ms, htmx sends the text to the search view. The view renders the matching options with the widget's option template, and htmx puts them into the list. The arrow keys move through the new options as through the old ones.
4. The user picks an option and saves. htmx posts the form, the view renders it again with its errors, and htmx morphs the whole form into the page. The alpine-compat extension keeps what Alpine wrote into the DOM. Formwork's `formwork-morph` extension keeps what the user changed after the post left: the value of the focused input, later edits, open dropdowns and a pick that is not yet confirmed.

The [cookbook](cookbook.md) builds such a form step by step, and [Server-side search](reference/views.md#server-side-search) covers the search view.

## Which one a change belongs to

| To | Use |
|---|---|
| Change a look: color, size, spacing, a state | DaisyUI and Tailwind classes in the template. See [Themes and Layout](reference/theming.md). |
| Show what the server knows: search results, an error, a saved value | An htmx request, with a morph of the part of the page that the answer changes |
| Keep state that only the browser needs: open, revealed, the current step | An Alpine component, registered with `Alpine.data` in a static JS file |
| Open and close something that has no other state | Native HTML: `<details>` or `<dialog>` |

Some rules follow from this split:

- Morph a large part of the page, such as the whole form or the page content, not single fields. One action often changes several places, and one morph keeps them all in step without extra templates. Use an out-of-band swap only for something outside that part, such as a toast.
- Put no `<script>` in a template or an htmx fragment. A fragment comes back with each swap, and its script with it. Register an Alpine component in a static module, and load the module before `{% formwork_head %}` so that its `alpine:init` listener exists when Alpine starts.
- A morph leaves the `open` state of a `<details>` or a `<dialog>` as it is, because formwork adds `open` to `htmx.config.morphIgnore`. Open and close them in the browser.
- A script that calls into a widget that starts on first use sends it `formwork:start` first. See [Widgets](reference/widgets.md#requirements).
