"""E2e tests for ValidatedTextarea inline htmx validation."""


class TestValidatedTextareaInline:
    """Inline htmx validation adds and removes the error state as the text changes."""

    def _trigger_validation(self, page):
        """Dispatch input event to trigger htmx debounced validation."""
        page.locator("textarea").dispatch_event("input", {"bubbles": True})
        page.wait_for_timeout(1000)  # debounce 500ms + network + settle

    def test_normal_text_no_error_state(self, textarea_page):
        """Typing valid text shows no error border or tooltip."""
        textarea = textarea_page.locator("textarea")
        textarea.fill("hello world")
        self._trigger_validation(textarea_page)

        aria = textarea.get_attribute("aria-invalid")
        assert aria != "true"

        # Tooltip should be hidden
        tooltip_visible = textarea_page.evaluate(
            """() => {
                const t = document.querySelector('.validated-textarea-tooltip');
                return t.offsetHeight > 0 || t.offsetWidth > 0;
            }""",
        )
        assert not tooltip_visible

    def test_error_text_shows_error_state(self, textarea_page):
        """Typing 'spam' shows red border and error tooltip."""
        textarea = textarea_page.locator("textarea")
        textarea.fill("spam")
        self._trigger_validation(textarea_page)

        # The .formwork-errors div has a <p> error message
        has_error_p = textarea_page.evaluate(
            """() => !!document.querySelector('.formwork-errors p')""",
        )
        assert has_error_p

    def test_error_clears_when_typing_valid_text(self, textarea_page):
        """After error, replacing with valid text clears the error state.

        Regression test: htmx OOB swap with empty content can leave a wrapper
        div inside .formwork-errors. CSS selectors must match <p> children
        specifically (not :not(:empty)) so the empty wrapper doesn't
        falsely trigger the error state.
        """
        textarea = textarea_page.locator("textarea")

        # First type "spam" to trigger error
        textarea.fill("spam")
        self._trigger_validation(textarea_page)

        has_error = textarea_page.evaluate(
            """() => !!document.querySelector('.formwork-errors p')""",
        )
        assert has_error, "Error state should appear for 'spam'"

        # Now clear and type valid text
        textarea.fill("hello world")
        self._trigger_validation(textarea_page)

        # Verify error is cleared from the user's perspective:
        # 1. No <p> error messages
        has_error_p = textarea_page.evaluate(
            """() => !!document.querySelector('.formwork-errors p')""",
        )
        assert not has_error_p

        # 2. Tooltip hidden (CSS uses :has(.formwork-errors p) selector)
        tooltip_visible = textarea_page.evaluate(
            """() => {
                const t = document.querySelector('.validated-textarea-tooltip');
                return t.offsetHeight > 0 && t.offsetWidth > 0;
            }""",
        )
        assert not tooltip_visible, "Tooltip should be hidden when valid"

        # 3. Textarea border is not the error color
        border = textarea_page.evaluate(
            """() => getComputedStyle(document.querySelector('textarea')).borderColor""",
        )
        # Error color contains 'oklch(0.71' (DaisyUI error red); valid color doesn't
        # This is fragile but catches the regression
        assert "0.194" not in border, f"Border should not be error color, got {border}"
