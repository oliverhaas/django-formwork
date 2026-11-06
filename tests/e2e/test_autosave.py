"""E2e tests for the Auto-Save Form page.

Tests auto-save via htmx morph, caret/selection preservation, required error
suppression, explicit submit behavior, and the dropdown state a morph keeps.
"""

from contextlib import contextmanager

import pytest
from playwright.sync_api import expect

from .conftest import submit


@contextmanager
def _morph(page):
    """Wait for the auto-save morph that the block triggers."""
    page.evaluate(
        """() => {
            window.__fwMorphed = false;
            document.querySelector('form[hx-post]')
                .addEventListener('htmx:after:swap', () => { window.__fwMorphed = true; }, {once: true});
        }""",
    )
    yield
    page.wait_for_function("window.__fwMorphed === true")


def _open_city(page):
    page.locator("summary#id_city").click()
    panel = page.locator("#id_city_wrapper [x-ref=panel]")
    expect(panel).to_be_visible()
    return panel


def _wait_for_autosave(page, timeout=1000):
    """Wait for htmx auto-save debounce (500ms) + network + morph."""
    page.wait_for_timeout(timeout)


def _trigger_input_event(page, selector):
    """Dispatch an input event to trigger htmx auto-save."""
    page.evaluate(
        f"""document.querySelector('{selector}')"""
        """.dispatchEvent(new Event('input', {bubbles: true}))""",
    )


class TestAutoSaveStructure:
    """Page and form structure."""

    def test_page_loads(self, autosave_page):
        assert autosave_page.title() == "Auto-Save Form"

    def test_form_renders(self, autosave_page):
        form = autosave_page.locator("#autosave-form")
        assert form.is_visible()

    def test_form_has_autosave_trigger(self, autosave_page):
        form = autosave_page.locator("#autosave-form")
        trigger = form.get_attribute("hx-trigger")
        assert "input" in trigger
        assert "change" in trigger

    def test_form_has_novalidate(self, autosave_page):
        """Native browser validation is disabled."""
        form = autosave_page.locator("#autosave-form")
        assert form.get_attribute("novalidate") is not None

    def test_no_html_required_attribute(self, autosave_page):
        """Required fields should NOT have the HTML required attribute."""
        name_input = autosave_page.locator('input[name="name"]')
        assert name_input.get_attribute("required") is None
        email_input = autosave_page.locator('input[name="email"]')
        assert email_input.get_attribute("required") is None

    def test_required_fields_show_the_asterisk(self, autosave_page):
        """Required fields keep the asterisk despite no HTML required."""
        expect(autosave_page.locator("#id_name_label .text-error")).to_have_text("*")
        expect(autosave_page.locator("#id_message_label .text-error")).to_have_count(0)


class TestAutoSaveBehavior:
    """Auto-save triggers, required error suppression, and format errors."""

    def test_typing_triggers_autosave(self, autosave_page):
        """Typing in a field triggers auto-save after debounce."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Alice")
        _wait_for_autosave(autosave_page)
        # After morph, value should be preserved
        assert inp.input_value() == "Alice"

    def test_empty_required_no_error(self, autosave_page):
        """Auto-save suppresses required errors for empty fields."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Alice")
        _wait_for_autosave(autosave_page)
        # Email is empty but no error should show
        email_errors = autosave_page.locator("#id_email_error")
        assert email_errors.count() == 0

    def test_invalid_email_shows_error(self, autosave_page):
        """Format errors are shown during auto-save."""
        email = autosave_page.locator('input[name="email"]')
        email.fill("not-an-email")
        _wait_for_autosave(autosave_page)
        email_error = autosave_page.locator("#id_email_error")
        assert email_error.count() == 1

    def test_valid_email_clears_error(self, autosave_page):
        """Fixing a format error clears the error on next auto-save."""
        email = autosave_page.locator('input[name="email"]')
        email.fill("bad")
        _wait_for_autosave(autosave_page)
        assert autosave_page.locator("#id_email_error").count() == 1
        email.fill("good@example.com")
        _wait_for_autosave(autosave_page)
        assert autosave_page.locator("#id_email_error").count() == 0


