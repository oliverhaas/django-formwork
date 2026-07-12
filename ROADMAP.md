# django-formwork: Road to 1.0

Working backlog of what's left to change, fix, or improve before this package earns a
solid 1.0. Produced 2026-07-05 from a multi-dimension audit; cleaned 2026-07-12, with all
completed items removed (git history and the changelog record what already landed).
File:line refs are where the evidence lives.

## Where it stands

The three original release blockers (security/correctness, CSS/icon distribution, API
naming lock-in) are resolved, and the architectural root cause is gone: the inline
`x-data` extraction landed 2026-07-12, so all widget JS now ships as lintable
`Alpine.data` modules with config passed through autoescaped `data-*` attributes, and
both template engines are verified in sync. What remains is scoped work: the
server-side upload enforcement decision, async save-path tests, screenshot coverage,
dropdown a11y, docs, and the config surface.

---

## Should have for 1.0

- [ ] **Make widget `max_size`/`accept` enforceable server-side (or loudly document them
  as cosmetic).** Drop zones enforce size and type only in client JS (file *count* is
  not enforced even there: a single-file zone accepts a multi-file drop); any direct
  POST uploads arbitrary size/type, a DoS + content-type bypass. It matches plain-Django
  semantics, but the API *implies* enforcement. The docs already warn for `max_size`;
  nothing says `accept` is cosmetic. Ship a validator auto-attached from the widget
  config (or `FormworkFileField`/`ImageField`), or extend the docs warnings to
  `accept`/count. (`django_formwork/widgets/file_drop_zone.py:42`, medium)
- [ ] **Cover the async ModelForm save path.** `avalidate_unique`'s ValidationError
  branch and the entire `_asave_m2m` loop have zero tests; async duplicate-unique
  validation and `asave()` on an M2M form are unexercised.
  (`django_formwork/async_forms.py:156`, medium)
- [ ] **Add screenshot coverage and deeper e2e for** `date_picker`, `input_mask`,
  `input_number`, `otp_input`. The extraction (2026-07-12) gave each its first browser
  smoke test, so their JS is no longer entirely undriven; still missing are screenshot
  baselines (none exist for these four) and the interaction cases the test files list
  as planned (keyboard navigation, morph preservation). (`tests/widgets/`, medium)
- [ ] **Fix custom-dropdown accessibility.** `MultiSelect` checkboxes are `display:none`
  (removed from the a11y tree); `keyboardNav` only toggles a CSS class and never sets
  `aria-activedescendant`/`aria-selected`.
  (`static/formwork/widgets/_helpers.js:15`, medium)
