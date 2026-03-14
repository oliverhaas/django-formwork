"""E2e tests for standalone HTML elements auto-styled by formwork.css."""

from percy import percy_snapshot


class TestStandaloneElements:
    """Verify that raw HTML inputs get DaisyUI styling from formwork.css."""

    def _card(self, page):
        return page.locator(".card-body")

    def test_page_loads(self, elements_page):
        assert elements_page.title() == "Standalone Elements"

    def test_text_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="text"]')
        assert inp.is_visible()
        percy_snapshot(elements_page, "Standalone Elements")

    def test_email_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="email"]')
        assert inp.is_visible()

    def test_password_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="password"]')
        assert inp.is_visible()

    def test_select_renders(self, elements_page):
        sel = self._card(elements_page).locator("select")
        assert sel.is_visible()
        options = sel.locator("option")
        assert options.count() == 4  # empty + 3 options

    def test_textarea_renders(self, elements_page):
        ta = self._card(elements_page).locator("textarea")
        assert ta.is_visible()

    def test_checkbox_renders(self, elements_page):
        cb = self._card(elements_page).locator('input[type="checkbox"]')
        assert cb.count() == 1

    def test_radio_renders(self, elements_page):
        radios = self._card(elements_page).locator('input[type="radio"]')
        assert radios.count() == 2

    def test_file_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="file"]')
        assert inp.count() == 1

    def test_range_input_renders(self, elements_page):
        rng = self._card(elements_page).locator('input[type="range"]')
        assert rng.is_visible()
