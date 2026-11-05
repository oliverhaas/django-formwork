# Browser Support

The CSS you build from `formwork.css` needs the browsers that Tailwind CSS 4 supports, plus CSS `subgrid`. The newer features that formwork uses beyond these, listed in [Progressive enhancements](#progressive-enhancements), have a fallback.

## Effective minimum

| Chrome | Edge | Firefox | Safari |
|---|---|---|---|
| 117 | 117 | 128 | 16.5 |

Tailwind 4 [lists](https://tailwindcss.com/docs/compatibility) Chrome 111, Safari 16.4 and Firefox 128 as its minimum. `subgrid` raises Chrome and Edge to 117, and the CSS nesting in the DaisyUI 5 output raises Safari to 16.5. An older browser renders the forms with visual defects, and the forms still submit.

## Feature matrix

| Feature | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| `:has()` selector | 105 | 121 | 15.4 | 105 |
| `color-mix()` | 111 | 113 | 16.2 | 111 |
| CSS Grid `subgrid` | 117 | 71 | 16 | 117 |
| CSS nesting | 112 | 117 | 16.5 | 112 |
| `@layer` | 99 | 97 | 15.4 | 99 |

## Where each feature is used

`formwork.css` uses `:has()` to style a fieldset by its content: the two-column layout of a single checkbox, the side-by-side layout of a multi-widget field, the size of the error tooltip, the `ClearableFileInput` layout and the error state of `ValidatedTextarea`.

`color-mix(in oklab, ...)` mixes the placeholder color of the dropdown triggers and of `<select>`, the icon color of the drop zones, the error highlight of `ValidatedTextarea`, the soft select and textarea variants and the soft alert. Some of these declarations have an `rgba()` or hex fallback on the line before. The soft variants, the soft alert, the input-mask placeholder dots and the `SelectMultiple` trigger in a disabled fieldset have none, so a browser without `color-mix()` drops their colors.

`subgrid` keeps a checkbox, or the inputs of a multi-widget field, aligned with the column grid of the fieldset while an error tooltip wraps them.

`formwork.css` itself has no nested rules. The DaisyUI 5 rules in the built CSS do, and a browser without nesting drops them.

Most `formwork.css` rules sit in `@layer components`, so the Tailwind utilities in your markup (in `@layer utilities`) and your unlayered CSS override them. A few rules stay unlayered, because they must beat DaisyUI rules in `@layer utilities`. Tailwind 4 puts its own output in layers too, so a browser without `@layer` ignores most of the stylesheet.

## Progressive enhancements

The dropdown panels of `Select`, `SelectMultiple` and `ComboBox` open in the top layer through the Popover API, and CSS anchor positioning places them next to the trigger. Without anchor positioning, the JavaScript sets the position of the panel. Without the Popover API, the panel stays absolutely positioned below its trigger.

`field-sizing: content` lets the text input of `DatePicker` and a native `<select>` fit an auto-width table column. A browser without it keeps the default width.

!!! note "Older browsers"
    Formwork has no fallback for `:has()`, `subgrid`, nesting or `@layer`. To support an older browser, add your own CSS overrides.
