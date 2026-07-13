"""E2e tests for the Tight Form: tooltip errors on a compact, help-text-free form."""

from .conftest import submit


class TestTightForm:
    """Tooltip error display on a compact, help-text-free form."""

    def test_page_loads(self, tight_page):
        assert tight_page.title() == "Tight Form"

    def test_form_renders(self, tight_page):
        assert tight_page.locator("#tight-form").is_visible()

    def test_no_help_disclosures(self, tight_page):
        """No help text means no disclosure rows for an inline error to shove."""
        assert tight_page.locator("#tight-form .formwork-disclosure").count() == 0

    def test_submit_empty_shows_tooltip(self, tight_page):
        submit(tight_page)
        assert tight_page.locator("#id_username_tooltip").count() == 1

    def test_error_renders_as_tooltip_not_inline(self, tight_page):
        submit(tight_page)
        assert tight_page.locator("#tight-form .tooltip-error").count() >= 1
        assert tight_page.locator("#tight-form details.formwork-errors").count() == 0

    def test_error_has_role_alert(self, tight_page):
        submit(tight_page)
        alerts = tight_page.locator('#tight-form .tooltip-content[role="alert"]')
        assert alerts.count() >= 1

    def test_aria_invalid_set(self, tight_page):
        submit(tight_page)
        assert tight_page.locator('#tight-form [aria-invalid="true"]').count() >= 1

    def test_server_only_rule_shows_tooltip(self, tight_page):
        """ "admin" passes native validation but is rejected server-side."""
        tight_page.locator('input[name="username"]').fill("admin")
        tight_page.locator('input[name="pin"]').fill("1234")
        submit(tight_page)
        assert tight_page.locator("#id_username_tooltip").count() == 1

    def test_valid_submit_clears_tooltip(self, tight_page):
        submit(tight_page)
        assert tight_page.locator("#id_username_tooltip").count() == 1
        tight_page.locator('input[name="username"]').fill("bob")
        tight_page.locator('input[name="pin"]').fill("1234")
        submit(tight_page)
        assert tight_page.locator("#tight-form .tooltip-error").count() == 0
