"""Form structure and morph infrastructure tests."""

from .conftest import submit


class TestFormStructure:
    """Form renders correctly with all expected structural elements."""

    def test_page_loads(self, widget_page):
        assert widget_page.title() == "e2e test"

    def test_form_renders(self, widget_page):
        form = widget_page.locator("#widget-form")
        assert form.is_visible()

    def test_fieldset_wrappers(self, widget_page):
        fieldsets = widget_page.locator("#widget-form fieldset.fieldset")
        # At least one fieldset per visible field
        assert fieldsets.count() >= 10

    def test_labels_render(self, widget_page):
        labels = widget_page.locator("#widget-form .fieldset-legend")
        assert labels.count() >= 10

    def test_help_text_renders(self, widget_page):
        help_text = widget_page.locator("#id_text_helptext")
        assert help_text.is_visible()
        assert "text" in help_text.text_content().lower()

    def test_required_asterisk(self, widget_page):
        asterisks = widget_page.locator("#widget-form .text-error")
        assert asterisks.count() >= 1

    def test_submit_empty_shows_errors(self, widget_page):
        submit(widget_page)
        tooltips = widget_page.locator("#widget-form .tooltip-error")
        assert tooltips.count() >= 1

    def test_error_has_role_alert(self, widget_page):
        submit(widget_page)
        alerts = widget_page.locator('#widget-form .tooltip-content[role="alert"]')
        assert alerts.count() >= 1

    def test_aria_invalid_set(self, widget_page):
        submit(widget_page)
        invalid = widget_page.locator('#widget-form [aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_novalidate_script_present(self, widget_page):
        """Inline script that disables native validation is present in rendered HTML."""
        script = widget_page.evaluate("""
            [...document.querySelectorAll('#widget-form script')].some(
                s => s.textContent.includes('noValidate')
            )
        """)
        assert script is True


class TestMorphInfrastructure:
    """Verify htmx, idiomorph, and morph swap work correctly."""

    def test_htmx_loaded(self, widget_page):
        assert widget_page.evaluate("typeof htmx") == "object"

    def test_idiomorph_loaded(self, widget_page):
        assert widget_page.evaluate("typeof Idiomorph") == "object"

    def test_morph_swap_works(self, widget_page):
        """After htmx POST, errors appear (form morphed in place)."""
        submit(widget_page)
        count = widget_page.evaluate(
            'document.querySelectorAll("#widget-form [aria-invalid]").length',
        )
        assert count >= 1

    def test_form_id_preserved(self, widget_page):
        submit(widget_page)
        assert widget_page.locator("#widget-form").count() == 1

    def test_csrf_token_exists(self, widget_page):
        submit(widget_page)
        token = widget_page.evaluate(
            "document.querySelector('#widget-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        assert token

    def test_no_duplicate_forms(self, widget_page):
        submit(widget_page)
        submit(widget_page)
        assert widget_page.locator("#widget-form").count() == 1

    def test_second_morph_clears_errors(self, widget_page):
        """Fill required fields and re-submit — errors should disappear."""
        submit(widget_page)
        assert widget_page.locator("#widget-form .tooltip-error").count() >= 1

        # Fill all required fields
        widget_page.locator('input[name="text"]').fill("Hello")
        widget_page.locator('input[name="email"]').fill("a@b.com")
        widget_page.locator('textarea[name="textarea"]').fill("Message")
        widget_page.locator('select[name="select"]').select_option("a")
        widget_page.locator('input[name="password"]').fill("secret")
        widget_page.locator('input[name="volume"]').fill("50")
        widget_page.locator('input[name="checkbox"]').check()
        widget_page.evaluate("""
            document.querySelector('#id_rating input[value="3"]').checked = true;
            document.querySelector('#id_rating input[value="3"]').dispatchEvent(
                new Event('change', {bubbles: true})
            );
            document.querySelector('input[name="radio"][value="x"]').checked = true;
        """)
        submit(widget_page)
        # Text field errors should be gone
        text_errors = widget_page.locator("#id_text_errors")
        assert text_errors.count() == 0
