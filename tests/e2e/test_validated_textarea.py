"""E2e tests for ValidatedTextarea inline htmx validation."""


class TestValidatedTextareaInline:
    """Inline htmx validation adds and removes the error state as the text changes."""

    def _fill_and_validate(self, page, text):
        """Fill the textarea and wait for the debounced htmx validation swap."""
        # Register the flag before fill() fires the input event so the
        # after:swap from the 500ms-debounced request cannot be missed.
        page.evaluate(
            """() => {
                window.__fwValidated = false;
                document.querySelector('textarea')
                    .addEventListener('htmx:after:swap', () => { window.__fwValidated = true; }, {once: true});
            }""",
        )
        page.locator("textarea").fill(text)
        page.wait_for_function("window.__fwValidated === true")

    def test_normal_text_no_error_state(self, textarea_page):
        """Typing valid text shows no error border or tooltip."""
        textarea = textarea_page.locator("textarea")
        self._fill_and_validate(textarea_page, "hello world")

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
        self._fill_and_validate(textarea_page, "spam")

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
        # First type "spam" to trigger error
        self._fill_and_validate(textarea_page, "spam")

        has_error = textarea_page.evaluate(
            """() => !!document.querySelector('.formwork-errors p')""",
        )
        assert has_error, "Error state should appear for 'spam'"

        # Now clear and type valid text
        self._fill_and_validate(textarea_page, "hello world")

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
