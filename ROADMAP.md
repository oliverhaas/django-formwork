# django-formwork: Road to 1.0

Working backlog of what's left to change, fix, or improve before this package earns a
solid 1.0. Produced 2026-07-05 from a multi-dimension audit (correctness, API surface,
widgets, frontend JS, tests, docs, a11y/i18n, types, packaging, perf/security, strategic
features). Every claimed bug was re-checked against the source; one claim was refuted and
dropped. File:line refs are where the evidence lives.

## Where it stands

Close to feature-complete and structurally healthy (~91% line coverage on the non-browser
suite, 989 passing), but **not 1.0-ready**. Three blockers dominate.

1. **Correctness / security.** Two confirmed Alpine expression-injection XSS holes exist
   because escapejs was applied inconsistently. The auto-search registry has a last-writer-wins
   key collision that can drop an auth decorator and leak an unfiltered queryset across tenants.
   (The `CountryInput` widget, which rejected every value it accepted, has since been removed;
   see Done below.)
2. **CSS / icon distribution is broken for anyone following the docs.** `installation.md`
   omits both `manage.py formwork install` (so the Tailwind build fails on the git-ignored,
   generated `icons.css`) and the `@source` directive (so Tailwind v4 tree-shakes every
   widget utility class and widgets render unstyled). The correct recipe already exists in
   `examples/simple/app.css`; the docs just don't match it. (Fixed 2026-07-10 together with
   the icons.css relocation; see Done below.)
3. **API / naming lock-in.** `widget_type` is spelled three ways, `ComboBox` four; the
   public import surface is fragmented; the registry is public-but-should-be-internal. These
   freeze under semver at 1.0 and must be settled first. (Settled 2026-07-10: snake_case
   tokens, uniform lazy top-level re-exports, registry made internal; see Done below.)

Underneath sits one architectural root cause: **11 of 17 widgets inline their JS as
duplicated `x-data` blocks across both template engines.** That is *why* the escaping bug
exists and what makes the a11y/i18n gaps expensive to close.

The good news: most release-blocking defects are small, surgical fixes. The expensive work
(i18n, inline-JS extraction, layout/formset-UI features) is largely deferrable if scoped
honestly.

---

## Must fix before 1.0

### Security & correctness (mostly small)

- [x] **Removed `CountryInput` + `country_choices()`** (2026-07-05, see Done). It was a thin
  `SearchSelect` wrapper that never validated (choices on the widget, not the field). Decided
  country lists are application data, not framework data.
- [x] **escapejs'd every value interpolated into an Alpine `x-data` / JS-string context**
  (2026-07-10, see Done). Fixed `date_picker.html`, `otp_input.html`, `input_number.html`
  (both engines) and the `SEARCH_SELECT_TEMPLATE`/`COMBOBOX_TEMPLATE` fragments; audited the
  remaining widgets, with regression tests using hostile values.
- [x] **Prevented registry key collisions that override auth/queryset across registrations**
  (2026-07-10, see Done). `make_key` now folds the form module/qualname + field name into the
  key, as `make_choices_key` already did.

### Packaging: make a fresh install actually work

- [x] **Rewrote `installation.md` so the build works and widgets render** (2026-07-10, see
  Done). Import only `formwork.css` plus the generated `iconx/icons.css`, the
  `@source "path/to/site-packages/django_formwork/";` directive, `django_iconx` in
  `INSTALLED_APPS`, and `python manage.py formwork install` as a required documented step
  (including the new `--output` option).
- [x] ~~Cap the unbounded pre-1.0 `django-iconx` dependency.~~ Won't do (2026-07-10): the
  maintainer owns django-iconx and wants the constraint uncapped.

### API surface: lock names before semver freezes them

- [x] **Locked `widget_type` and `ComboBox` naming to snake_case** (2026-07-10, see Done).
  Tokens are now `search_select` / `multi_select` / `combo_box`; the view template
  attributes are `SEARCH_SELECT_TEMPLATE` / `MULTI_SELECT_TEMPLATE` / `COMBO_BOX_TEMPLATE`;
  `widgets/combobox.py` became `widgets/combo_box.py`. Class names stay PascalCase.
