# SearchSelect POC — inline port plan

A plan for copying django-formwork's `SearchSelect` widget into another Django project as a POC, without adding a dependency on `django-formwork`.

## Constraints and context

- **No global CSS touchable.** All styles must live inside the template (inline `<style>` block) or on elements directly as utility classes.
- **Server-side search is mandatory.** This is the main feature — client-side-only filtering would defeat the point.
- **Target stack already has:** DaisyUI (v5-ish), Tailwind v4, HTMX, AlpineJS. We can rely on DaisyUI `select`, `dropdown-content`, `rounded-box`, `loading loading-spinner` etc. being available.
- **No AlpineJS state preservation needed.** The host page navigates away on change — we never have to survive an HTMX swap of the widget itself, so we can skip the morph/`_v` counter gymnastics if we want (though keeping `_v` is cheap).
- **POC, not long-term.** Single-select only. No multiselect, no combobox, no ChoiceLabel abstraction. Options are plain `{value, label, icon?, description?}` dicts.

## What we are copying

From [django_formwork/](django_formwork/) we need the behaviour of three pieces:

1. The widget template — [django_formwork/jinja2/formwork/widgets/search_select.html](django_formwork/jinja2/formwork/widgets/search_select.html) (Jinja2 form — identical DTL form at [django_formwork/templates/formwork/widgets/search_select.html](django_formwork/templates/formwork/widgets/search_select.html))
2. The Python widget — [django_formwork/widgets/search_select.py](django_formwork/widgets/search_select.py) (we do NOT need this class, we just need its rendering logic; see below)
3. The server view — [FormworkSearchView](django_formwork/views.py) in [django_formwork/views.py](django_formwork/views.py), specifically `get()`, `_get_template()`, the `SEARCH_SELECT_TEMPLATE` string, and the OOB-total-count response footer.

We can ignore:

- [django_formwork/fields.py](django_formwork/fields.py) — `FormworkChoiceLabel` et al. Not needed if we pass plain dicts.
- [django_formwork/registry.py](django_formwork/registry.py) — auto-registered `search_fields`. Not needed; we wire one URL explicitly.
- [django_formwork/static/formwork/formwork.css](django_formwork/static/formwork/formwork.css) — most of it. We only need to port the ~10 behaviour-critical rules (see CSS section).
- Icon pipeline from django-formwork-icons. If icons are plain emoji or already-rendered `<i class="…">` markup, nothing extra needed. If we want Lucide we can paste a tiny inline SVG mapping, not a whole package.

## Architecture — what lives where in the host project

Three files, one URL:

1. **A Django template snippet** — e.g. `templates/_search_select.html`, included via `{% include %}` where needed. Self-contained: markup + Alpine + inline `<style>`.
2. **A Django view** — `SearchView(View)` returning an HTML fragment. Drop into whatever app owns the feature.
3. **One urlconf entry** — `path("…/search/", SearchView.as_view(), name="…-search")`.

Because we have no `SearchSelect` widget class, the template receives its context directly from the parent view (or via `{% include … with … %}`), not from a form widget's `get_context()`.

## The template (snippet file)

Adapted from [search_select.html](django_formwork/jinja2/formwork/widgets/search_select.html), flattened to DTL and with a **scoped `<style>` block** at the top that replaces the global rules in `formwork.css`.

### Expected context variables

The `{% include %}` caller passes:

| Variable | Meaning |
|---|---|
| `name` | form field name (`name="…"` on the hidden input) |
| `widget_id` | DOM id prefix (`id_{name}` by convention) |
| `value` | currently-selected value (string) |
| `selected_label` | label of the currently-selected option (display text) |
| `selected_icon` | icon HTML of the selected option (may be `""`) |
| `search_url` | URL for the HTMX search endpoint |
| `search_threshold` | int, default `20` — below this, the search input is hidden |
| `placeholder` | e.g. `"Select…"` |

Options are NOT passed in — they come from the first HTMX response on `focus`.

