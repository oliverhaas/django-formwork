"""E2e tests for complex forms with cross-field validation and morph resilience."""

import pytest
from playwright.sync_api import expect

from .conftest import submit


def _fill_base_fields(page):
    """Fill all required base fields with valid data."""
    page.locator('input[name="password"]').fill("abc123")
    page.locator('input[name="confirm_password"]').fill("abc123")
    page.locator('input[name="start_date"]').fill("2025-01-01")
    page.locator('input[name="end_date"]').fill("2025-12-31")
    page.locator('input[name="terms"]').check()


def _pick_search_select(page, value, label):
    """Open SearchSelect, load results via htmx, and pick an option."""
    details = page.locator("details.search-select")
    # Open the dropdown via JS (summary::before overlay blocks clicks)
    page.evaluate("document.querySelector('details.search-select').open = true")
    # Focus the search input to trigger the htmx options load
    search = details.locator("input[type='text']")
    search.evaluate("el => { el.focus(); el.dispatchEvent(new Event('focus')); }")
    # click() auto-waits for the option button from the htmx response
    details.locator(f'button[data-value="{value}"]').click()
    expect(details.locator("summary")).to_contain_text(label)


def _fill_base_fields_silently(page):
    """Set base-field values without input/change events, so no auto-validate fires."""
    page.evaluate(
        """(() => {
            document.querySelector('input[name="password"]').value = 'abc123';
            document.querySelector('input[name="confirm_password"]').value = 'abc123';
            document.querySelector('input[name="start_date"]').value = '2025-01-01';
            document.querySelector('input[name="end_date"]').value = '2025-12-31';
            document.querySelector('input[name="terms"]').checked = true;
        })()""",
    )


def _settle_auto_validate(page):
    """Wait out the auto-validate debounce so its morph lands before we proceed."""
    page.wait_for_timeout(2500)


def _toggle_multiselect_option(page, value, label):
    """Open MultiSelect and toggle an option via Alpine data store."""
    # Use Alpine's toggle method directly: it's more reliable than clicking
    # checkboxes injected by htmx (avoids timing issues with Alpine init).
    page.evaluate(
        f"""(() => {{
            const ms = document.querySelector('details.multiselect');
            const data = Alpine.$data(ms);
            data.toggle('{value}', '{label}', '');
        }})()""",
    )
    page.wait_for_timeout(200)


class TestComplexFormStructure:
    """Basic rendering and structure tests."""

    def test_page_loads(self, complex_page):
        assert complex_page.title() == "Complex Form"

    def test_form_renders(self, complex_page):
        form = complex_page.locator("#complex-form")
        assert form.is_visible()

    def test_has_two_password_fields(self, complex_page):
        pw_labels = complex_page.locator("label.password-reveal")
        assert pw_labels.count() == 2

    def test_has_search_select(self, complex_page):
        details = complex_page.locator("details.search-select")
        assert details.count() == 1

    def test_has_multi_select(self, complex_page):
        details = complex_page.locator("details.multiselect")
        assert details.count() == 1

    def test_has_date_fields(self, complex_page):
        start = complex_page.locator('input[name="start_date"]')
        end = complex_page.locator('input[name="end_date"]')
        assert start.get_attribute("type") == "date"
        assert end.get_attribute("type") == "date"

    def test_has_terms_checkbox(self, complex_page):
        terms = complex_page.locator('input[name="terms"]')
        assert terms.count() == 1