- [x] **Reconciled the `FormworkModel` import path + uniform lazy top-level re-exports**
  (2026-07-10, see Done). A lazy module-level `__getattr__` in `django_formwork/__init__.py`
  resolves every documented public name (forms, formsets, view base classes,
  `FormworkModel`, async mixins, renderers) from the top level; submodule imports keep
  working; docs and examples show top-level imports as canonical.

---

## Should have for 1.0

- [ ] **Make widget `max_size`/`accept` enforceable server-side (or loudly document them as
  cosmetic).** Drop zones enforce size/type/count only in client JS; any direct POST uploads
  arbitrary size/type, a DoS + content-type bypass. It matches plain-Django semantics, but the
  API *implies* enforcement. Ship a validator auto-attached from the widget config (or
  `FormworkFileField`/`ImageField`), or at minimum document the footgun.
  (`django_formwork/widgets/file_drop_zone.py:42`, medium)
- [ ] **Extract inline `x-data` widgets into shipped `Alpine.data` JS modules.** 11 of 17
  widgets inline their JS, duplicated byte-for-byte across DTL and Jinja2. Root cause of the
  escapejs inconsistency; makes logic un-lintable/un-testable/un-minifiable and is where the
  two engines silently drift. At minimum do the security-sensitive ones (`date_picker`,
  `otp_input`) before 1.0. (`templates/formwork/widgets/input_mask.html:1`, large)
- [ ] **Cover the async ModelForm save path.** `avalidate_unique`'s ValidationError branch
  and the entire `_asave_m2m` loop have zero tests; async duplicate-unique validation and
  `asave()` on an M2M form are unexercised. Also remove the dead, shadowed
  `AsyncModelFormMixin._apost_clean` so async coverage can actually close.
  (`django_formwork/async_forms.py:156`, medium)
- [ ] **Add e2e/screenshot coverage for the six untested widgets** (`country_input`,
  `date_picker`, `input_mask`, `input_number`, `otp_input`, `phone_input`). The
  client-behavior ones have their entire value in JS no browser test drives. Prioritize
  `otp_input` and `input_mask`. (`tests/widgets/`, large)
- [ ] **Fix custom-dropdown accessibility.** `MultiSelect` checkboxes are `display:none`
  (removed from the a11y tree); `keyboardNav` only toggles a CSS class and never sets
  `aria-activedescendant`/`aria-selected`; the three dropdowns drop the `aria-describedby`
  Django 6 auto-populates, so an AT user hears "invalid" but never the error/help text.
  (`static/formwork/widgets/_helpers.js:15`, medium)