### Markup structure (one copy, flattened from the Jinja template)

```django
{% load static %}
<details class="dropdown search-select" id="{{ widget_id }}_searchselect"
  x-data="{
    _v: 0,
    search: '',
    showSearch: false,
    value: '{{ value|escapejs }}',
    label: '{{ selected_label|escapejs }}',
    icon: '{{ selected_icon|escapejs }}',
    get displayText() { this._v; return this.label || ''; },
    _checkTotalCount() {
      const el = document.getElementById('{{ widget_id }}_total');
      if (el) this.showSearch = parseInt(el.value, 10) >= {{ search_threshold|default:20 }};
    },
    pick(val, lbl, ic) {
      this.value = val; this.label = lbl; this.icon = ic || '';
      this.search = ''; this._v++;
      this.$root.open = false;
      this.$nextTick(() => {
        const inp = this.$root.querySelector('input[type=hidden]');
        if (inp) inp.dispatchEvent(new Event('change', {bubbles: true}));
      });
    }
  }"
  @toggle="if ($el.open) {
    if (!$el.dataset.loaded) {
      $el.dataset.loaded = '1';
      requestAnimationFrame(() => $refs.search.dispatchEvent(new Event('focus')));
    }
    $nextTick(() => { if (showSearch && $refs.search) $refs.search.focus(); });
  }">
  <summary id="{{ widget_id }}_trigger" class="text-left"
           :class="!displayText && 'formwork-placeholder'">
    <span x-show="icon" x-html="icon" x-cloak class="shrink-0"></span>
    <span x-text="displayText || '{{ placeholder|default:"Select…"|escapejs }}'">{{ selected_label|default:placeholder|default:"Select…" }}</span>
  </summary>

  <input type="hidden" name="{{ name }}" value="{{ value }}" :value="value" id="{{ widget_id }}">
  <input type="hidden" id="{{ widget_id }}_total" value="0">

  <div class="dropdown-content bg-base-100 rounded-box shadow-lg border border-base-300 mt-1 text-sm">
    <div x-show="showSearch" x-cloak class="p-1.5 border-b border-base-300 flex items-center gap-1">
      <input x-ref="search" x-model="search" type="text"
             class="grow bg-transparent px-2 py-1 rounded"
             placeholder="Search…" aria-label="Search" @click.stop
             hx-get="{{ search_url }}"
             hx-trigger="input changed delay:300ms, focus"
             hx-target="#{{ widget_id }}_listbox"
             hx-swap="innerHTML"
             hx-params="none"
             hx-on::config-request="event.detail.parameters.q = this.value; event.detail.parameters.name = '{{ name }}'"
             hx-indicator="#{{ widget_id }}_spinner">
      <span id="{{ widget_id }}_spinner" class="htmx-indicator">
        <span class="loading loading-spinner loading-xs"></span>
      </span>
    </div>
    <ul x-ref="options" id="{{ widget_id }}_listbox" role="listbox"
        class="max-h-60 overflow-y-auto p-1"
        @click="const btn = $event.target.closest('[data-value]'); if (btn) pick(btn.dataset.value, btn.dataset.label, btn.dataset.icon || '')"
        hx-on::after-swap="Alpine.$data(this.closest('[x-data]'))._checkTotalCount()">
    </ul>
  </div>
</details>
```

A few simplifications vs. the original:

- Dropped the client-side `noResults` / `filter-on-label` getter — we never render options client-side.
- Dropped the `{% if not widget.search_url %}` branches — server-side is the only path.
- Dropped `clear()` — unless the design explicitly needs a clear button. Easy to add back.

### Inline `<style>` block

Put this at the **top** of the snippet, inside `<style>` tags. These rules are **behaviour-critical** and cannot be left to Tailwind utility classes alone:

