"""Form structure and morph infrastructure tests."""

from percy import percy_snapshot

from .conftest import submit


class TestFormStructure:
    """Form renders correctly with all expected structural elements."""

    def test_page_loads(self, basic_page):
        assert basic_page.title() == "Basic Forms"

    def test_form_renders(self, basic_page):
        form = basic_page.locator("#widget-form")
        assert form.is_visible()
        percy_snapshot(basic_page, "Basic Forms - Default")

    def test_fieldset_wrappers(self, basic_page):
        fieldsets = basic_page.locator("#widget-form fieldset.fieldset")
        assert fieldsets.count() >= 5

    def test_labels_render(self, basic_page):
        labels = basic_page.locator("#widget-form .fieldset-legend")
        assert labels.count() >= 5

    def test_help_text_renders(self, basic_page):
        help_text = basic_page.locator("#id_name_helptext")
        assert help_text.is_visible()
        assert "name" in help_text.text_content().lower()

    def test_required_asterisk(self, basic_page):
        asterisks = basic_page.locator("#widget-form .text-error")
        assert asterisks.count() >= 1

    def test_submit_empty_shows_errors(self, basic_page):
        submit(basic_page)
        tooltips = basic_page.locator("#widget-form .tooltip-error")
        assert tooltips.count() >= 1
        percy_snapshot(basic_page, "Basic Forms - Errors")

    def test_error_has_role_alert(self, basic_page):
        submit(basic_page)
        alerts = basic_page.locator('#widget-form .tooltip-content[role="alert"]')
        assert alerts.count() >= 1

    def test_aria_invalid_set(self, basic_page):
        submit(basic_page)
        invalid = basic_page.locator('#widget-form [aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_novalidate_script_present(self, basic_page):
        """Inline script that disables native validation is present in rendered HTML."""
        script = basic_page.evaluate("""
            [...document.querySelectorAll('#widget-form script')].some(
                s => s.textContent.includes('noValidate')
            )
        """)
        assert script is True


class TestMorphInfrastructure:
    """Verify htmx, idiomorph, and morph swap work correctly."""

    def test_htmx_loaded(self, basic_page):
        assert basic_page.evaluate("typeof htmx") == "object"

    def test_idiomorph_loaded(self, basic_page):
        assert basic_page.evaluate("typeof Idiomorph") == "object"

    def test_morph_swap_works(self, basic_page):
        """After htmx POST, errors appear (form morphed in place)."""
        submit(basic_page)
        count = basic_page.evaluate(
            'document.querySelectorAll("#widget-form [aria-invalid]").length',
        )
        assert count >= 1

    def test_form_id_preserved(self, basic_page):
        submit(basic_page)
        assert basic_page.locator("#widget-form").count() == 1

    def test_csrf_token_exists(self, basic_page):
        submit(basic_page)
        token = basic_page.evaluate(
            "document.querySelector('#widget-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        assert token

    def test_no_duplicate_forms(self, basic_page):
        submit(basic_page)
        submit(basic_page)
        assert basic_page.locator("#widget-form").count() == 1

    def test_second_morph_clears_errors(self, basic_page):
        """Fill required fields and re-submit — errors should disappear."""
        submit(basic_page)
        assert basic_page.locator("#widget-form .tooltip-error").count() >= 1

        # Fill all required fields on the basic form
        basic_page.locator('input[name="name"]').fill("Alice")
        basic_page.locator('input[name="email"]').fill("a@b.com")
        basic_page.locator('textarea[name="message"]').fill("Hello")
        basic_page.locator('select[name="priority"]').select_option("low")
        basic_page.locator('input[name="agree"]').check()
        basic_page.evaluate("""
            document.querySelector('input[name="notify"][value="email"]').checked = true;
        """)
        submit(basic_page)
        # Name field errors should be gone
        name_errors = basic_page.locator("#id_name_errors")
        assert name_errors.count() == 0