class TestMorphPreservation:
    """Values and state preserved across auto-save morphs."""

    def test_text_input_value_preserved(self, autosave_page):
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Test Name")
        _wait_for_autosave(autosave_page)
        assert inp.input_value() == "Test Name"

    def test_email_value_preserved(self, autosave_page):
        email = autosave_page.locator('input[name="email"]')
        email.fill("test@example.com")
        _wait_for_autosave(autosave_page)
        assert email.input_value() == "test@example.com"

    def test_textarea_value_preserved(self, autosave_page):
        ta = autosave_page.locator('textarea[name="message"]')
        ta.fill("Hello\nWorld")
        _wait_for_autosave(autosave_page)
        assert ta.input_value() == "Hello\nWorld"

    def test_select_value_preserved(self, autosave_page):
        sel = autosave_page.locator('select[name="priority"]')
        sel.select_option("high")
        _wait_for_autosave(autosave_page)
        assert sel.input_value() == "high"

    def test_radio_value_preserved(self, autosave_page):
        radio = autosave_page.locator('input[name="notify"][value="sms"]')
        radio.click(force=True)
        _wait_for_autosave(autosave_page)
        checked = autosave_page.evaluate(
            'document.querySelector(\'input[name="notify"]:checked\')?.value || ""',
        )
        assert checked == "sms"

    def test_checkbox_state_preserved(self, autosave_page):
        cb = autosave_page.locator('input[name="agree"]')
        cb.check()
        _wait_for_autosave(autosave_page)
        assert autosave_page.locator('input[name="agree"]').is_checked()

    def test_caret_position_preserved_in_text(self, autosave_page):
        """Caret position in focused text input survives auto-save morph."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Hello World")
        _wait_for_autosave(autosave_page)
        # Position caret at index 5 (between "Hello" and " World")
        autosave_page.evaluate("""
            const el = document.querySelector('input[name="name"]');
            el.focus();
            el.setSelectionRange(5, 5);
        """)
        # Dispatch input event to trigger another auto-save morph
        _trigger_input_event(autosave_page, 'input[name="name"]')
        _wait_for_autosave(autosave_page)
        pos = autosave_page.evaluate(
            "document.querySelector('input[name=\"name\"]').selectionStart",
        )
        assert pos == 5

    def test_caret_position_preserved_in_textarea(self, autosave_page):
        """Caret position in focused textarea survives auto-save morph."""
        ta = autosave_page.locator('textarea[name="message"]')
        ta.fill("Line one\nLine two")
        _wait_for_autosave(autosave_page)
        # Position caret at index 4 (in "Line")
        autosave_page.evaluate("""
            const el = document.querySelector('textarea[name="message"]');
            el.focus();
            el.setSelectionRange(4, 4);
        """)
        _trigger_input_event(autosave_page, 'textarea[name="message"]')
        _wait_for_autosave(autosave_page)
        pos = autosave_page.evaluate(
            "document.querySelector('textarea[name=\"message\"]').selectionStart",
        )
        assert pos == 4

    def test_focused_input_value_not_overwritten(self, autosave_page):
        """Focused input keeps its current value during morph (ignoreActiveValue)."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Original")
        _wait_for_autosave(autosave_page)
        # Now type more while the input is focused
        inp.focus()
        inp.press_sequentially("Extra", delay=50)
        # The server-side value is "Original" but the focused input has "OriginalExtra"
        # Trigger morph: the formwork-morph extension preserves the focused input value
        _trigger_input_event(autosave_page, 'input[name="name"]')
        _wait_for_autosave(autosave_page)
        assert inp.input_value() == "OriginalExtra"


