"""E2e tests for ValidatedTextarea with htmx validation."""

from percy import percy_snapshot
from playwright.sync_api import expect

from .conftest import submit


class TestValidatedTextarea:
    """ValidatedTextarea with htmx validation, mark highlights, and error tooltip."""

    def _trigger_validation(self, page, text):
        """Trigger htmx validation POST via fetch."""
        page.evaluate(
            """(text) => {
            const textarea = document.querySelector('textarea[name="bio"]');
            textarea.value = text;
            const url = textarea.getAttribute('hx-post');
            const highlightsId = textarea.getAttribute('hx-target');
            const params = new URLSearchParams();
            params.append('text', text);
            params.append('field_name', 'bio');
            params.append('errors_id', textarea.id + '_errors');
            fetch(url, {method: 'POST', body: params})
                .then(r => r.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
                    const oob = doc.querySelector('[hx-swap-oob]');
                    const errorsTarget = document.getElementById(textarea.id + '_errors');
                    if (oob && errorsTarget) {
                        errorsTarget.innerHTML = oob.innerHTML;
                        oob.remove();
                    }
                    const target = document.querySelector(highlightsId);
                    const remaining = doc.body.firstChild;
                    target.innerHTML = remaining.innerHTML;
                });
        }""",
            text,
        )

    def test_renders(self, textarea_page):
        wrapper = textarea_page.locator(".validated-textarea")
        assert wrapper.is_visible()
        percy_snapshot(textarea_page, "ValidatedTextarea - Default")

    def test_has_overlay(self, textarea_page):
        highlights = textarea_page.locator(".validated-textarea-highlights")
        assert highlights.count() == 1

    def test_has_errors_tooltip(self, textarea_page):
        tooltip = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
        assert tooltip.count() == 1

    def test_clean_text_no_marks(self, textarea_page):
        self._trigger_validation(textarea_page, "Hello world")
        textarea_page.wait_for_timeout(500)
        marks = textarea_page.locator(".validated-textarea-highlights mark")
        assert marks.count() == 0

    def test_bad_text_shows_marks(self, textarea_page):
        self._trigger_validation(textarea_page, "This has a badword in it")
        textarea_page.wait_for_timeout(500)
        marks = textarea_page.locator(".validated-textarea-highlights mark")
        expect(marks).to_have_count(1, timeout=3000)
        assert marks.first.text_content() == "badword"
        percy_snapshot(textarea_page, "ValidatedTextarea - Badword Highlighted")

    def test_error_messages_appear(self, textarea_page):
        self._trigger_validation(textarea_page, "badword and spam here")
        textarea_page.wait_for_timeout(500)
        errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
        messages = errors.locator("p")
        expect(messages).to_have_count(2, timeout=3000)
        percy_snapshot(textarea_page, "ValidatedTextarea - Multiple Errors")

    def test_errors_clear(self, textarea_page):
        self._trigger_validation(textarea_page, "badword")
        textarea_page.wait_for_timeout(500)
        expect(textarea_page.locator(".validated-textarea-highlights mark")).to_have_count(
            1,
            timeout=3000,
        )
        self._trigger_validation(textarea_page, "All clean now")
        textarea_page.wait_for_timeout(500)
        expect(textarea_page.locator(".validated-textarea-highlights mark")).to_have_count(
            0,
            timeout=3000,
        )
        percy_snapshot(textarea_page, "ValidatedTextarea - Errors Cleared")

    def test_errors_clear_on_input(self, textarea_page):
        """Error messages clear immediately when user starts typing."""
        self._trigger_validation(textarea_page, "badword")
        textarea_page.wait_for_timeout(500)
        errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
        expect(errors.locator("p")).to_have_count(1, timeout=3000)
        # Simulate typing — fires @input which clears errors immediately
        textarea_page.evaluate("""
            const ta = document.querySelector('textarea[name="bio"]');
            ta.value = 'fixing the text';
            ta.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        textarea_page.wait_for_timeout(100)
        # Errors should be cleared immediately (not waiting for htmx debounce)
        assert errors.inner_html().strip() == ""

    def test_has_help_text(self, textarea_page):
        """Help text mentions the invalid words."""
        label = textarea_page.locator("fieldset:has(textarea) .label")
        text = label.text_content()
        assert "badword" in text
        assert "spam" in text

    def test_morph_preserves_value(self, textarea_page):
        ta = textarea_page.locator('textarea[name="bio"]')
        ta.fill("Some bio text")
        submit(textarea_page)
        assert ta.input_value() == "Some bio text"

    def test_aria_invalid_clears_when_errors_resolve(self, textarea_page):
        """aria-invalid is set when errors appear and cleared when they resolve."""
        ta = textarea_page.locator('textarea[name="bio"]')

        # Type "spam" and trigger htmx validation via input event.
        textarea_page.evaluate("""
            const ta = document.querySelector('textarea[name="bio"]');
            ta.value = 'spam';
            ta.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        # Wait for htmx debounce (500ms) + round trip + settle.
        textarea_page.wait_for_timeout(1500)

        # Errors should be visible and aria-invalid="true" set on textarea.
        errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
        expect(errors.locator("p")).to_have_count(1, timeout=3000)
        expect(ta).to_have_attribute("aria-invalid", "true")

        # Clear the textarea and trigger validation again.
        textarea_page.evaluate("""
            const ta = document.querySelector('textarea[name="bio"]');
            ta.value = '';
            ta.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        # Wait for htmx debounce (500ms) + round trip + settle.
        textarea_page.wait_for_timeout(1500)

        # Errors should be gone and aria-invalid="false" on textarea.
        expect(errors.locator("p")).to_have_count(0, timeout=3000)
        expect(ta).to_have_attribute("aria-invalid", "false")
        percy_snapshot(textarea_page, "ValidatedTextarea - aria-invalid Cleared")