```html
<style>
  /* Hide Alpine-guarded elements before Alpine initialises. */
  [x-cloak] { display: none !important; }

  /* Dropdown chrome: make the <details> fill its container and
     position the menu absolutely below the trigger. */
  details.dropdown.search-select { position: relative; width: 100%; }
  details.dropdown.search-select > .dropdown-content {
    position: absolute; z-index: 1; width: 100%;
  }

  /* Apply DaisyUI .select look to the <summary> trigger.
     (We cannot @apply from inline CSS; replicate the essentials.) */
  details.dropdown.search-select > summary {
    /* DaisyUI .select variables cascade here already; we just need the box. */
    display: flex; align-items: center; gap: 0.5rem;
    border: var(--border, 1px) solid color-mix(in oklab, currentColor 20%, transparent);
    border-radius: var(--radius-field, 0.5rem);
    padding-inline: 0.75rem; padding-block: 0.375rem;
    min-height: 2.5rem;
    background: var(--color-base-100);
    cursor: pointer;
  }
  details.dropdown.search-select[open] > summary {
    outline: 2px solid var(--color-base-content);
    outline-offset: 2px;
  }

  /* Placeholder dimming when nothing is selected. */
  .formwork-placeholder {
    color: color-mix(in oklab, currentColor 50%, transparent);
  }

  /* Checkmark visibility on the selected option (rendered by the
     server fragment — opacity-0 by default, opacity-100 when
     x:class matches). Needs to beat Tailwind's opacity-0. */
  .formwork-check { transition: opacity 0.1s; }

  /* Pure-CSS outside-click close: invisible full-page overlay
     captures the next click and toggles <details> shut. */
  details.dropdown[open] > summary::before {
    content: ""; position: fixed; inset: 0; cursor: default;
  }

  /* Kill the double focus ring on the search input (parent summary
     already has an outline when open). */
  .dropdown-content input:focus {
    outline: none; border-color: transparent; box-shadow: none;
  }
</style>
```

If the host's DaisyUI config matches django-formwork's, most of the `<summary>` block can be deleted because DaisyUI's `.select` utility will already style it — but inlining it makes the snippet self-contained and survives DaisyUI version drift.

## The view

Copy [FormworkSearchView](django_formwork/views.py) into the host project, stripped to what we need. The only moving parts are:

1. Take `q` from `GET`.
2. Look up matching rows (however the host wants — ORM, dict list, API call).
3. Render each as an `<li><button data-value="…" data-label="…" …>` fragment — **one compiled Django Template instance, cached at class level.**
4. Append an OOB-swap hidden input carrying the total result count, so the widget's search bar appears once the set exceeds `search_threshold`.

### Minimal port

```python
# search_view.py (or wherever)
from django.http import HttpRequest, HttpResponse
from django.template import Context
from django.template.engine import Engine
from django.views import View

SEARCH_SELECT_TEMPLATE = """{% for item in results %}
<li role="option"><button type="button"
    class="flex w-full items-center gap-2 px-3 py-1.5 rounded-btn cursor-pointer hover:bg-base-200 text-left"
    data-value="{{ item.value }}" data-label="{{ item.label }}"{% if item.icon %} data-icon="{{ item.icon }}"{% endif %}>
  <span class="formwork-check shrink-0 opacity-0"
        :class="value === '{{ item.value }}' && 'opacity-100'"
        aria-hidden="true">&#x2713;</span>
  {% if item.icon %}<span class="shrink-0">{{ item.icon }}</span>{% endif %}
  <span class="flex flex-col">
    <span class="select-none">{{ item.label }}</span>
    {% if item.description %}<span class="text-xs text-base-content/50">{{ item.description }}</span>{% endif %}
  </span>
</button></li>{% endfor %}
{% if not results %}<li class="px-3 py-2 text-base-content/50">No results</li>{% endif %}"""


class SearchView(View):
    MAX_QUERY_LENGTH = 200
    _engine: Engine | None = None
    _template = None

    @classmethod
    def _get_template(cls):
        if cls._template is None:
            cls._engine = Engine()
            cls._template = cls._engine.from_string(SEARCH_SELECT_TEMPLATE)
        return cls._template

    def get_results(self, query: str, request: HttpRequest) -> list[dict]:
        raise NotImplementedError

    def get_total_count(self, request: HttpRequest) -> int:
        return len(self.get_results("", request))

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "").strip()[: self.MAX_QUERY_LENGTH]
        field_name = request.GET.get("name", "")

        total = self.get_total_count(request)
        results = self.get_results(query, request)

        html = self._get_template().render(Context({"results": results})).strip()
        parts = [html]
        if field_name:
            widget_id = f"id_{field_name}"
            parts.append(
                f'<input id="{widget_id}_total" type="hidden" '
                f'value="{total}" hx-swap-oob="true">'
            )
        return HttpResponse("".join(parts))
```

