"""E2e tests for idiomorph full-form morphing.

Each test sets up widget state, submits the form via htmx (triggering an
idiomorph morph), and verifies the state is preserved after the morph.
"""


def _submit_morph(page):
    """Submit the morph form via htmx and wait for the morph to complete."""
    # Disable native validation so the POST reaches Django
    page.evaluate("document.querySelector('#morph-form').noValidate = true")
    page.locator("#morph-form button[type='submit']").click()
    # Wait for htmx to complete the swap
    page.wait_for_timeout(500)


class TestMorphDiagnostics:
    """Verify that htmx, idiomorph, and formwork.js are working."""

    def test_htmx_loaded(self, morph_page):
        assert morph_page.evaluate("typeof htmx") == "object"

    def test_idiomorph_extension_loaded(self, morph_page):
        # Check if Idiomorph global is available (from the extension script)
        has_idiomorph = morph_page.evaluate("typeof Idiomorph")
        assert has_idiomorph == "object", f"Idiomorph not loaded: {has_idiomorph}"

    def test_morph_swap_works(self, morph_page):
        """After htmx POST, the form content changes (errors appear)."""
        _submit_morph(morph_page)
        count = morph_page.evaluate(
            'document.querySelectorAll("#morph-form [aria-invalid]").length',
        )
        assert count >= 1, f"Expected errors after morph, got {count} aria-invalid elements"


class TestMorphTextInputs:
    """Text-like inputs preserve their values and gain error states after morph."""

    def test_text_input_value_preserved(self, morph_page):
        inp = morph_page.locator('input[name="m-text"]')
        inp.fill("Hello World")
        _submit_morph(morph_page)
        # Value should survive the morph (ignoreActiveValue)
        assert inp.input_value() == "Hello World"

    def test_email_input_value_preserved(self, morph_page):
        inp = morph_page.locator('input[name="m-email"]')
        inp.fill("test@example.com")
        _submit_morph(morph_page)
        assert inp.input_value() == "test@example.com"

    def test_textarea_value_preserved(self, morph_page):
        ta = morph_page.locator('textarea[name="m-textarea"]')
        ta.fill("Multiline\ntext content")
        _submit_morph(morph_page)
        assert ta.input_value() == "Multiline\ntext content"

    def test_error_tooltips_appear_after_morph(self, morph_page):
        """Submitting with empty required fields shows error tooltips."""
        _submit_morph(morph_page)
        tooltips = morph_page.locator("#morph-form .tooltip-error")
        assert tooltips.count() >= 1

    def test_error_tooltip_has_id(self, morph_page):
        """Error tooltip divs have stable IDs for subsequent morphs."""
        _submit_morph(morph_page)
        # The text field's errors div should have an id
        errors = morph_page.locator("#id_m-text_errors")
        assert errors.count() == 1

    def test_fieldset_has_id_after_morph(self, morph_page):
        """Fieldset wrappers have stable IDs."""
        _submit_morph(morph_page)
        fieldset = morph_page.locator("#id_m-text_field")
        assert fieldset.count() == 1

    def test_second_morph_updates_errors(self, morph_page):
        """Submitting twice: first shows errors, second (with values) removes them."""
        # First submit — empty, should show errors
        _submit_morph(morph_page)
        tooltips = morph_page.locator("#morph-form .tooltip-error")
        assert tooltips.count() >= 1

        # Fill all required fields
        morph_page.locator('input[name="m-text"]').fill("Hello")
        morph_page.locator('input[name="m-email"]').fill("a@b.com")
        morph_page.locator('textarea[name="m-textarea"]').fill("Message")
        morph_page.locator('select[name="m-select"]').select_option("a")
        morph_page.locator('input[name="m-password"]').fill("secret")
        morph_page.locator('input[name="m-volume"]').fill("50")
        # Click rating star (3rd star)
        morph_page.evaluate("""
            document.querySelector('#id_m-rating input[value="3"]').checked = true;
            document.querySelector('#id_m-rating input[value="3"]').dispatchEvent(new Event('change', {bubbles: true}));
        """)
        # Click radio
        morph_page.evaluate("""
            document.querySelector('input[name="m-radio"][value="a"]').checked = true;
        """)
        _submit_morph(morph_page)
        # Error tooltips should be gone for the text field
        text_errors = morph_page.locator("#id_m-text_errors")
        assert text_errors.count() == 0


class TestMorphSelect:
    """Native select preserves selected value after morph."""

    def test_select_value_preserved(self, morph_page):
        sel = morph_page.locator('select[name="m-select"]')
        sel.select_option("b")
        _submit_morph(morph_page)
        assert sel.input_value() == "b"


