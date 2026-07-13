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


class TestTightFormFloatingLabels:
    """DaisyUI floating labels on the tight form's optional showcase fields."""

    # (fieldset id, placeholder text) for each floating widget: input, select, textarea.
    FLOATING_FIELDS = (
        ("id_nickname_field", "Nickname"),
        ("id_role_field", "Role"),
        ("id_note_field", "Note"),
    )

    def test_floating_labels_render(self, tight_page):
        """Each floating field emits a DaisyUI <label class="floating-label"> wrapper."""
        assert tight_page.locator("#tight-form .floating-label").count() == len(self.FLOATING_FIELDS)

    def test_floating_label_span_carries_placeholder(self, tight_page):
        """The floating <span> reuses the placeholder as its visible label text."""
        for field_id, placeholder in self.FLOATING_FIELDS:
            span = tight_page.locator(f"#{field_id} .floating-label > span")
            assert span.count() == 1
            assert span.inner_text().strip() == placeholder

    def test_redundant_fieldset_legend_hidden(self, tight_page):
        """The field template's own fieldset-legend is hidden so the label isn't duplicated."""
        for field_id, _ in self.FLOATING_FIELDS:
            legend = tight_page.locator(f"#{field_id} > .fieldset-legend")
            assert legend.count() == 1
            assert not legend.is_visible()

    def test_floating_wraps_the_control(self, tight_page):
        """The real control sits inside the floating-label wrapper (accessible name)."""
        assert tight_page.locator("#tight-form .floating-label > input[name='nickname']").count() == 1
        assert tight_page.locator("#tight-form .floating-label > select[name='role']").count() == 1
        assert tight_page.locator("#tight-form .floating-label > textarea[name='note']").count() == 1

    def test_select_has_no_placeholder_attr(self, tight_page):
        """<select> has no placeholder attribute; the text lives only in the span."""
        select = tight_page.locator("#tight-form select[name='role']")
        assert select.get_attribute("placeholder") is None