### Concrete subclass (example — replace with the real data source)

```python
class CitySearchView(SearchView):
    def get_results(self, query, request):
        qs = City.objects.all()
        if query:
            qs = qs.filter(name__icontains=query)
        return [{"value": str(c.pk), "label": c.name} for c in qs[:50]]

    def get_total_count(self, request):
        return City.objects.count()
```

Wire it up:

```python
# urls.py
path("cities/search/", CitySearchView.as_view(), name="city-search"),
```

## Host page — putting it together

```django
{% include "_search_select.html" with
    name="city"
    widget_id="id_city"
    value=form.city.value|default:""
    selected_label=selected_city_name|default:""
    selected_icon=""
    search_url="/cities/search/"
    search_threshold=20
    placeholder="Select a city…" %}
```

The hidden `<input name="city">` participates in normal form submission. On `change` the Alpine code dispatches a `change` event — if the host page auto-submits on change, bind at the form level or on `#id_city`.

## Implementation checklist

In rough order:

1. [ ] Confirm HTMX + Alpine are already loaded globally on the target page. If not, add the two `<script>` tags.
2. [ ] Create `templates/_search_select.html` with the markup + scoped `<style>` block above.
3. [ ] Create `search_view.py` with the `SearchView` base class and `SEARCH_SELECT_TEMPLATE`.
4. [ ] Write the concrete subclass for the real data source (queryset filter, API call, whatever).
5. [ ] Add the URL route.
6. [ ] Include the template in the host page, passing the context variables.
7. [ ] Manually test: open dropdown → search field focuses and HTMX fires, results render, clicking an option fills the trigger label and closes the dropdown, submit sends the right hidden value.
8. [ ] Verify the `showSearch` threshold behaviour: widget with <20 results hides the search bar, widget with ≥20 shows it.
9. [ ] Verify `[x-cloak]` isn't flashing — the inline style must load before Alpine initialises (it will, since it's inline in the same document).

## Known gotchas

- **`hx-on::config-request` syntax.** HTMX 2.x uses `hx-on::config-request`; HTMX 1.x uses `hx-on:htmx:config-request`. Check the host's HTMX version and adjust.
- **Alpine version.** `Alpine.$data(...)` works on Alpine v3. If the host still runs v2, the OOB total-count handler needs rewriting.
- **Tailwind v4 utilities.** `rounded-btn`, `rounded-box`, `base-100`, `base-200`, `base-content`, `base-300` are DaisyUI semantic tokens — confirm they exist in the host's Tailwind build.
- **CSRF.** `GET` search requests don't need CSRF, but if the host has aggressive middleware, verify.
- **Escaping.** `escapejs` is used in the Alpine attributes. If a label contains HTML, the user sees escaped text — that's intentional. Icon HTML is the one place we allow raw markup (via `x-html="icon"`), so any icon source must be trusted or pre-escaped.
- **Missing clear button.** If the design calls for a "×" to reset the selection, add a `clear()` method to the Alpine scope and a button in `<summary>`.
- **No keyboard navigation in this POC.** The original widget doesn't ship full arrow-key navigation either — ↑/↓/Enter inside the `<ul>` will not select. If required, add `@keydown.down` / `@keydown.up` handlers to the search input that move focus across `li > button` children.