class TestExplicitSubmit:
    """Explicit submit via Submit button."""

    def test_submit_valid_no_errors(self, autosave_page):
        """Submit with all required fields produces no validation errors."""
        autosave_page.locator('input[name="name"]').fill("Alice")
        autosave_page.locator('input[name="email"]').fill("alice@example.com")
        autosave_page.locator('input[name="agree"]').check()
        # Wait for auto-save morphs to settle before explicit submit
        _wait_for_autosave(autosave_page)
        submit(autosave_page)
        errors = autosave_page.locator("#autosave-form details.formwork-errors")
        assert errors.count() == 0

    def test_submit_missing_required_shows_errors(self, autosave_page):
        """Submit with empty required fields shows required errors."""
        # Clear fields to ensure they're empty
        autosave_page.locator('input[name="name"]').fill("")
        autosave_page.locator('input[name="email"]').fill("")
        autosave_page.locator('input[name="agree"]').uncheck(force=True)
        _wait_for_autosave(autosave_page)
        submit(autosave_page)
        errors = autosave_page.locator("#autosave-form details.formwork-errors")
        assert errors.count() >= 1

    def test_submit_preserves_values_on_error(self, autosave_page):
        """Submitted values are preserved in the form after validation errors."""
        autosave_page.locator('input[name="name"]').fill("Bob")
        autosave_page.locator('input[name="email"]').fill("")
        autosave_page.locator('input[name="agree"]').uncheck(force=True)
        _wait_for_autosave(autosave_page)
        submit(autosave_page)
        assert autosave_page.locator('input[name="name"]').input_value() == "Bob"


class TestPersistenceAndReset:
    """Data persistence, reset, and delete."""

    def test_data_persists_after_reload(self, autosave_page):
        """Auto-saved data is loaded from DB on page reload."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("Persistent")
        _wait_for_autosave(autosave_page)
        autosave_page.reload()
        autosave_page.wait_for_timeout(300)
        assert autosave_page.locator('input[name="name"]').input_value() == "Persistent"

    def test_select_persists_after_reload(self, autosave_page):
        """Auto-saved select value is loaded from DB on page reload."""
        sel = autosave_page.locator('select[name="priority"]')
        sel.select_option("high")
        _wait_for_autosave(autosave_page)
        autosave_page.reload()
        autosave_page.wait_for_timeout(300)
        assert autosave_page.locator('select[name="priority"]').input_value() == "high"

    def test_delete_clears_data(self, autosave_page):
        """Delete button removes saved data and resets the form."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("ToDelete")
        _wait_for_autosave(autosave_page)
        # The button only renders once the auto-save morph marked the form as saved.
        delete_btn = autosave_page.locator('button:text("Delete")')
        expect(delete_btn).to_be_visible()
        delete_btn.click()
        expect(inp).to_have_value("")

    def test_reset_clears_to_defaults(self, autosave_page):
        """Reset button clears saved data but keeps the form."""
        inp = autosave_page.locator('input[name="name"]')
        inp.fill("ToReset")
        _wait_for_autosave(autosave_page)
        reset_btn = autosave_page.locator('button:text("Reset")')
        expect(reset_btn).to_be_visible()
        reset_btn.click()
        expect(inp).to_have_value("")
        expect(autosave_page.locator("#autosave-form")).to_be_visible()


def test_multiple_fields_persist_after_reload(autosave_page):
    """All auto-saved field types are restored from the DB on reload."""
    page = autosave_page
    page.locator('input[name="name"]').fill("Persisted User")
    page.locator('input[name="email"]').fill("persist@test.com")
    page.locator('select[name="priority"]').select_option("medium")
    page.locator('input[name="agree"]').check()
    _trigger_input_event(page, 'input[name="name"]')
    _wait_for_autosave(page, timeout=1500)

    page.reload()
    page.wait_for_timeout(500)

    assert page.locator('input[name="name"]').input_value() == "Persisted User"
    assert page.locator('input[name="email"]').input_value() == "persist@test.com"
    assert page.locator('select[name="priority"]').input_value() == "medium"
    assert page.locator('input[name="agree"]').is_checked()


def test_picked_option_keeps_check_mark_after_autosave(autosave_dropdowns_page):
    page = autosave_dropdowns_page
    panel = _open_city(page)

    with _morph(page):
        panel.locator('button[data-value="ldn"]').click()

    expect(page.locator('#id_city_wrapper button[data-value="ldn"]')).to_have_attribute("aria-selected", "true")
    expect(page.locator('#id_city_wrapper button[data-value="par"]')).to_have_attribute("aria-selected", "false")


