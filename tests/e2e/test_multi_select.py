"""E2e tests for MultiSelect widget: plain, with icons, and htmx."""

from percy import percy_snapshot
from playwright.sync_api import expect

from .conftest import submit


class TestMultiSelectPlain:
    """MultiSelect with static choices, no icons, no search."""

    def _get(self, page):
        return page.locator("details.dropdown.multiselect").first

    def test_renders(self, multi_select_page):
        multi = self._get(multi_select_page)
        assert multi.is_visible()
        percy_snapshot(multi_select_page, "MultiSelect - Default")

    def test_open_shows_checkboxes(self, multi_select_page):
        multi = self._get(multi_select_page)
        summary = multi.locator("summary")
        summary.click()
        multi_select_page.wait_for_timeout(100)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() >= 2
        percy_snapshot(multi_select_page, "MultiSelect Plain - Open")

    def test_select_multiple(self, multi_select_page):
        multi = self._get(multi_select_page)
        multi.locator("summary").click()
        multi_select_page.wait_for_timeout(100)
        multi_select_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.multiselect');
            ['py', 'go'].forEach(v => {
                const cb = dd.querySelector(`input[value="${v}"]`);
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""")
        multi_select_page.wait_for_timeout(100)
        assert multi.locator('input[value="py"]').is_checked()
        assert multi.locator('input[value="go"]').is_checked()

    def test_summary_shows_selection(self, multi_select_page):
        multi = self._get(multi_select_page)
        summary = multi.locator("summary")
        summary.click()
        multi_select_page.wait_for_timeout(100)
        multi_select_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.multiselect');
            const cb = dd.querySelector('input[value="py"]');
            cb.checked = true;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        multi_select_page.wait_for_timeout(100)
        summary_text = summary.text_content()
        assert "Python" in summary_text or "1" in summary_text

    def test_morph_preserves_values(self, multi_select_page):
        multi_select_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = true;
        """)
        multi_select_page.wait_for_timeout(200)
        multi_select_page.evaluate("""
            const dd = document.querySelector('details.dropdown.multiselect');
            const cbs = dd.querySelectorAll('input[type="checkbox"]');
            cbs[0].checked = true;
            cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
            cbs[2].checked = true;
            cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
        """)
        multi_select_page.wait_for_timeout(200)
        multi_select_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = false;
        """)
        multi_select_page.wait_for_timeout(100)
        submit(multi_select_page)
        checked = multi_select_page.evaluate("""
            [...document.querySelectorAll('details.dropdown.multiselect input[type="checkbox"]:checked')]
                .map(cb => cb.value)
        """)
        assert "py" in checked
        assert "go" in checked

    def test_morph_preserves_dropdown_open(self, multi_select_page):
        multi_select_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = true;
        """)
        multi_select_page.wait_for_timeout(200)
        multi_select_page.evaluate("""
            document.querySelector('form[hx-post]').noValidate = true;
            document.querySelector('form[hx-post] button[type="submit"]').click();
        """)
        multi_select_page.wait_for_timeout(500)
        multi = self._get(multi_select_page)
        assert multi.get_attribute("open") is not None

    def test_wrapper_has_id(self, multi_select_page):
        multi = self._get(multi_select_page)
        assert multi.get_attribute("id") is not None
        assert "_multiselect" in multi.get_attribute("id")

    def test_no_search_bar(self, multi_select_page):
        """Plain MultiSelect with 4 choices should not show search (< threshold)."""
        multi = self._get(multi_select_page)
        multi.locator("summary").click()
        multi_select_page.wait_for_timeout(100)
        search = multi.locator('input[type="text"]')
        assert search.count() == 0


class TestMultiSelectIcons:
    """MultiSelect with flag icons and 31 countries (auto-search threshold)."""

    def _get(self, page):
        return page.locator("details.dropdown.multiselect").nth(1)

    def test_renders(self, multi_select_page):
        multi = self._get(multi_select_page)
        assert multi.is_visible()

    def test_has_search_bar(self, multi_select_page):
        """31 countries > search_threshold=20 — search bar appears automatically."""
        multi = self._get(multi_select_page)
        multi.locator("summary").click()
        multi_select_page.wait_for_timeout(100)
        search = multi.locator('input[type="text"]')
        assert search.count() == 1
        percy_snapshot(multi_select_page, "MultiSelect Icons - Open with Search")

    def test_many_checkboxes(self, multi_select_page):
        """Should have 31 country checkboxes."""
        multi = self._get(multi_select_page)
        multi.locator("summary").click()
        multi_select_page.wait_for_timeout(100)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() == 31


class TestMultiSelectHtmx:
    """MultiSelect with server-side search via htmx."""

    def _get(self, page):
        return page.locator("details.dropdown.multiselect").nth(2)

    def _open_and_load(self, page):
        multi = self._get(page)
        multi.locator("summary").click()
        page.wait_for_timeout(200)
        page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.multiselect');
            const search = dds[2].querySelector('input[type="text"]');
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=&type=multiselect&name=languages_htmx', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        checkboxes = multi.locator('input[type="checkbox"]')
        expect(checkboxes.first).to_be_attached(timeout=3000)
        return multi

    def test_renders(self, multi_select_page):
        multi = self._get(multi_select_page)
        assert multi.is_visible()

    def test_open_loads_results(self, multi_select_page):
        multi = self._open_and_load(multi_select_page)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() >= 1

    def test_select_creates_hidden_inputs(self, multi_select_page):
        multi = self._open_and_load(multi_select_page)
        multi_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.multiselect');
            const cbs = dds[2].querySelectorAll('input[type="checkbox"]');
            if (cbs.length >= 2) {
                cbs[0].checked = true;
                cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
                cbs[1].checked = true;
                cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""")
        multi_select_page.wait_for_timeout(300)
        hidden = multi.locator('input[type="hidden"][name="languages_htmx"]')
        assert hidden.count() >= 2
