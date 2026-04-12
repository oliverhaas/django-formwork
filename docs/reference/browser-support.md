# Browser Support

Formwork's CSS uses several modern CSS features. The table below lists the minimum browser versions required for full support.

## Feature matrix

| Feature | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| `:has()` selector | 105 | 121 | 15.4 | 105 |
| `color-mix()` | 111 | 113 | 16.2 | 111 |
| CSS Grid `subgrid` | 117 | 71 | 16 | 117 |
| CSS Nesting | 112 | 117 | 16.5 | 112 |
| `color-mix()` with `oklab` | 111 | 113 | 16.2 | 111 |
| `@layer` | 99 | 97 | 15.4 | 99 |

## Where each feature is used

**`:has()`** — used throughout `formwork.css` to style fieldsets contextually: single-checkbox two-column layout, multi-widget side-by-side layout, error tooltip sizing, ClearableFileInput flow layout, and validated textarea error state.

**`color-mix(in oklab, ...)`** — used for placeholder color on `<select>` and summary triggers, upload widget icon color, and the error highlight background on `ValidatedTextarea`. Browsers that don't support `color-mix()` fall back to a hardcoded `rgba()` value immediately before each `color-mix()` declaration.

**CSS Grid `subgrid`** — used so checkbox and multi-widget inputs inside an error tooltip wrapper stay aligned with the parent fieldset's column grid.

**CSS Nesting** — used inside `@layer components` rule blocks (e.g. `.fieldset + .fieldset`). Browsers that don't support nesting will silently drop those rules.

**`@layer`** — all `formwork.css` rules are wrapped in `@layer components`. This ensures Tailwind utilities in HTML (which are in `@layer utilities`) always take precedence, and users can override formwork styles with unlayered CSS. Browsers that don't support `@layer` receive no formwork styles at all.

## Effective minimum

All five features are available in Chrome 117+, Firefox 121+, Safari 16.5+, and Edge 117+. Browsers released before these versions will have visual regressions (misaligned layouts, missing placeholder colors, broken subgrid alignment), but the forms remain functional.

!!! note "Fallbacks"
    `color-mix()` rules always include a `rgba()` fallback on the preceding line, so colors degrade gracefully on older browsers. All other features have no fallback — if you need to support older browsers, you will need to add custom CSS overrides.
