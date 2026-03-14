"""E2e tests for complex forms with cross-field validation."""

from .conftest import submit


class TestComplexForm:
    """ComplexForm with password confirmation, date range, and terms."""

    def test_page_loads(self, complex_page):
        assert complex_page.title() == "Complex Forms"

    def test_form_renders(self, complex_page):
        form = complex_page.locator("#widget-form")
        assert form.is_visible()

    def test_has_two_password_fields(self, complex_page):
        pw_labels = complex_page.locator("label.password-reveal")
        assert pw_labels.count() == 2

    def test_has_date_fields(self, complex_page):
        start = complex_page.locator('input[name="start_date"]')
        end = complex_page.locator('input[name="end_date"]')
        assert start.get_attribute("type") == "date"
        assert end.get_attribute("type") == "date"

    def test_has_terms_checkbox(self, complex_page):
        terms = complex_page.locator('input[name="terms"]')
        assert terms.count() == 1

    def test_submit_empty_shows_errors(self, complex_page):
        submit(complex_page)
        tooltips = complex_page.locator("#widget-form .tooltip-error")
        assert tooltips.count() >= 3

    def test_password_mismatch_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("xyz789")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_confirm_password_errors")
        assert errors.count() == 1
        assert "match" in errors.text_content().lower()

    def test_password_match_no_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_confirm_password_errors")
        assert errors.count() == 0

    def test_date_range_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-12-31")
        complex_page.locator('input[name="end_date"]').fill("2025-01-01")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_end_date_errors")
        assert errors.count() == 1
        assert "after" in errors.text_content().lower()

    def test_valid_date_range_no_error(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        complex_page.locator('input[name="terms"]').check()
        submit(complex_page)
        errors = complex_page.locator("#id_end_date_errors")
        assert errors.count() == 0

    def test_terms_required(self, complex_page):
        complex_page.locator('input[name="password"]').fill("abc123")
        complex_page.locator('input[name="confirm_password"]').fill("abc123")
        complex_page.locator('input[name="start_date"]').fill("2025-01-01")
        complex_page.locator('input[name="end_date"]').fill("2025-12-31")
        # Don't check terms
        submit(complex_page)
        errors = complex_page.locator("#id_terms_errors")
        assert errors.count() == 1
