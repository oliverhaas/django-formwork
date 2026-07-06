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
   `examples/simple/app.css`; the docs just don't match it.
3. **API / naming lock-in.** `widget_type` is spelled three ways, `ComboBox` four; the
   public import surface is fragmented; the registry is public-but-should-be-internal. These
   freeze under semver at 1.0 and must be settled first.

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
- [ ] **escapejs every value interpolated into an Alpine `x-data` / JS-string context (two
  confirmed XSS).** Alpine reads the HTML-entity-decoded attribute and `eval`s it, so
  Django's autoescaping doesn't defend. `input_mask.html`/`search_select.html` already use
  `escapejs`, proving the fix is known; apply it consistently and audit every inline widget
  in one pass. (small)
    - `date_picker.html:3`, exploitable on validation-error redisplay (arbitrary length value)
    - `views.py:63` (htmx `SEARCH_SELECT_TEMPLATE`), exploitable via stored data when
      `to_field_name` is a user-editable slug/username field
    - `otp_input.html:2`, same unescaped pattern (constrained, but fix it too)
- [ ] **Prevent registry key collisions that override auth/queryset across registrations.**
  `make_key` uses only `(model_label, sorted search_fields, to_field_name)`; the
  `queryset_factory` and `search_decorator` aren't in the key, and `register()` overwrites
  last-writer-wins on a process-global dict re-populated per request. A public/unfiltered
  `SearchSelect` on the same model+fields as a tenant-scoped `login_required` one shares a
  URL and nondeterministically drops the decorator and leaks the unfiltered queryset. Fold a
  discriminator (form module/qualname, as `make_choices_key` already does) into the key, or
  refuse to overwrite a materially different registration. (`django_formwork/registry.py:57`,
  medium)

### Packaging: make a fresh install actually work

- [ ] **Fix `installation.md` so the build works and widgets render.** Replace the CSS block
  with the `examples/simple/app.css` recipe: import *only* `formwork.css` (it pulls in
  tailwind+daisyui+icons itself), add `@source "path/to/site-packages/django_formwork/";`,
  add `django_iconx` to `INSTALLED_APPS`, and add `python manage.py formwork install` as a
  required step. Document the `formwork install` command (currently the only CLI surface,
  entirely undocumented). (`docs/getting-started/installation.md:38`, small)
- [ ] **Cap the unbounded pre-1.0 `django-iconx` dependency.** `>=0.2.0` with no upper bound
  on a 0.x package whose API can break on any minor bump. A future 0.3/0.4 can silently break
  every adopter's `formwork install`. Pin `>=0.2.0,<0.3` (or fast-track iconx to 1.0).
  (`pyproject.toml:29`, small)

### API surface: lock names before semver freezes them

- [ ] **Lock `widget_type` and `ComboBox` naming to one convention.** Tokens ship three
  spellings (`search_select` vs `combobox` vs `multiselect`); `ComboBox` is spelled four ways
  (class / `combo_box.html` / `combo_box.js` / token `"combobox"`). Public via
  `VALID_WIDGET_TYPES`, the `?type=` query param, and `SearchRegistration.widget_type`.
  Recommend snake_case everywhere. (`django_formwork/views.py:136`, medium)
- [ ] **Reconcile the `FormworkModel` import path + decide the top-level re-export policy.**
  The `ImproperlyConfigured` message and docstrings tell users `from django_formwork import
  FormworkModel`, which raises `ImportError`; only `django_formwork.models` works. More
  broadly, formsets, view base classes, and async mixins are submodule-only while forms are
  top-level (an arbitrary split). Decide the canonical surface (recommend a lazy module-level
  `__getattr__` so documented names resolve) and make it uniform.
  (`django_formwork/__init__.py:25`, small)

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
- [ ] **Settle the config surface + scope the auto-search registry as internal.**
  `search_threshold` is class-only, `max_results` isn't settable from the widget,
  `FORMWORK_FORCE_ASYNC` is an undocumented bare `getattr`; meanwhile `registry.py` publicly
  exports `make_key`/`register`/`SearchRegistration`, freezing a key format the code itself
  plans to evolve. Introduce one documented `FORMWORK` settings dict + constructor kwargs;
  drop registry internals from the public surface. (`widgets/search_select.py:54`, medium)
- [ ] **Move generated `icons.css` out of site-packages.** `formwork install` hardcodes
  output into the installed package dir, so it fails on read-only deploys (containers, system
  pip, Nix, zipapp). Expose `--output` defaulting to a project static dir; make the import
  overridable. (Shapes what the install docs can even recommend.)
  (`management/commands/formwork.py:16`, medium)
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

- [ ] escapejs the two confirmed XSS sinks (`date_picker.html:3`, `views.py:63`) + `otp_input.html`
- [x] ~~Ship `CountryField`~~ Removed `CountryInput`/`country_choices()` entirely (2026-07-05)
- [ ] Swap `installation.md` CSS block for the `examples/simple/app.css` recipe + add the
  `formwork install` / `django_iconx` step
- [ ] Cap `django-iconx` to `>=0.2.0,<0.3` (one line, removes a release blocker)
- [ ] Add `fail_under=90` to `[tool.coverage.report]`; delete/confirm-gitignore the stale
  `coverage.xml` (reports a misleading 36% vs the real ~91%)
- [ ] Force `FormworkAutoSearchView.widget_type` from the registration, ignoring client `?type=`
  (`views.py:143`)
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

1. **Public API surface:** commit to uniform lazy top-level re-exports (forms, formsets, view
   base classes, `FormworkModel`, async mixins all from `django_formwork`), or a documented
   "import from submodules" convention? And is the registry semver-covered at all? Must be
   decided before the freeze.
2. **Is i18n a 1.0 requirement or a fast-follow?** Full gettext + locale + JS externalization
   is large and cheapest *after* the inline-x-data extraction. Blocking 1.0 on it could delay
   significantly; shipping English-only forecloses non-English adopters until a minor release.
3. **Which strategic feature is the 1.0 differentiator?** You can realistically land one large
   feature for 1.0: conditional fields (medium, highest value-per-effort), the layout system
   (large, decides non-trivial CRUD adoption), or the inline-formset UI (large, most-requested).
   Pick deliberately.
4. **Where should generated `icons.css` live**, inside site-packages (current, breaks
   read-only installs) or a project-controlled static dir with an overridable import? Reshapes
   the whole CSS distribution + install-docs story.
5. **Type-checking direction:** keep both mypy and ty (pay the double-suppression tax, flip
   `respect-type-ignore-comments=true`), or drop one checker for the library source?
6. **Should `max_size`/`accept` be enforced server-side** (auto-attach validators, changing
   behavior) or remain presentational-only with loud docs? An API-semantics call that freezes
   user expectations at 1.0.
7. **`FormworkValidateView`** is CSRF-exempt with no default auth hook and no length cap on
   POSTed text (unlike search). Harmless for the base class (no-op `get_errors`), but a real
   subclass doing expensive work (spellcheck/LLM/DB) inherits an unauthenticated,
   unrate-limited endpoint. Add the same decorator hook + length cap the search side has, or
   just document the responsibility? (Audit verdict: *uncertain*, your call.)

---

## Done

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