class TestComplexFormValidation:
    """Cross-field validation tests."""

    def test_submit_empty_shows_errors(self, complex_page):
        submit(complex_page)
        errors = complex_page.locator("#complex-form details.formwork-errors")
        assert errors.count() >= 3

    def test_password_mismatch_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("xyz789")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_confirm_password_error")
        assert errors.count() == 1
        assert "match" in errors.text_content().lower()

    def test_password_match_no_error(self, complex_page):
        _fill_base_fields(complex_page)
        submit(complex_page)
        errors = complex_page.locator("#id_confirm_password_error")
        assert errors.count() == 0

    def test_date_range_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-12-31")
        complex_page.locator('input[name="end_date"]').fill("2025-01-01")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_end_date_error")
        assert errors.count() == 1
        assert "after" in errors.text_content().lower()

    def test_valid_date_range_no_error(self, complex_page):
        _fill_base_fields(complex_page)
        submit(complex_page)
        errors = complex_page.locator("#id_end_date_error")
        assert errors.count() == 0

    def test_terms_required(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        # Don't check terms
        submit(complex_page)
        errors = complex_page.locator("#id_terms_error")
        assert errors.count() == 1

    def test_country_without_languages_error(self, complex_page):
        """Selecting a country without languages shows cross-field error."""
        _fill_base_fields(complex_page)
        _pick_search_select(complex_page, "us", "United States")
        submit(complex_page)
        errors = complex_page.locator("#id_languages_error")
        assert errors.count() == 1
        assert "language" in errors.text_content().lower()

    def test_country_with_languages_no_error(self, complex_page):
        """Selecting both country and languages passes cross-field validation."""
        _fill_base_fields(complex_page)
        _pick_search_select(complex_page, "us", "United States")
        _toggle_multiselect_option(complex_page, "py", "Python")
        submit(complex_page)
        errors = complex_page.locator("#id_languages_error")
        assert errors.count() == 0


class TestComplexFormMorphResilience:
    """Morph resilience tests: client-side state survives server-side morphing."""

    def test_search_select_value_survives_morph(self, complex_page):
        """SearchSelect selected value persists through morph."""
        _pick_search_select(complex_page, "us", "United States")
        summary = complex_page.locator("details.search-select summary")
        expect(summary).to_contain_text("United States", timeout=2000)
        submit(complex_page)
        hidden = complex_page.locator('input[name="country"]')
        assert hidden.input_value() == "us"
        summary = complex_page.locator("details.search-select summary")
        expect(summary).to_contain_text("United States", timeout=2000)

    def test_multiselect_value_survives_morph(self, complex_page):
        """MultiSelect selected values persist through morph."""
        _toggle_multiselect_option(complex_page, "py", "Python")
        submit(complex_page)
        hidden = complex_page.locator('input[type="hidden"][name="languages"]')
        values = [hidden.nth(i).input_value() for i in range(hidden.count())]
        assert "py" in values

    def test_password_reveal_state_survives_morph(self, complex_page):
        """PasswordReveal show/hide state persists through morph."""
        inp = complex_page.locator('input[name="password"]')
        inp.fill("secret")
        complex_page.locator("label.password-reveal button").first.click()
        expect(inp).to_have_attribute("type", "text")
        submit(complex_page)
        # Reveal state preserved (x-data not overwritten).  The morph drops
        # the Alpine-applied type attribute, so check the Alpine state and
        # the effective input type (attribute-less inputs render as text).
        assert (
            complex_page.evaluate(
                "Alpine.$data(document.querySelector('label.password-reveal')).show",
            )
            is True
        )
        assert inp.evaluate("el => el.type") == "text"

    def test_search_select_dropdown_state_survives_morph(self, complex_page):
        """Open SearchSelect dropdown stays open through morph."""
        page = complex_page
        page.evaluate("document.querySelector('details.search-select').open = true")
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelector('details.search-select').open")
        # Submit via JS: open dropdown's summary::before overlay blocks clicks
        page.evaluate(
            """(() => {
            const form = document.querySelector('form[hx-post]');
            form.noValidate = true;
            window.__fwSubmitDone = false;
            form.addEventListener('htmx:after:swap', () => { window.__fwSubmitDone = true; }, {once: true});
            document.querySelector('button[type=\"submit\"]').click();
        })()""",
        )
        page.wait_for_function("window.__fwSubmitDone === true")
        # htmx 4 morph (with formwork's morphIgnore) preserves open attribute on <details>
        assert page.evaluate("document.querySelector('details.search-select').open")

    def test_auto_validate_shows_error_without_submit(self, complex_page):
        """Auto-validation shows cross-field errors without explicit submit."""
        page = complex_page
        # Pick a country via SearchSelect (triggers change)
        _pick_search_select(page, "us", "United States")
        # Cross-field error: country without languages.  The timeout covers
        # the 1500ms auto-validate debounce plus the round trip.
        errors = page.locator("#id_languages_error")
        expect(errors).to_have_count(1, timeout=5000)
        assert "language" in errors.text_content().lower()


@pytest.mark.screenshot
def test_search_select_open_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: SearchSelect dropdown open with server-loaded results."""
    page = complex_page
    page.evaluate("document.querySelector('details.search-select').open = true")
    page.wait_for_timeout(300)
    search = page.locator("details.search-select input[type='text']")
    search.evaluate("el => { el.focus(); el.dispatchEvent(new Event('focus')); }")
    page.wait_for_timeout(800)
    assert_screenshot(
        page.locator("#id_country_field"),
        "complex-search-select-open.png",
        capture_dropdown=True,
    )


@pytest.mark.screenshot
def test_search_select_filtered_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: SearchSelect dropdown with search text filtering results."""
    page = complex_page
    page.evaluate("document.querySelector('details.search-select').open = true")
    page.wait_for_timeout(300)
    search = page.locator("details.search-select input[type='text']")
    search.evaluate("el => { el.focus(); el.dispatchEvent(new Event('focus')); }")
    page.wait_for_timeout(800)
    search.evaluate(
        """el => {
        el.value = 'uni';
        el.dispatchEvent(new Event('input', {bubbles: true}));
    }""",
    )
    page.wait_for_timeout(800)
    assert_screenshot(
        page.locator("#id_country_field"),
        "complex-search-select-filtered.png",
        capture_dropdown=True,
    )


@pytest.mark.screenshot
def test_multiselect_open_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: MultiSelect dropdown open with server-loaded options."""
    page = complex_page
    page.evaluate("document.querySelector('details.multiselect').open = true")
    page.wait_for_timeout(300)
    search = page.locator("details.multiselect input[type='text']")
    search.evaluate("el => { el.focus(); el.dispatchEvent(new Event('focus')); }")
    page.wait_for_timeout(800)
    assert_screenshot(
        page.locator("#id_languages_field"),
        "complex-multiselect-open.png",
        capture_dropdown=True,
    )


@pytest.mark.screenshot
def test_multiselect_selections_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: MultiSelect summary with three options toggled."""
    page = complex_page
    _toggle_multiselect_option(page, "py", "Python")
    _toggle_multiselect_option(page, "rs", "Rust")
    _toggle_multiselect_option(page, "go", "Go")
    _settle_auto_validate(page)
    assert_screenshot(page.locator("#id_languages_field"), "complex-multiselect-selected.png")


@pytest.mark.screenshot
def test_full_form_filled_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: all fields filled, before explicit submit."""
    page = complex_page
    _pick_search_select(page, "de", "Germany")
    _toggle_multiselect_option(page, "py", "Python")
    _toggle_multiselect_option(page, "ts", "TypeScript")
    _settle_auto_validate(page)
    # The morph preserves the SearchSelect summary label now; the hidden
    # input carries the submitted key.
    expect(page.locator('input[name="country"]')).to_have_value("de")
    _fill_base_fields_silently(page)
    assert_screenshot(page.locator("#complex-form"), "complex-form-filled.png")


@pytest.mark.screenshot
def test_full_form_after_submit_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: valid form submitted with no errors, morphed state."""
    page = complex_page
    _pick_search_select(page, "de", "Germany")
    _toggle_multiselect_option(page, "py", "Python")
    _toggle_multiselect_option(page, "ts", "TypeScript")
    _settle_auto_validate(page)
    _fill_base_fields_silently(page)
    submit(page)
    expect(page.locator('input[name="country"]')).to_have_value("de")
    expect(page.locator("#complex-form details.formwork-errors")).to_have_count(0)
    assert_screenshot(page.locator("#complex-form"), "complex-form-submitted.png")


@pytest.mark.screenshot
def test_password_reveal_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: PasswordReveal with the password shown as text."""
    page = complex_page
    field = page.locator("#id_password_field")
    # Set the value without an input event so no morph can wipe it.
    page.locator('input[name="password"]').evaluate("el => el.value = 'supersecret'")
    field.locator("label.password-reveal button").click()
    page.wait_for_timeout(200)
    assert_screenshot(field, "complex-password-revealed.png")


@pytest.mark.screenshot
def test_auto_validate_error_then_fix_screenshot(complex_page, assert_screenshot):
    """Visual snapshot: auto-validate cross-field error, then the fixed state."""
    page = complex_page
    _pick_search_select(page, "us", "United States")
    _settle_auto_validate(page)
    errors = page.locator("#id_languages_error")
    expect(errors).to_have_count(1, timeout=3000)
    assert_screenshot(page.locator("#id_languages_field"), "complex-languages-error.png")
    _toggle_multiselect_option(page, "py", "Python")
    _settle_auto_validate(page)
    expect(errors).to_have_count(0, timeout=3000)
    assert_screenshot(page.locator("#id_languages_field"), "complex-languages-fixed.png")
