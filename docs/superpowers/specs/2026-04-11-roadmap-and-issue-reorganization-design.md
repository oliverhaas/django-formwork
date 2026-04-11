# Roadmap and Issue Reorganization

## Context

django-formwork is at v0.1.0a1 with 15 custom widgets, async form support, auto-search registry, idiomorph integration, and 547 tests (325 unit + 222 e2e). The codebase is clean with no outstanding TODOs.

The package is primarily built for the maintainer's own use (and django-voyager), but structured cleanly enough for others to adopt or learn from. The API is not yet locked down — naming, imports, widget configuration, and the auto-search registry may all change before 1.0.

There are 11 open GitHub issues (#8-#17, #24) ranging from tactical bug fixes to ambitious vision statements. Some are too large to work through (#8 has 40+ checkboxes), and several topics aren't tracked at all.

## Goals

1. Reorganize GitHub issues into workable, focused units with clear priorities
2. Fill gaps: test recipes, Jinja2 parity testing, API surface review, examples
3. Establish a phased execution order that builds foundations before features

## Priority Phases

### Phase 1: Test Recipes (P0)

Establish canonical, repeatable test patterns before writing more tests.

**New issue: Canonical test patterns and recipes**

- **Unit test recipe for widgets**: render with `widget.render()`, verify HTML structure with BeautifulSoup, test `value_from_datadict`, test with `value=None`, no `id`, prefix handling
- **Unit test recipe for views**: request factory, test valid/invalid/missing params, error handling
- **Unit test recipe for forms**: form instantiation, validation, cleaning, rendering via renderer
- **E2e test recipe for widgets**: Playwright interaction, morph resilience, error display/clearing
- **Visual regression recipe**: Percy screenshot approach, what to capture, naming conventions
- Each recipe documented as a docstring or comment in a test helper module, with one exemplar test per category

### Phase 2: Production Hardening (P0)

Split #8 (production readiness) into 6 focused issues, then close #8.

**#8a — Bug fixes: CSP violations and JS issues**

- Inline script in `formwork.html` breaks CSP
- Rating clear button inline `onclick` handler breaks CSP
- `formwork.js` unconditionally overwrites `ignoreActiveValue`
- `beforeNodeRemoved` template walk incomplete
- No `x-show` preservation in morph

**#8b — Missing test coverage**

- `_format_size()`, `_format_accept()` utility tests
- Widget with `value=None`, no `id` in attrs
- FormworkModelForm with real model
- Formset rendering
- View error handling edge cases
- `_build_highlighted` edge cases
- Optgroup rendering
- Form prefix handling
- Parametrize repetitive tests, add negative tests

**#8c — API surface and code quality**

- `__all__` in all public modules
- Remove unnecessary `default_auto_field` in `apps.py`
- Ruff/mypy target version mismatch (py313 should be py312)
- Duplicated `get_context()` in FileDropZone/ImageDropZone
- Move `FormworkSearchView` inline templates to template files

**#8d — Security hardening**

- CSRF-exempt validation view — document or add opt-in
- No query length limit in search views
- `mark_safe` audit and documentation

**#8e — Accessibility (WCAG 2.1 AA)**

- Missing focus indicators on dropdown search inputs
- No `role="listbox"` on static MultiSelect
- Tooltip error screen reader announcement verification

**#8f — Documentation gaps**

- Per-widget API reference
- Server-side search/validation docs
- Browser support matrix
- DaisyUI version pinning
- `formwork-dist.css` purpose docs
- CSRF note for ValidatedTextarea

### Phase 3: Simple Example (P1)

**New issue: Simple example app — minimal setup with one form**

- Standalone Django project in `examples/simple/`
- Minimal setup: install formwork, one form with a mix of standard + custom widgets
- Demonstrates: `FormworkForm`, `FormworkRenderer`, `{% formwork_css %}` / `{% formwork_js %}`, basic validation, morph behavior
- Goal: verify the onboarding path — can someone go from zero to working form quickly?
- Runnable with `uv run manage.py runserver`

### Phase 4: Jinja2 Support + Parity Tests (P1)

**Refine #24 — Jinja2 template support**

- Ship Jinja2 versions of all widget/form/field templates alongside DTL ones
- Auto-detect which engine to use based on project configuration
- Update `FormworkRenderer` to support both backends

**New issue: Jinja2/DTL parity test suite**

- Every widget and form/field template gets a test that renders via both engines
- Parse output with BeautifulSoup, compare HTML trees (whitespace-insensitive)
- Catches drift between template sets
- Runs as part of normal test suite (not optional)

### Phase 5: Full Example (P1)

**Refine #12 — Full example app with CRUD, search/filter, and wizard**

- Standalone Django project in `examples/full/`
- Multiple views exercising real patterns:
  - CRUD page (list, detail, edit, delete with htmx)
  - Search/filter list (htmx-driven filtering, URL state)
  - Multi-step wizard (form state, progress indicator, dependent fields)
- Uses the full stack: htmx, Alpine, DaisyUI, morph
- Goal: stress-test formwork's real-world ergonomics, surface missing features
- Remaining examples from #12 (modal forms, inline editing, bulk actions, infinite scroll) stay as future ideas

### Phase 6: API Refinement (P2)

**New issue: API surface review**

- Review informed by building both examples
- Naming audit: widget classes, view names, template tag names, import paths
- Widget configuration consistency: constructor args vs class attributes
- Auto-search registry ergonomics — is the implicit magic right?
- Public interface: what should be importable from top-level vs submodules?
- Goal: settle the public API before 1.0

### Phase 7: Everything Else (P2/P3)

**Existing issues — keep, add priority labels:**

| Issue | Description | Priority | Action |
|-------|-------------|----------|--------|
| #9 | Icons via CSS mask-image | P2 | Keep as-is |
| #10 | Django 6.0 template partials | P3 | Keep as-is |
| #11 | Vision: htmx + Alpine + DaisyUI stack | P3 | Keep, revisit after examples |
| #13 | Starter templates and layout components | P2 | Keep, depends on examples |
| #14 | Theming and styling documentation | P2 | Keep as-is |
| #15 | Custom widget ideas | P2 | Keep, examples will prioritize |
| #16 | Standard widget coverage gaps | P1 | Bump priority, related to Phase 2 |
| #17 | Unsaved changes indicator | P3 | Keep as-is |

**New issue: Packaging and CI improvements (P2)**

Extracted from #8:

- `formwork-dist.css` in wheel — exclude or document
- `py.typed` verification in tests
- Publish workflow version verification
- Changelog automation (towncrier or similar)

## Changes to Existing Issues

| Issue | Action |
|-------|--------|
| #8 | Split into 6 focused issues (#8a-#8f), close #8 with cross-references |
| #9 | Add P2 label |
| #10 | Add P3 label |
| #11 | Add P3 label |
| #12 | Rewrite as "full example" (Phase 5), remaining ideas stay as backlog |
| #13 | Add P2 label |
| #14 | Add P2 label |
| #15 | Add P2 label |
| #16 | Add P1 label (bump) |
| #17 | Add P3 label |
| #24 | Refine scope for Jinja2 template support |

## New Issues to Create (12)

| # | Title | Phase | Priority |
|---|-------|-------|----------|
| 1 | Canonical test patterns and recipes | 1 | P0 |
| 2 | Bug fixes: CSP violations and JS issues | 2 | P0 |
| 3 | Missing test coverage | 2 | P0 |
| 4 | API surface and code quality | 2 | P0 |
| 5 | Security hardening | 2 | P0 |
| 6 | Accessibility (WCAG 2.1 AA) | 2 | P0 |
| 7 | Documentation gaps | 2 | P0 |
| 8 | Simple example app | 3 | P1 |
| 9 | Jinja2/DTL parity test suite | 4 | P1 |
| 10 | Full example app | 5 | P1 |
| 11 | API surface review | 6 | P2 |
| 12 | Packaging and CI improvements | 7 | P2 |

**Total after reorganization: 21 open issues** (12 new + 9 existing kept open)

## Design Decisions

- **Test recipes before production fixes**: establishing patterns first means all Phase 2 work follows consistent recipes from the start.
- **Examples as discovery**: the simple and full examples are explicitly designed to surface gaps — expect new issues to emerge from building them.
- **API not locked until Phase 6**: building examples first avoids premature API decisions.
- **Both template engines long-term**: Jinja2 and DTL are both first-class, with parity tests to prevent drift.
- **Primary consumer is the maintainer**: optimize for own needs (and django-voyager), keep structure clean for others.