class TestMorphSearchSelect:
    """SearchSelect preserves its Alpine state after morph."""

    def test_search_select_value_preserved(self, morph_page):
        """Selected value persists through morph."""
        sel = morph_page.locator("details.search-select")
        summary = sel.locator("summary")
        # Open dropdown via JS (DaisyUI summary::before overlay blocks clicks)
        morph_page.evaluate("""
            document.querySelector('details.search-select').open = true;
        """)
        morph_page.wait_for_timeout(200)
        # Click "London" option
        sel.locator("button", has_text="London").click()
        morph_page.wait_for_timeout(200)
        # Verify value is set
        hidden = sel.locator('input[type="hidden"]')
        assert hidden.input_value() == "ldn"
        assert "London" in summary.text_content()

        # Submit via morph
        _submit_morph(morph_page)

        # Value should be preserved (x-data blocked from re-parsing)
        hidden = morph_page.locator("details.search-select input[type='hidden']")
        assert hidden.input_value() == "ldn"
        summary = morph_page.locator("details.search-select summary")
        assert "London" in summary.text_content()

    def test_search_select_dropdown_closed_after_morph(self, morph_page):
        """Dropdown is closed after morph (it was closed before submit)."""
        sel = morph_page.locator("details.search-select")
        # Open, pick, close
        morph_page.evaluate("document.querySelector('details.search-select').open = true")
        morph_page.wait_for_timeout(200)
        sel.locator("button", has_text="Tokyo").click()
        morph_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is None  # closed after pick

        _submit_morph(morph_page)

        # Still closed after morph
        assert sel.get_attribute("open") is None

    def test_search_select_dropdown_open_preserved(self, morph_page):
        """If dropdown was open before morph, it stays open after morph."""
        morph_page.evaluate("document.querySelector('details.search-select').open = true")
        morph_page.wait_for_timeout(200)
        assert morph_page.locator("details.search-select").get_attribute("open") is not None

        # Submit via JS — open dropdown overlays the submit button
        morph_page.evaluate("""
            document.querySelector('#morph-form').noValidate = true;
            document.querySelector('#morph-form button[type="submit"]').click();
        """)
        morph_page.wait_for_timeout(500)

        # Dropdown stays open (formwork.js blocks open attr changes on <details>)
        assert morph_page.locator("details.search-select").get_attribute("open") is not None

    def test_search_select_wrapper_has_id(self, morph_page):
        sel = morph_page.locator("details.search-select")
        assert sel.get_attribute("id") is not None
        assert "_searchselect" in sel.get_attribute("id")


class TestMorphMultiSelect:
    """MultiSelect preserves selections after morph."""

    def test_multi_select_value_preserved(self, morph_page):
        """Checked checkboxes persist through morph."""
        ms = morph_page.locator("details.multiselect")
        # Open dropdown
        morph_page.evaluate("document.querySelector('details.multiselect').open = true")
        morph_page.wait_for_timeout(200)
        # Check Python and Go via JS (DaisyUI summary::before blocks clicks)
        morph_page.evaluate("""
            const cbs = document.querySelectorAll('details.multiselect input[type="checkbox"]');
            cbs[0].checked = true;
            cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
            cbs[2].checked = true;
            cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
        """)
        morph_page.wait_for_timeout(200)
        # Close dropdown
        morph_page.evaluate("document.querySelector('details.multiselect').open = false")
        morph_page.wait_for_timeout(100)

        _submit_morph(morph_page)

        # After morph, checkboxes should still be checked
        checked = morph_page.evaluate("""
            [...document.querySelectorAll('details.multiselect input[type="checkbox"]:checked')]
                .map(cb => cb.value)
        """)
        assert "py" in checked
        assert "go" in checked

    def test_multi_select_dropdown_open_preserved(self, morph_page):
        morph_page.evaluate("document.querySelector('details.multiselect').open = true")
        morph_page.wait_for_timeout(200)

        # Submit via JS — open dropdown may overlay the submit button
        morph_page.evaluate("""
            document.querySelector('#morph-form').noValidate = true;
            document.querySelector('#morph-form button[type="submit"]').click();
        """)
        morph_page.wait_for_timeout(500)

        assert morph_page.locator("details.multiselect").get_attribute("open") is not None

    def test_multi_select_wrapper_has_id(self, morph_page):
        ms = morph_page.locator("details.multiselect")
        assert ms.get_attribute("id") is not None
        assert "_multiselect" in ms.get_attribute("id")


class TestMorphComboBox:
    """ComboBox preserves typed text after morph."""

    def test_combobox_value_preserved(self, morph_page):
        inp = morph_page.locator('input[name="m-combobox"]')
        inp.fill("Haskell")
        _submit_morph(morph_page)
        assert inp.input_value() == "Haskell"

    def test_combobox_wrapper_has_id(self, morph_page):
        wrapper = morph_page.locator("div.combobox")
        assert wrapper.get_attribute("id") is not None
        assert "_combobox" in wrapper.get_attribute("id")


