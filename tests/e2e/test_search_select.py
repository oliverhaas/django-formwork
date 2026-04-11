"""E2e tests for SearchSelect widget: plain, with icons, and htmx."""

from playwright.sync_api import expect

from .conftest import submit


class TestSearchSelectPlain:
    """SearchSelect with few static choices — no search input shown."""

    def _get(self, page):
        return page.locator("details.dropdown.search-select").first

    def test_renders(self, search_select_page):
        sel = self._get(search_select_page)
        assert sel.is_visible()

    def test_open_close_dropdown(self, search_select_page):
        sel = self._get(search_select_page)
        summary = sel.locator("summary")
        summary.click()
        search_select_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is not None
        summary.click()
        search_select_page.wait_for_timeout(200)

    def test_no_search_input_with_few_options(self, search_select_page):
        sel = self._get(search_select_page)
        search_select_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        search_wrapper = sel.locator(".dropdown-content > div").first
        assert not search_wrapper.is_visible()

    def test_pick_option_sets_value(self, search_select_page):
        sel = self._get(search_select_page)
        hidden = sel.locator('input[type="hidden"][name]')
        search_select_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        search_select_page.wait_for_timeout(100)
        assert hidden.input_value() == "ldn"

    def test_pick_closes_dropdown(self, search_select_page):
        sel = self._get(search_select_page)
        summary = sel.locator("summary")
        summary.click()
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        search_select_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is None
        assert "London" in summary.text_content()

    def test_morph_preserves_value(self, search_select_page):
        sel = self._get(search_select_page)
        search_select_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        search_select_page.wait_for_timeout(200)
        hidden = sel.locator('input[type="hidden"][name]')
        assert hidden.input_value() == "ldn"
        submit(search_select_page)
        hidden = search_select_page.locator(
            "details.dropdown.search-select input[type='hidden']",
        ).first
        assert hidden.input_value() == "ldn"
        summary = search_select_page.locator(
            "details.dropdown.search-select summary",
        ).first
        assert "London" in summary.text_content()

    def test_morph_preserves_dropdown_closed(self, search_select_page):
        sel = self._get(search_select_page)
        search_select_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="Tokyo").click()
        search_select_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is None
        submit(search_select_page)
        assert sel.get_attribute("open") is None

    def test_morph_preserves_dropdown_open(self, search_select_page):
        search_select_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        search_select_page.wait_for_timeout(200)
        search_select_page.evaluate("""
            document.querySelector('form[hx-post]').noValidate = true;
            document.querySelector('form[hx-post] button[type="submit"]').click();
        """)
        search_select_page.wait_for_timeout(500)
        sel = self._get(search_select_page)
        assert sel.get_attribute("open") is not None

    def test_wrapper_has_id(self, search_select_page):
        sel = self._get(search_select_page)
        assert sel.get_attribute("id") is not None
        assert "_searchselect" in sel.get_attribute("id")


class TestSearchSelectMany:
    """SearchSelect with many options — search input shown automatically."""

    def _get(self, page):
        return page.locator("details.dropdown.search-select").nth(1)

    def test_search_input_shown(self, search_select_page):
        sel = self._get(search_select_page)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[1].open = true;
            dds[1].dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        search = sel.locator('.dropdown-content input[type="text"]')
        assert search.count() == 1

    def test_search_filters_options(self, search_select_page):
        sel = self._get(search_select_page)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[1].open = true;
            dds[1].dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        search = sel.locator('.dropdown-content input[type="text"]')
        search.fill("Jap")
        search_select_page.wait_for_timeout(100)
        assert sel.locator("button", has_text="Japan").is_visible()
        assert not sel.locator("button", has_text="Brazil").is_visible()

    def test_pick_option_sets_value(self, search_select_page):
        sel = self._get(search_select_page)
        hidden = sel.locator('input[type="hidden"][name]')
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[1].open = true;
            dds[1].dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="Germany").click()
        search_select_page.wait_for_timeout(100)
        assert hidden.input_value() == "de"