- [ ] **Document formsets, Jinja2 setup, and a consolidated settings page.** The marketed
  batched-uniqueness formsets have zero docs and no nav entry; Jinja2 users have no
  documented way to configure the renderer or emit CSS/JS (the tags are DTL-only
  `simple_tag`s that don't work in Jinja2); no single settings reference for
  `FORM_RENDERER`/`FORMWORK_FORCE_ASYNC`. (`mkdocs.yml:44`, medium)
- [ ] **Settle the config surface.** `search_threshold` is class-only, `max_results`
  isn't settable from the widget, `FORMWORK_FORCE_ASYNC` is an undocumented bare
  `getattr`. Introduce one documented `FORMWORK` settings dict + constructor kwargs.
  (`widgets/search_select.py:54`, medium)
- [ ] **Scope the global htmx morph config to formwork subtrees.** `formwork-core.js`
  pushes `'open'` into `htmx.config.morphIgnore` and appends x-for/x-if selectors to
  `morphSkipChildren` *globally*, silently changing morph for every non-formwork
  `<details>` and Alpine list on the host page. Gate on a formwork marker in the
  per-node hook. (`static/formwork/formwork-core.js:112`, medium)
- [ ] **Collapse the type-checking debt.** Two checkers with divergent suppression force
  every ignore to be written twice; `async_forms.py` types `self: Any` on all 13 methods,
  disabling checking on the entire async validation/ORM path. Give the cooperative mixins
  a TYPE_CHECKING protocol base, drop `self: Any`, and either flip
  `respect-type-ignore-comments=true` or drop one checker for a single source of truth.
  (`django_formwork/async_forms.py:47`, medium)
- [ ] **Conditional (show/hide) fields driven by other field values.** A near-universal
  real-form need with zero support today (users must abandon `{{ form }}`). Per VISION:
  easy to build fragile, so only with a design that holds up; needs a server-side guard
  so hidden fields skip validation.
  (`templates/django/forms/formwork_field.html:1`, medium)
- [ ] **Reduce e2e flakiness.** 211 `wait_for_timeout` sleeps (recounted 2026-07-12)
  violate the project's own Playwright guidance and will intermittently fail as the
  suite grows. Convert to `expect()` state-based waits.
  (`tests/widgets/test_search_select.py:1`, medium)

---

## Post-1.0 (additive; define the ceiling, don't block the freeze)

- [ ] **Inline-formset editing UI (add/remove/reorder rows).** The most-requested form-UI
  capability; the marketed batched-uniqueness formsets are 100% backend with zero
  rendering side. The htmx+Alpine machinery is already present. Ship a widget JS module
  wired to `FormworkBaseInlineFormSet`. (large)
- [ ] **Declarative form layout system** (fieldset grouping, multi-column, column span).
  `{{ form }}` can only produce one-column stacks; every non-trivial CRUD screen loses to
  crispy/manual templates. Design the API deliberately rather than rushing into the
  freeze. (large)
- [ ] **`TimePicker` / `DateTimePicker` / `DateRangePicker`.** `DatePicker` is the only
  temporal widget; `TimeField`/`DateTimeField` are among the most common Django fields.
  Reuses the existing calendar. (medium)
- [ ] **Tags/token input, plus color, slug, and JSON widgets.** The most frequently
  hand-rolled widgets in Django projects. (medium)
- [ ] **Full internationalization** (gettext + locale catalog + JS string
  externalization). No `{% trans %}` or `locale/` dir anywhere; dozens of hardcoded
  English strings block non-English deployment. The inline-x-data extraction has
  landed, so this is now unblocked. (large)
- [ ] **`FormworkWizardView` + an htmx form-submit mixin/helper.** The docs advertise a
  wizard that only exists hand-coded in `examples/full`; every view repeats the same
  `HX-Request` partial-vs-page + `HX-Redirect` branching, exactly the boilerplate the
  framework claims to eliminate. (medium/large)
- [ ] **Per-field template/escape hatch** (widget-tweaks/crispy equivalent) + remaining
  a11y polish (date-picker grid semantics). Lets non-DaisyUI stacks adopt without
  abandoning `{{ form }}`. (medium)
- [ ] **Repo hygiene.** Publish an npm package (or drop the bundler-import claim that
  can't resolve today), drop Git LFS for 340 KB of screenshots, fix the dead
  `publish.yml` version verification on the automated release path. (small)

---

## Quick wins (small effort, high value)

- [ ] Add a Jinja2 setup section (FORM_RENDERER wiring + how to emit CSS/JS)
- [ ] Document the no-`self` convention for `search_choices_<field>` handlers

---

## Open questions (your calls; decide before the relevant work)

1. **Is i18n a 1.0 requirement or a fast-follow?** Full gettext + locale + JS
   externalization is large (though the inline-x-data extraction that made it cheap has
   now landed). Blocking 1.0 on it could delay significantly; shipping English-only
   forecloses non-English adopters until a minor release.
2. **Which strategic feature is the 1.0 differentiator?** You can realistically land one
   large feature for 1.0: conditional fields (medium, highest value-per-effort), the
   layout system (large, decides non-trivial CRUD adoption), or the inline-formset UI
   (large, most-requested). Pick deliberately.
3. **Type-checking direction:** keep both mypy and ty (pay the double-suppression tax,
   flip `respect-type-ignore-comments=true`), or drop one checker for the library source?
4. **Should `max_size`/`accept` be enforced server-side** (auto-attach validators,
   changing behavior) or remain presentational-only with loud docs? An API-semantics call
   that freezes user expectations at 1.0.

---

<details>
<summary>Audit provenance</summary>

66 findings across 11 dimensions; every bug/security/critical claim adversarially
re-verified against source (11 verified, 1 refuted: a claimed `SearchSelect` load-once
error-handling bug that turned out to be already handled in the `hx-on::` template
attributes). File:line references throughout point at the evidence. Severities reflect
post-verification adjustments (e.g. file-upload validation downgraded high to medium as
it matches standard Django widget semantics; the misleading API is the real issue).
</details>
