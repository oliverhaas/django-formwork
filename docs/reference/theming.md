# Themes and Layout

Formwork's templates and styles use DaisyUI's semantic colors, such as
`primary`, `base-100` and `error`, and no fixed colors. A DaisyUI theme
therefore recolors every widget, light and dark themes alike.

## Pick a theme

`formwork.css` loads every DaisyUI theme. A page without `data-theme` shows the
`light` theme, or `dark` when the browser prefers a dark color scheme. Set
`data-theme` on `<html>` to use another theme:

```html
<html lang="en" data-theme="corporate">
```

The [DaisyUI theme list](https://daisyui.com/docs/themes/) shows each theme.

## Let the user switch

An input with DaisyUI's `theme-controller` class switches the page to the
theme in its `value` while it is checked. A row of buttons needs no script:

```html
<div class="join">
  <input type="radio" name="theme" value="light" class="join-item btn btn-sm theme-controller" aria-label="Light">
  <input type="radio" name="theme" value="dark" class="join-item btn btn-sm theme-controller" aria-label="Dark">
</div>
```

The choice lasts until the next page load. To keep it, store it in a cookie and
render `data-theme` and the checked button from the cookie. Until the user picks
a theme, the page follows the browser's color scheme:

```html
<html lang="en"{% if request.COOKIES.theme %} data-theme="{{ request.COOKIES.theme }}"{% endif %}>
...
<div class="join" x-data @change="document.cookie = `theme=${$event.target.value}; path=/; max-age=31536000; samesite=lax`">
  <input type="radio" name="theme" value="light" class="join-item btn btn-sm theme-controller" aria-label="Light"{% if request.COOKIES.theme == "light" %} checked{% endif %}>
  <input type="radio" name="theme" value="dark" class="join-item btn btn-sm theme-controller" aria-label="Dark"{% if request.COOKIES.theme == "dark" %} checked{% endif %}>
</div>
```

The [admin](admin.md#the-site) has a theme menu of its own, with the themes in
the site's `themes`.

## Your own theme

DaisyUI's `daisyui/theme` plugin adds a theme or changes one. Write it after the
import of `formwork.css`. A theme with the name of a built-in theme changes only
the values it lists:

```css
@import "path/to/site-packages/django_formwork/static/formwork/formwork.css";

@plugin "daisyui/theme" {
  name: "light";
  default: true;
  --color-primary: oklch(52% 0.2 300);
  --color-primary-content: oklch(98% 0.01 300);
}
```

A theme with a new name works in `data-theme` and in a theme controller. Each
value it leaves out comes from the page's default theme, so list every color.
DaisyUI's
[theme generator](https://daisyui.com/theme-generator/) writes the full block.

`--formwork-focus-color` colors the border of a focused or open field and its
floating label. It is `var(--color-primary)` unless a theme or a page sets it:

```css
:root {
  --formwork-focus-color: var(--color-secondary);
}
```

The colors of a changed field have
[variables of their own](forms.md#changed-field-highlight).

## Lay out a form

`{{ form }}` writes no element around the fields, and a field group has no outer
margin. The element around the fields lays them out with Tailwind's grid
classes.

One column:

```html
<div class="grid gap-2">{{ form }}</div>
```

Two columns, with a wide field across both. `items-start` keeps each field
group at its own height, so a field does not stretch to the height of its
neighbor's help text:

```html
<div class="grid items-start gap-x-6 gap-y-2 sm:grid-cols-2">
  {{ form.full_name.as_field_group }}
  {{ form.email.as_field_group }}
  <div class="sm:col-span-2">{{ form.bio.as_field_group }}</div>
  {{ form.team.as_field_group }}
  {{ form.start.as_field_group }}
</div>
```

`{{ form }}` in the same grid puts its fields in the columns in order. The
alert with the form's own errors spans every column.

A row of filters, with the controls and the button lined up at the bottom when
a label wraps. `mb-1` on the button matches the padding below a field group:

```html
<form method="get" class="grid items-end gap-x-3 gap-y-2 sm:grid-cols-4">
  {{ filter_form }}
  <button class="btn mb-1">Filter</button>
</form>
```

For a table of fields, see `as_table()` and `as_control()` under
[Layouts](forms.md#layouts).
