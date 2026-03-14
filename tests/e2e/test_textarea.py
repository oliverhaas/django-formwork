"""E2e tests for ValidatedTextarea with htmx validation."""

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

    def test_error_messages_appear(self, textarea_page):
        self._trigger_validation(textarea_page, "badword and spam here")
        textarea_page.wait_for_timeout(500)
        errors = textarea_page.locator(".validated-textarea-tooltip .formwork-errors")
        messages = errors.locator("p")
        expect(messages).to_have_count(2, timeout=3000)

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

    def test_morph_preserves_value(self, textarea_page):
        ta = textarea_page.locator('textarea[name="bio"]')
        ta.fill("Some bio text")
        submit(textarea_page)
        assert ta.input_value() == "Some bio text"