- [ ] **Document formsets, Jinja2 setup, and a consolidated settings page.** The marketed
  batched-uniqueness formsets have zero docs and no nav entry; Jinja2 users have no documented
  way to configure the renderer or emit CSS/JS (the tags are DTL-only `simple_tag`s that
  don't work in Jinja2); no single settings reference for `FORM_RENDERER`/`FORMWORK_FORCE_ASYNC`.
  (`mkdocs.yml:44`, medium)
- [ ] **Settle the config surface.** `search_threshold` is class-only, `max_results` isn't
  settable from the widget, `FORMWORK_FORCE_ASYNC` is an undocumented bare `getattr`.
  Introduce one documented `FORMWORK` settings dict + constructor kwargs.
  (`widgets/search_select.py:54`, medium) The registry half of this item is done: `registry.py`
  became the internal `_registry.py` (2026-07-10, see Done).
- [x] **Moved generated `icons.css` out of site-packages** (2026-07-10, see Done).
  `formwork install` now writes to the project static dir (first `STATICFILES_DIRS` entry,
  else `BASE_DIR/static`) with an `--output` override; `formwork.css` no longer imports it
  and the recipe imports it from the project instead.
- [ ] **Scope the global htmx morph config to formwork subtrees.** `formwork-core.js` pushes
  `'open'` into `htmx.config.morphIgnore` and appends x-for/x-if selectors to
  `morphSkipChildren` *globally*, silently changing morph for every non-formwork `<details>`
  and Alpine list on the host page. Gate on a formwork marker in the per-node hook.
  (`static/formwork/formwork-core.js:112`, medium)
- [ ] **Collapse the type-checking debt.** Two checkers with divergent suppression force every
  ignore to be written twice; `async_forms.py` types `self: Any` on all 13 methods, disabling
  checking on the entire async validation/ORM path. Give the cooperative mixins a
  TYPE_CHECKING protocol base, drop `self: Any`, and either flip
  `respect-type-ignore-comments=true` or drop one checker for a single source of truth.
  (`django_formwork/async_forms.py:47`, medium)
- [ ] **Add conditional (show/hide) fields driven by other field values.** A near-universal
  real-form need with zero support today (users must abandon `{{ form }}`). Alpine is already
  a hard dependency and bootstrapped, so this is the highest value-per-effort strategic
  feature, plausibly *the* 1.0 differentiator. Needs a server-side guard so hidden fields skip
  validation. (`templates/django/forms/formwork_field.html:1`, medium)
- [ ] **Reduce e2e flakiness + add a coverage floor.** 210 `wait_for_timeout` sleeps violate
  the project's own Playwright guidance and will intermittently fail as the suite grows; no
  `fail_under` so coverage can silently regress. Convert to `expect()` state-based waits; add
  `fail_under=90`. (`tests/widgets/test_search_select.py:1`, medium)

---

## Post-1.0 (additive; define the ceiling, don't block the freeze)

- [ ] **Inline-formset editing UI (add/remove/reorder rows).** The most-requested form-UI
  capability; the marketed batched-uniqueness formsets are 100% backend with zero rendering
  side. The htmx+Alpine machinery is already present. Ship a 4th widget JS module wired to
  `FormworkBaseInlineFormSet`. (large)
- [ ] **Declarative form layout system** (fieldset grouping, multi-column, column span).
  `{{ form }}` can only produce one-column stacks; every non-trivial CRUD screen loses to
  crispy/manual templates. Design the API deliberately rather than rushing into the freeze.
  (large)
- [ ] **`TimePicker` / `DateTimePicker` / `DateRangePicker`.** `DatePicker` is the only
  temporal widget; `TimeField`/`DateTimeField` are among the most common Django fields.
  Reuses the existing calendar. (medium)
- [ ] **Tags/token input, plus color, slug, and JSON widgets.** The most frequently
  hand-rolled widgets in Django projects. (medium)
- [ ] **Full internationalization** (gettext + locale catalog + JS string externalization).
  No `{% trans %}` or `locale/` dir anywhere; dozens of hardcoded English strings block
  non-English deployment. Cleanest *after* the inline-x-data extraction lands. (large)
- [ ] **`FormworkWizardView` + an htmx form-submit mixin/helper.** The docs advertise a wizard
  that only exists hand-coded in `examples/full`; every view repeats the same `HX-Request`
  partial-vs-page + `HX-Redirect` branching, exactly the boilerplate the framework claims to
  eliminate. (medium/large)
- [ ] **Per-field template/escape hatch** (widget-tweaks/crispy equivalent) + remaining a11y
  polish (date-picker grid semantics, phone-prefix keyboard access). Lets non-DaisyUI stacks
  adopt without abandoning `{{ form }}`. (medium)
- [ ] **Repo hygiene.** Publish an npm package (or drop the bundler-import claim that can't
  resolve today), drop Git LFS for 340 KB of screenshots, fix the dead `publish.yml` version
  verification on the automated release path. (small)

---

## Quick wins (small effort, high value; knock these out first)

- [x] ~~escapejs the two confirmed XSS sinks~~ Done (2026-07-10), plus `input_number.html` and a
  full audit of both engines
- [x] ~~Ship `CountryField`~~ Removed `CountryInput`/`country_choices()` entirely (2026-07-05)
- [x] ~~Swap `installation.md` CSS block for the `examples/simple/app.css` recipe + add the
  `formwork install` / `django_iconx` step~~ Done (2026-07-10), full rewrite; see Done
- [x] ~~Cap `django-iconx` to `>=0.2.0,<0.3`~~ Won't do (2026-07-10): maintainer owns iconx,
  wants it uncapped
- [ ] Add `fail_under=90` to `[tool.coverage.report]`; delete/confirm-gitignore the stale
  `coverage.xml` (reports a misleading 36% vs the real ~91%)
- [x] ~~Force `FormworkAutoSearchView.widget_type` from the registration, ignoring client
  `?type=`~~ Done (2026-07-10); widget templates no longer send `type`, `VALID_WIDGET_TYPES`
  removed
- [ ] Drop clamped-empty spans in `_build_highlighted` so no stray empty `<mark>` is emitted
  (`views.py:322`)
- [ ] Fix the `FormworkModel` error message + docstring cross-refs (or add the lazy `__getattr__`)
- [ ] Render `aria-describedby` on the combobox input + SearchSelect/MultiSelect summaries
- [ ] Add `role="alert"` to the drop-zone/image-upload error `<p>` so rejected-file feedback
  is announced
- [ ] Type `search_decorator` as `Callable | None` instead of `Callable | object`
- [ ] Render empty (not `'0'`) for unbound `InputNumber`; round `inc()`/`dec()` to step precision
- [ ] Remove the dead `AsyncModelFormMixin._apost_clean` copy so async coverage can close
- [ ] Add a Jinja2 setup section (FORM_RENDERER wiring + how to emit CSS/JS)
- [ ] Document the no-`self` convention for `search_choices_<field>` handlers

---

## Open questions (your calls; decide before the relevant work)

1. ~~**Public API surface:** commit to uniform lazy top-level re-exports (forms, formsets, view
   base classes, `FormworkModel`, async mixins all from `django_formwork`), or a documented
   "import from submodules" convention? And is the registry semver-covered at all? Must be
   decided before the freeze.~~ Resolved (2026-07-10): uniform lazy top-level re-exports via
   module `__getattr__`; the registry is internal (`_registry.py`), not semver-covered. See Done.
2. **Is i18n a 1.0 requirement or a fast-follow?** Full gettext + locale + JS externalization
   is large and cheapest *after* the inline-x-data extraction. Blocking 1.0 on it could delay
   significantly; shipping English-only forecloses non-English adopters until a minor release.
3. **Which strategic feature is the 1.0 differentiator?** You can realistically land one large
   feature for 1.0: conditional fields (medium, highest value-per-effort), the layout system
   (large, decides non-trivial CRUD adoption), or the inline-formset UI (large, most-requested).
   Pick deliberately.
4. ~~**Where should generated `icons.css` live**, inside site-packages (current, breaks
   read-only installs) or a project-controlled static dir with an overridable import?~~
   Resolved (2026-07-10): project static dir via `--output` (default first `STATICFILES_DIRS`
   entry, else `BASE_DIR/static`); the project's Tailwind input imports it next to
   `formwork.css`. See Done.
5. **Type-checking direction:** keep both mypy and ty (pay the double-suppression tax, flip
   `respect-type-ignore-comments=true`), or drop one checker for the library source?
6. **Should `max_size`/`accept` be enforced server-side** (auto-attach validators, changing
   behavior) or remain presentational-only with loud docs? An API-semantics call that freezes
   user expectations at 1.0.
7. ~~**`FormworkValidateView`** is CSRF-exempt with no default auth hook and no length cap on
   POSTed text (unlike search).~~ Resolved (2026-07-10): added the `validate_decorator` hook
   and a `MAX_TEXT_LENGTH` cap (50k chars) mirroring the search side; documented in
   `docs/reference/views.md`.

---

## Done

- **API naming batch: snake_case widget-type tokens, uniform lazy top-level imports,
  internal registry** (2026-07-10). Widget-type tokens settled on snake_case everywhere:
  `"multiselect"` → `"multi_select"`, `"combobox"` → `"combo_box"` (in
  `SearchRegistration.widget_type`, `FormworkSearchView.widget_type`, and the template
  cache keys); `MULTISELECT_TEMPLATE`/`COMBOBOX_TEMPLATE` → `MULTI_SELECT_TEMPLATE`/
  `COMBO_BOX_TEMPLATE`; `widgets/combobox.py` → `widgets/combo_box.py` (class names stay
  PascalCase; DOM CSS classes are unchanged). `django_formwork/__init__.py` now resolves
  every documented public name lazily via module `__getattr__` (PEP 562): forms, formsets,
  fields, view base classes, `FormworkModel`, async mixins, renderers. So
  `from django_formwork import FormworkModel` finally works without forcing the app
  registry at import time; docs and examples show top-level imports as canonical.
  `registry.py` became `_registry.py` (internal; key format and registration API are
  explicitly not semver-covered). New import-surface tests in `tests/test_packaging.py`,
  including a no-`DJANGO_SETTINGS_MODULE` subprocess import check.
- **Packaging batch: icons.css out of site-packages + installation guide rewrite**
  (2026-07-10). `manage.py formwork install` no longer writes the generated `icons.css` into
  the installed package dir (which failed on read-only installs: containers, system pip,
  Nix). It now targets the project static dir (first `STATICFILES_DIRS` entry, else
  `BASE_DIR/static`, with a `STATICFILES_DIRS` injection + warning in the fallback case) and
  grew an `--output DIR` override; the stray cwd-relative `static/iconx/icons.css` artifact
  from iconx's add-time generate is gone (`--no-generate` + explicit generate).
  `formwork.css` dropped its `../iconx/icons.css` import; the project's Tailwind input now
  imports the generated file itself (both example apps, the e2e harness, and the CI comments
  updated). `installation.md` was rewritten as one walkthrough that actually builds:
  `django_iconx` in `INSTALLED_APPS`, `formwork install` as a required documented step (the
  command finally has reference docs), import only `formwork.css` + the generated icons CSS,
  and the `@source "path/to/django_formwork/"` directive with the tree-shaking rationale.
  New command tests in `tests/test_formwork_command.py`. Decided separately: the
  `django-iconx` constraint stays uncapped (maintainer owns the package).
- **Security batch: Alpine escaping, registry key collisions, forced `widget_type`,
  `FormworkValidateView` hardening** (2026-07-10). escapejs'd every user-influenced value
  interpolated into an Alpine `x-data`/expression context in both template engines
  (`date_picker`, `otp_input`, `input_number`, plus the `SEARCH_SELECT_TEMPLATE` and
  `COMBOBOX_TEMPLATE` htmx fragments) with hostile-value regression tests. `make_key` now
  includes the form module/qualname + field name so two forms on the same model+fields can't
  overwrite each other's decorator or queryset. `FormworkAutoSearchView` ignores the client
  `?type=` param and renders with the registration's widget type; templates stopped sending
  it and `VALID_WIDGET_TYPES` was removed. `FormworkValidateView` gained a
  `validate_decorator` hook and a `MAX_TEXT_LENGTH` (50k) truncation cap.
- **Removed `PhoneInput` and the bundled country/dial-code dataset (`data.py`)** (2026-07-06).
  It put application data in the framework and emitted a non-normalized, unvalidated phone
  string. The `full` example now ships a project-local `PhoneInput` (widget + app template under
  `taskmanager`) as the reference pattern; real apps should use `django-phonenumber-field`.
  Removed the widget, both templates, the phone CSS, its tests, and the e2e usage; updated the
  README, docs, widget reference, and changelog. `data.py` had no remaining consumer, so it was
  deleted outright.
- **Removed `CountryInput` and `country_choices()`** (2026-07-05). The widget was a thin
  `SearchSelect` wrapper pre-loaded with an ISO 3166-1 list that never validated (choices sat
  on the widget, not the field, so every submission was rejected). Decided country lists are
  application data, not framework data: build a `forms.ChoiceField(choices=...,
  widget=SearchSelect())` from your own list (or `django-countries`). Deleted the widget + its
  test, dropped `country_choices()` from `data.py` (kept the table for `PhoneInput`'s dial
  codes), moved a demo country list into the example apps, and updated the README, docs index,
  widget reference, changelog, and both example apps.

---

<details>
<summary>Audit provenance</summary>

66 findings across 11 dimensions; every bug/security/critical claim adversarially re-verified
against source (11 verified, 1 refuted: a claimed `SearchSelect` load-once error-handling bug
that turned out to be already handled in the `hx-on::` template attributes). File:line
references throughout point at the evidence. Severities reflect post-verification adjustments
(e.g. file-upload validation downgraded high to medium as it matches standard Django widget
semantics; the misleading API is the real issue).
</details>
