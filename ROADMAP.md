# django-formwork: Road to 1.0

Working backlog of what's left to change, fix, or improve before this package earns a
solid 1.0. Produced 2026-07-05 from a multi-dimension audit; cleaned 2026-07-12, with all
completed items removed; reconciled 2026-07-18 against current source (git history and the
changelog record what already landed). File:line refs are where the evidence lives.

## Where it stands

The three original release blockers (security/correctness, CSS/icon distribution, API
naming lock-in) are resolved, and the architectural root cause is gone: the inline
`x-data` extraction landed 2026-07-12, so all widget JS now ships as lintable
`Alpine.data` modules with config passed through autoescaped `data-*` attributes. Since
the 2026-07-12 cleanup, editable tables (`as_row`/`as_rows`/`FormworkRowSaveMixin`), the
`error_display` Meta option, and a uniform top-level import surface all landed; the `Unreleased` changelog has grown large enough that an `a3`/beta cut is
due. What remains is scoped work: the server-side upload enforcement decision, the
remaining async save-path tests, screenshot coverage, dropdown a11y, docs (now including
editable tables), and the config surface.

---

## Should have for 1.0

- [ ] **Make widget `max_size`/`accept` enforceable server-side (or loudly document them
  as cosmetic).** Drop zones enforce size and type only in client JS (file *count* is
  not enforced even there: a single-file zone accepts a multi-file drop); any direct
  POST uploads arbitrary size/type, a DoS + content-type bypass. It matches plain-Django
  semantics, but the API *implies* enforcement. The docs already warn for `max_size`;
  nothing says `accept` is cosmetic. Ship a validator auto-attached from the widget
  config (or `FormworkFileField`/`ImageField`), or extend the docs warnings to
  `accept`/count. (`django_formwork/widgets/file_dropzone.py:21`, medium)
- [ ] **Finish covering the async ModelForm save path.** `avalidate_constraints` now has
  tests (constraint violation surfaces as a form error), but the two branches the audit
  named are still unexercised: `avalidate_unique`'s ValidationError branch has no async
  duplicate-unique test, and `_asave_m2m`'s loop body never runs because the only model
  form touching the hook (`BasicModelForm`) has no M2M fields, so the test just asserts the
  hook is bound. Add a unique-collision async test and an `asave()` test on a form with a
  real `ManyToManyField`. (`django_formwork/async_forms.py:125`, medium)
- [ ] **Add screenshot coverage and deeper e2e for** `date_picker`, `input_mask`,
  `stepper_number`, `otp_input`. The extraction (2026-07-12) gave each its first browser
  smoke test, so their JS is no longer entirely undriven; still missing are screenshot
  baselines (none exist for these four) and the interaction cases the test files list
  as planned (keyboard navigation, morph preservation). (`tests/widgets/`, medium)
- [ ] **Fix custom-dropdown accessibility.** Arrow-key navigation only adds a
  `highlighted` CSS class and scrolls the option into view; it never sets
  `aria-activedescendant`, so keyboard users get no announced highlight.
  (`static/formwork/widgets/_helpers.js:292`, medium)
- [ ] **Document formsets, editable tables, and a consolidated settings page.** The
  marketed batched-uniqueness formsets have zero docs and no nav entry; the newer editable
  tables (`as_row`/`as_rows`/`FormworkRowSaveMixin` and per-row htmx autosave) shipped with
  no docs or nav entry either; no single settings reference for
  `FORM_RENDERER`/`FORMWORK_FORCE_ASYNC`.
  (`mkdocs.yml:44`, medium)
- [ ] **Settle the config surface.** `search_threshold` is class-only, the search page
  size (`SEARCH_PAGE_SIZE`) isn't settable at all, `FORMWORK_FORCE_ASYNC` is an
  undocumented bare `getattr`. Introduce one documented `FORMWORK` settings dict +
  constructor kwargs. (`widgets/select.py:105`, medium)
- [ ] **Scope the global htmx morph config to formwork subtrees.** `formwork-core.js`
  pushes `'open'` into `htmx.config.morphIgnore` and appends x-for/x-if selectors to
  `morphSkipChildren` *globally*, silently changing morph for every non-formwork
  `<details>` and Alpine list on the host page. Gate on a formwork marker in the
  per-node hook. (`static/formwork/formwork-core.js:321`, medium)
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
  (`templates/formwork/forms/field.html:1`, medium)
- [ ] **Reduce e2e flakiness.** 194 `wait_for_timeout` sleeps (recounted 2026-11-01)
  violate the project's own Playwright guidance and will intermittently fail as the
  suite grows. Convert to `expect()` state-based waits.
  (`tests/widgets/test_select.py:1`, medium)

---

## Post-1.0 (additive; define the ceiling, don't block the freeze)

- [ ] **Inline-formset editing UI: add/remove/reorder rows.** The rendering and per-row
  autosave half landed (`as_row`/`as_rows`/`FormworkRowSaveMixin`, keyed on the posted pk),
  so formsets are no longer backend-only. What is left is the dynamic-row half: add, remove,
  and reorder are demonstrated ad hoc in `examples/full` but not shipped as a reusable
  widget JS module wired to `FormworkBaseInlineFormSet`. (medium)
- [ ] **Declarative form layout system** (fieldset grouping, multi-column, column span).
  `{{ form }}` can only produce one-column stacks; every non-trivial CRUD screen loses to
  crispy/manual templates. Design the API deliberately rather than rushing into the
  freeze. (large)
- [ ] **`TimePicker` / `DateTimePicker` / `DateRangePicker`.** `DatePicker`, `DateInput`
  and `DateRangeInput` handle dates only; `TimeField`/`DateTimeField` are among the most
  common Django fields. A calendar range picker reuses the existing calendar. (medium)
- [ ] **Tags/token input, plus color, slug, and JSON widgets.** The most frequently
  hand-rolled widgets in Django projects. (medium)
- [ ] **`FormworkWizardView` + an htmx form-submit mixin/helper.** The docs advertise a
  wizard that only exists hand-coded in `examples/full`; every view repeats the same
  `HX-Request` partial-vs-page + `HX-Redirect` branching, exactly the boilerplate the
  framework claims to eliminate. (medium/large)
- [ ] **Per-field template/escape hatch** (widget-tweaks/crispy equivalent) + remaining
  a11y polish (date-picker grid semantics). Lets non-DaisyUI stacks adopt without
  abandoning `{{ form }}`. (medium)
- [ ] **Repo hygiene.** Publish an npm package (or drop the bundler-import claim that
  can't resolve today), fix the dead `publish.yml` version verification on the
  automated release path. (small)

---

## Quick wins (small effort, high value)

- [ ] Make the `[more]`/`[less]` error toggle translatable. The text is CSS `content`
  in `formwork.css`, which no gettext call reaches. (`static/formwork/formwork.css:989`)

---

## Open questions (your calls; decide before the relevant work)

1. **Which strategic feature is the 1.0 differentiator?** You can realistically land one
   large feature for 1.0: conditional fields (medium, highest value-per-effort), the
   layout system (large, decides non-trivial CRUD adoption), or finishing the
   inline-formset UI (now medium, since rendering and per-row autosave already landed and
   only add/remove/reorder rows remains). Pick deliberately.
2. **Type-checking direction:** keep both mypy and ty (pay the double-suppression tax,
   flip `respect-type-ignore-comments=true`), or drop one checker for the library source?
3. **Should `max_size`/`accept` be enforced server-side** (auto-attach validators,
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