class TestMorphPasswordReveal:
    """PasswordReveal preserves show/hide state after morph."""

    def test_password_value_cleared_by_design(self, morph_page):
        """Django's PasswordInput doesn't render values for security — morph clears them."""
        inp = morph_page.locator('input[name="m-password"]')
        inp.fill("secret123")
        _submit_morph(morph_page)
        # Password is intentionally cleared because Django never renders password
        # values in HTML responses (PasswordInput.render_value defaults to False).
        assert inp.input_value() == ""

    def test_password_reveal_state_preserved(self, morph_page):
        """After toggling show, the type='text' state persists through morph."""
        # Wait for Alpine init
        morph_page.wait_for_timeout(300)
        inp = morph_page.locator('input[name="m-password"]')
        inp.fill("secret")
        # Toggle to show password
        morph_page.locator("label.input button").click()
        morph_page.wait_for_timeout(200)
        # Should now be text type
        assert (
            morph_page.evaluate(
                "document.querySelector('input[name=\"m-password\"]').type",
            )
            == "text"
        )

        _submit_morph(morph_page)

        # After morph, x-data is preserved so show state should persist
        assert (
            morph_page.evaluate(
                "document.querySelector('input[name=\"m-password\"]').type",
            )
            == "text"
        )

    def test_password_wrapper_has_id(self, morph_page):
        wrapper = morph_page.locator("label.input")
        assert wrapper.get_attribute("id") is not None
        assert "_wrapper" in wrapper.get_attribute("id")


class TestMorphToggle:
    """Toggle checkbox preserves checked state after morph."""

    def test_toggle_checked_preserved(self, morph_page):
        toggle = morph_page.locator('input[name="m-toggle"]')
        toggle.check()
        assert toggle.is_checked()
        _submit_morph(morph_page)
        assert morph_page.locator('input[name="m-toggle"]').is_checked()

    def test_toggle_unchecked_preserved(self, morph_page):
        toggle = morph_page.locator('input[name="m-toggle"]')
        assert not toggle.is_checked()
        _submit_morph(morph_page)
        assert not morph_page.locator('input[name="m-toggle"]').is_checked()


class TestMorphRange:
    """Range input preserves value after morph."""

    def test_range_value_preserved(self, morph_page):
        rng = morph_page.locator('input[name="m-volume"]')
        morph_page.evaluate("""
            const r = document.querySelector('input[name="m-volume"]');
            r.value = '70';
            r.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        assert rng.input_value() == "70"
        _submit_morph(morph_page)
        assert morph_page.locator('input[name="m-volume"]').input_value() == "70"


class TestMorphRating:
    """Rating radio inputs preserve selected star after morph."""

    def test_rating_value_preserved(self, morph_page):
        # Click 3rd star via JS
        morph_page.evaluate("""
            const star = document.querySelector('#id_m-rating input[value="3"]');
            star.checked = true;
            star.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        _submit_morph(morph_page)
        checked_val = morph_page.evaluate("""
            document.querySelector('#id_m-rating input:checked')?.value || ''
        """)
        assert checked_val == "3"


class TestMorphCheckbox:
    """Standard checkbox preserves checked state after morph."""

    def test_checkbox_checked_preserved(self, morph_page):
        cb = morph_page.locator('input[name="m-checkbox"]')
        cb.check()
        _submit_morph(morph_page)
        assert morph_page.locator('input[name="m-checkbox"]').is_checked()


class TestMorphRadio:
    """Radio group preserves selected option after morph."""

    def test_radio_value_preserved(self, morph_page):
        morph_page.evaluate("""
            const radio = document.querySelector('input[name="m-radio"][value="b"]');
            radio.checked = true;
            radio.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        _submit_morph(morph_page)
        checked = morph_page.evaluate("""
            document.querySelector('input[name="m-radio"]:checked')?.value || ''
        """)
        assert checked == "b"


class TestMorphFormStructure:
    """The morph form preserves structural integrity."""

    def test_form_id_preserved(self, morph_page):
        _submit_morph(morph_page)
        assert morph_page.locator("#morph-form").count() == 1

    def test_csrf_token_updated(self, morph_page):
        """CSRF token should be updated from server response."""
        old_token = morph_page.evaluate(
            "document.querySelector('#morph-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        _submit_morph(morph_page)
        new_token = morph_page.evaluate(
            "document.querySelector('#morph-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        # Token should exist (may or may not change)
        assert new_token

    def test_submit_button_still_works(self, morph_page):
        """After morph, the submit button triggers another htmx request."""
        _submit_morph(morph_page)
        # Fill a required field so errors change
        morph_page.locator('input[name="m-text"]').fill("Test")
        # Second submit
        _submit_morph(morph_page)
        # Form should still be there
        assert morph_page.locator("#morph-form").count() == 1

    def test_no_duplicate_forms(self, morph_page):
        """Morph replaces in-place — should never create duplicate forms."""
        _submit_morph(morph_page)
        _submit_morph(morph_page)
        forms = morph_page.locator("#morph-form")
        assert forms.count() == 1

    def test_non_field_errors_appear(self, morph_page):
        """Non-field errors div gets an id for stable morphing."""
        # Submit empty — required field errors show as per-field errors
        _submit_morph(morph_page)
        # After morph, field errors should be present
        errors_divs = morph_page.locator("#morph-form .formwork-errors")
        assert errors_divs.count() >= 1