def test_open_dropdown_keeps_search_filter_through_autosave(autosave_dropdowns_page):
    page = autosave_dropdowns_page
    panel = _open_city(page)
    search = panel.locator("input[type=search]")

    with _morph(page):
        search.press_sequentially("par")

    expect(panel).to_be_visible()
    expect(search).to_have_value("par")
    expect(panel.locator("li[role=option]:visible")).to_have_count(1)
    expect(panel.locator("li[role=option]:visible")).to_have_text("Paris")
    expect(panel.get_by_role("button", name="Clear search")).to_be_visible()


def test_pick_made_during_a_save_survives_the_older_response(autosave_dropdowns_page):
    page = autosave_dropdowns_page
    held = []

    def hold(route):
        held.append(route)

    page.route("**/autosave-dropdowns/", hold)

    with page.expect_request(lambda request: request.method == "POST"):
        _open_city(page).locator('button[data-value="ldn"]').click()
    _open_city(page).locator('button[data-value="par"]').click()
    expect(page.locator("#id_city_value")).to_have_value("par")

    with _morph(page):
        held.pop(0).continue_()

    expect(page.locator("#id_city_value")).to_have_value("par")
    expect(page.locator("summary#id_city span[x-text]")).to_have_text("Paris")


def test_server_answer_to_the_pick_wins_over_the_pick(autosave_dropdowns_page):
    page = autosave_dropdowns_page
    page.route(
        "**/autosave-dropdowns/",
        lambda route: route.continue_(
            post_data=route.request.post_data.replace('name="city"\r\n\r\nldn', 'name="city"\r\n\r\ntyo'),
        ),
    )

    with _morph(page):
        _open_city(page).locator('button[data-value="ldn"]').click()

    expect(page.locator("#id_city_value")).to_have_value("tyo")
    expect(page.locator("summary#id_city span[x-text]")).to_have_text("Tokyo")


@pytest.mark.screenshot
def test_autosave_filled_form_screenshot(autosave_page, assert_screenshot):
    """Visual snapshot: form after filling every field, auto-saved field by field."""
    page = autosave_page

    page.locator('input[name="name"]').fill("Jane Doe")
    _trigger_input_event(page, 'input[name="name"]')
    _wait_for_autosave(page)

    page.locator('input[name="email"]').fill("jane@example.com")
    _trigger_input_event(page, 'input[name="email"]')
    _wait_for_autosave(page)

    page.locator('textarea[name="message"]').fill("Hello,\nThis is a multi-line message.")
    _trigger_input_event(page, 'textarea[name="message"]')
    _wait_for_autosave(page)

    page.locator('select[name="priority"]').select_option("high")
    page.evaluate(
        """document.querySelector('select[name="priority"]')"""
        """.dispatchEvent(new Event('change', {bubbles: true}))""",
    )
    _wait_for_autosave(page)

    page.locator('input[name="notify"][value="sms"]').click(force=True)
    _wait_for_autosave(page)

    page.locator('input[name="agree"]').check()
    _wait_for_autosave(page)

    assert_screenshot(page.locator("#autosave-form"), "autosave-form-filled.png")


@pytest.mark.screenshot
def test_autosave_error_cycle_screenshot(autosave_page, assert_screenshot):
    """Visual snapshot: email format error appears on auto-save, then clears."""
    page = autosave_page

    page.locator('input[name="email"]').fill("not-valid")
    _trigger_input_event(page, 'input[name="email"]')
    _wait_for_autosave(page)
    assert_screenshot(page.locator("#id_email_field"), "autosave-email-error.png")

    page.locator('input[name="email"]').fill("fixed@example.com")
    _trigger_input_event(page, 'input[name="email"]')
    _wait_for_autosave(page)
    assert_screenshot(page.locator("#id_email_field"), "autosave-email-fixed.png")
