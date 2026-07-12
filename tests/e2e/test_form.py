"""Form structure and morph infrastructure tests."""

from playwright.sync_api import expect

from .conftest import submit


class TestFormStructure:
    """Form renders correctly with all expected structural elements."""

    def test_page_loads(self, basic_page):
        assert basic_page.title() == "Basic Form"

    def test_form_renders(self, basic_page):
        form = basic_page.locator("#basic-form")
        assert form.is_visible()

    def test_fieldset_wrappers(self, basic_page):
        fieldsets = basic_page.locator("#basic-form fieldset.fieldset")
        assert fieldsets.count() >= 5

    def test_labels_render(self, basic_page):
        labels = basic_page.locator("#basic-form .fieldset-legend")
        assert labels.count() >= 5

    def test_help_text_renders(self, basic_page):
        help_text = basic_page.locator("#id_name_helptext")
        assert help_text.is_visible()
        assert "textinput" in help_text.text_content().lower()

    def test_required_asterisk(self, basic_page):
        asterisks = basic_page.locator("#basic-form .text-error")
        assert asterisks.count() >= 1

    def test_submit_empty_shows_errors(self, basic_page):
        submit(basic_page)
        tooltips = basic_page.locator("#basic-form .tooltip-error")
        assert tooltips.count() >= 1

    def test_error_has_role_alert(self, basic_page):
        submit(basic_page)
        alerts = basic_page.locator('#basic-form .tooltip-content[role="alert"]')
        assert alerts.count() >= 1

    def test_aria_invalid_set(self, basic_page):
        submit(basic_page)
        invalid = basic_page.locator('#basic-form [aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_novalidate_set_on_form_with_errors(self, basic_page):
        """formwork.js disables native validation after errors appear via morph."""
        submit(basic_page)
        no_validate = basic_page.evaluate(
            "document.querySelector('#basic-form').noValidate",
        )
        assert no_validate is True


class TestHelpTextToggle:
    """Help text truncates to one line, with a [more]/[less] toggle when it overflows."""

    def _narrow(self, basic_page):
        basic_page.set_viewport_size({"width": 480, "height": 720})
        basic_page.reload()
        basic_page.wait_for_load_state("domcontentloaded")
        basic_page.wait_for_timeout(300)

    def test_toggle_hidden_when_text_fits(self, basic_page):
        """The "message" field's help text fits on one line, so the toggle hides after measuring."""
        toggle = basic_page.locator("#id_message_helptext button")
        expect(toggle).not_to_be_visible()

    def test_truncate_survives_morph(self, basic_page):
        """Server HTML carries truncate statically, so a morph cannot wipe it."""
        submit(basic_page)
        helptext = basic_page.locator("#id_name_helptext span")
        assert "truncate" in (helptext.get_attribute("class") or "")

    def test_toggle_shown_when_text_overflows(self, basic_page):
        """The "agree" field's help text overflows, so the toggle is shown."""
        self._narrow(basic_page)
        toggle = basic_page.locator("#id_agree_helptext button")
        assert toggle.is_visible()
        assert toggle.text_content() == "[more]"

    def test_click_expands_and_collapses(self, basic_page):
        self._narrow(basic_page)
        helptext = basic_page.locator("#id_agree_helptext span")
        toggle = basic_page.locator("#id_agree_helptext button")

        assert "truncate" in (helptext.get_attribute("class") or "")

        toggle.click()
        assert toggle.text_content() == "[less]"
        assert "truncate" not in (helptext.get_attribute("class") or "")

        toggle.click()
        assert toggle.text_content() == "[more]"
        assert "truncate" in (helptext.get_attribute("class") or "")

    def test_expanded_icon_and_button_align_to_edges(self, basic_page):
        """When expanded, the icon top-aligns and the toggle bottom-aligns to the row."""
        self._narrow(basic_page)
        toggle = basic_page.locator("#id_agree_helptext button")
        toggle.click()

        icon_box = basic_page.locator("#id_agree_helptext i").bounding_box()
        toggle_box = toggle.bounding_box()
        row_box = basic_page.locator("#id_agree_helptext").bounding_box()

        assert abs(icon_box["y"] - row_box["y"]) <= 3
        row_bottom = row_box["y"] + row_box["height"]
        toggle_bottom = toggle_box["y"] + toggle_box["height"]
        assert abs(toggle_bottom - row_bottom) <= 3


class TestMorphInfrastructure:
    """Verify htmx 4 morph swap and the formwork-morph extension are registered."""

    def test_htmx_loaded(self, basic_page):
        assert basic_page.evaluate("typeof htmx") == "object"

    def test_formwork_morph_extension_registered(self, basic_page):
        assert (
            basic_page.evaluate(
                "htmx.config.morphIgnore && htmx.config.morphIgnore.includes('x-data')",
            )
            is True
        )

    def test_morph_swap_works(self, basic_page):
        """After htmx POST, errors appear (form morphed in place)."""
        submit(basic_page)
        count = basic_page.evaluate(
            'document.querySelectorAll("#basic-form [aria-invalid]").length',
        )
        assert count >= 1

    def test_form_id_preserved(self, basic_page):
        submit(basic_page)
        assert basic_page.locator("#basic-form").count() == 1

    def test_csrf_token_exists(self, basic_page):
        submit(basic_page)
        token = basic_page.evaluate(
            "document.querySelector('#basic-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        assert token

    def test_no_duplicate_forms(self, basic_page):
        submit(basic_page)
        submit(basic_page)
        assert basic_page.locator("#basic-form").count() == 1

    def test_second_morph_clears_errors(self, basic_page):
        """Fill required fields and re-submit — errors should disappear."""
        submit(basic_page)
        assert basic_page.locator("#basic-form .tooltip-error").count() >= 1

        # Fill all required fields on the basic form
        basic_page.locator('input[name="name"]').fill("Alice")
        basic_page.locator('input[name="email"]').fill("a@b.com")
        basic_page.locator('input[name="agree"]').check()
        submit(basic_page)
        # Name field errors should be gone
        name_errors = basic_page.locator("#id_name_error")
        assert name_errors.count() == 0