class TestSearchSelectIcons:
    """SearchSelect with icons in choices."""

    def _get(self, page):
        return page.locator("details.dropdown.search-select").nth(2)

    def test_renders(self, search_select_page):
        sel = self._get(search_select_page)
        assert sel.is_visible()

    def test_pick_shows_icon_in_summary(self, search_select_page):
        sel = self._get(search_select_page)
        summary = sel.locator("summary")
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[2].open = true;
            dds[2].dispatchEvent(new Event('toggle'));
        }""")
        search_select_page.wait_for_timeout(200)
        sel.locator("button", has_text="New York").click()
        search_select_page.wait_for_timeout(100)
        assert "New York" in summary.text_content()


class TestSearchSelectHtmx:
    """SearchSelect with server-side search via htmx."""

    def _get(self, page):
        return page.locator("details.dropdown.search-select").nth(3)

    def _open_and_load(self, page):
        sel = self._get(page)
        page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[3].open = true;
            dds[3].dispatchEvent(new Event('toggle'));
        }""")
        page.wait_for_timeout(200)
        page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[3].querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        page.wait_for_timeout(1000)
        return sel

    def test_renders(self, search_select_page):
        sel = self._get(search_select_page)
        assert sel.is_visible()

    def test_open_loads_results(self, search_select_page):
        sel = self._open_and_load(search_select_page)
        buttons = sel.locator("ul button")
        assert buttons.count() >= 1

    def test_search_filters_via_htmx(self, search_select_page):
        sel = self._open_and_load(search_select_page)
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[3].querySelector('.dropdown-content input[type="text"]');
            search.value = 'Tok';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
        assert "Tokyo" in sel.locator("ul button").first.text_content()

    def test_pick_sets_value(self, search_select_page):
        sel = self._open_and_load(search_select_page)
        hidden = sel.locator('input[type="hidden"][name]')
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[3].querySelector('.dropdown-content input[type="text"]');
            search.value = 'Lon';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        search_select_page.wait_for_timeout(1000)
        sel.locator("ul button", has_text="London").click()
        search_select_page.wait_for_timeout(200)
        assert hidden.input_value() == "ldn"

    def test_no_results_message(self, search_select_page):
        sel = self._open_and_load(search_select_page)
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[3].querySelector('.dropdown-content input[type="text"]');
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=zzzzz&type=search_select', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        no_results = sel.locator("li", has_text="No results")
        expect(no_results).to_be_visible(timeout=3000)


class TestSearchSelectHtmxMany:
    """SearchSelect with server-side search and enough options for auto-search.

    This is the city_htmx_many dropdown (nth=4).
    It has 24 options — above the search_threshold of 20 — so the search
    input should become visible after the first htmx load.
    """

    def _get(self, page):
        return page.locator("details.dropdown.search-select").nth(4)

    def _open_and_wait(self, page):
        sel = self._get(page)
        page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[4].open = true;
            dds[4].dispatchEvent(new Event('toggle'));
        }""")
        page.wait_for_timeout(2000)
        return sel

    def test_open_loads_all_results(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        buttons = sel.locator("ul button")
        expect(buttons).to_have_count(24, timeout=3000)

    def test_search_input_shown_above_threshold(self, search_select_page):
        """Search input becomes visible because total (24) >= threshold (20)."""
        sel = self._open_and_wait(search_select_page)
        search_wrapper = sel.locator(".dropdown-content > div").first
        expect(search_wrapper).to_be_visible(timeout=3000)

    def test_search_filters_via_htmx(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[4].querySelector('.dropdown-content input[type="text"]');
            search.value = 'Ber';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
        assert "Berlin" in sel.locator("ul button").first.text_content()


class TestSearchSelectHtmxIcons:
    """SearchSelect with server-side search, icons, and descriptions.

    This is the country_htmx_icons dropdown (nth=5).
    It has 31 options — above the search_threshold — so the search
    input should become visible after the first htmx load.
    """

    def _get(self, page):
        return page.locator("details.dropdown.search-select").nth(5)

    def _open_and_wait(self, page):
        sel = self._get(page)
        page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            dds[5].open = true;
            dds[5].dispatchEvent(new Event('toggle'));
        }""")
        # Wait for htmx to load initial results and OOB total count.
        page.wait_for_timeout(2000)
        return sel

    def test_renders(self, search_select_page):
        sel = self._get(search_select_page)
        assert sel.is_visible()

    def test_open_loads_all_results(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        buttons = sel.locator("ul button")
        expect(buttons).to_have_count(31, timeout=3000)

    def test_search_input_shown_above_threshold(self, search_select_page):
        """Search input should be visible when total count >= search_threshold."""
        sel = self._open_and_wait(search_select_page)
        search_wrapper = sel.locator(".dropdown-content > div").first
        expect(search_wrapper).to_be_visible(timeout=3000)

    def test_results_have_icons(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        # Each button has an icon span with a flag emoji.
        first_button = sel.locator("ul button").first
        icon_span = first_button.locator("span.shrink-0").first
        assert icon_span.text_content().strip() != ""

    def test_results_have_descriptions(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        descs = sel.locator("ul button span.text-xs")
        assert descs.count() >= 1
        assert descs.first.text_content().strip() != ""

    def test_search_filters_via_htmx(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        search_select_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const search = dds[5].querySelector('.dropdown-content input[type="text"]');
            search.value = 'Jap';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
        assert "Japan" in sel.locator("ul button").first.text_content()

    def test_pick_sets_value(self, search_select_page):
        sel = self._open_and_wait(search_select_page)
        hidden = sel.locator('input[type="hidden"][name]')
        sel.locator("ul button", has_text="France").click()
        search_select_page.wait_for_timeout(200)
        assert hidden.input_value() == "fr"
