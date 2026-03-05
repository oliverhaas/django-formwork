"""E2e tests for dropdown widgets: SearchSelect, MultiSelect, ComboBox."""

from playwright.sync_api import expect

from .conftest import submit

# ---------------------------------------------------------------------------
# SearchSelect (static choices)
# ---------------------------------------------------------------------------


class TestSearchSelect:
    """SearchSelect with static choices — dropdown, search, pick, morph."""

    def test_renders(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        assert sel.is_visible()

    def test_open_close_dropdown(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        summary = sel.locator("summary")
        summary.click()
        widget_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is not None
        # Click outside to close (summary::before overlay)
        summary.click()
        widget_page.wait_for_timeout(200)

    def test_search_filters_options(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        widget_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        widget_page.wait_for_timeout(200)
        search = sel.locator('.dropdown-content input[type="text"]')
        search.fill("Tok")
        widget_page.wait_for_timeout(100)
        assert sel.locator("button", has_text="Tokyo").is_visible()
        assert not sel.locator("button", has_text="London").is_visible()

    def test_pick_option_sets_value(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        hidden = sel.locator('input[type="hidden"]')
        widget_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        widget_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        widget_page.wait_for_timeout(100)
        assert hidden.input_value() == "ldn"

    def test_pick_closes_dropdown(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        summary = sel.locator("summary")
        summary.click()
        widget_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        widget_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is None
        assert "London" in summary.text_content()

    def test_pick_shows_icon_in_summary(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        summary = sel.locator("summary")
        widget_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        widget_page.wait_for_timeout(200)
        sel.locator("button", has_text="New York").click()
        widget_page.wait_for_timeout(100)
        assert "New York" in summary.text_content()

    def test_morph_preserves_value(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        widget_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        widget_page.wait_for_timeout(200)
        sel.locator("button", has_text="London").click()
        widget_page.wait_for_timeout(200)
        hidden = sel.locator('input[type="hidden"]')
        assert hidden.input_value() == "ldn"
        submit(widget_page)
        hidden = widget_page.locator(
            "details.dropdown.search-select input[type='hidden']",
        ).first
        assert hidden.input_value() == "ldn"
        summary = widget_page.locator("details.dropdown.search-select summary").first
        assert "London" in summary.text_content()

    def test_morph_preserves_dropdown_closed(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        widget_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        widget_page.wait_for_timeout(200)
        sel.locator("button", has_text="Tokyo").click()
        widget_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is None
        submit(widget_page)
        assert sel.get_attribute("open") is None

    def test_morph_preserves_dropdown_open(self, widget_page):
        widget_page.evaluate("""
            document.querySelector('details.dropdown.search-select').open = true;
        """)
        widget_page.wait_for_timeout(200)
        # Submit via JS (open dropdown overlays the submit button)
        widget_page.evaluate("""
            document.querySelector('#widget-form').noValidate = true;
            document.querySelector('#widget-form button[type="submit"]').click();
        """)
        widget_page.wait_for_timeout(500)
        sel = widget_page.locator("details.dropdown.search-select").first
        assert sel.get_attribute("open") is not None

    def test_wrapper_has_id(self, widget_page):
        sel = widget_page.locator("details.dropdown.search-select").first
        assert sel.get_attribute("id") is not None
        assert "_searchselect" in sel.get_attribute("id")


# ---------------------------------------------------------------------------
# SearchSelect with htmx
# ---------------------------------------------------------------------------


class TestSearchSelectHtmx:
    """SearchSelect with server-side search via htmx."""

    def _get_htmx_select(self, widget_page):
        """Return the htmx-powered SearchSelect (second one on page)."""
        return widget_page.locator("details.dropdown.search-select").nth(1)

    def _open_and_load(self, widget_page):
        sel = self._get_htmx_select(widget_page)
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const dd = dds[1];
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        widget_page.wait_for_timeout(200)
        # Trigger htmx load
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const dd = dds[1];
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        widget_page.wait_for_timeout(1000)
        return sel

    def test_renders(self, widget_page):
        sel = self._get_htmx_select(widget_page)
        assert sel.is_visible()

    def test_open_loads_results(self, widget_page):
        sel = self._open_and_load(widget_page)
        buttons = sel.locator("ul button")
        assert buttons.count() >= 1

    def test_search_filters_via_htmx(self, widget_page):
        sel = self._open_and_load(widget_page)
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const dd = dds[1];
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.value = 'Tok';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
        assert "Tokyo" in sel.locator("ul button").first.text_content()

    def test_pick_sets_value(self, widget_page):
        sel = self._open_and_load(widget_page)
        hidden = sel.locator('input[type="hidden"]')
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const dd = dds[1];
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.value = 'Lon';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        widget_page.wait_for_timeout(1000)
        sel.locator("ul button", has_text="London").click()
        widget_page.wait_for_timeout(200)
        assert hidden.input_value() == "ldn"

    def test_no_results_message(self, widget_page):
        sel = self._open_and_load(widget_page)
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.search-select');
            const dd = dds[1];
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=zzzzz&type=search_select', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        no_results = sel.locator("li", has_text="No results")
        expect(no_results).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# MultiSelect (static choices)
# ---------------------------------------------------------------------------


class TestMultiSelect:
    """MultiSelect with static choices — checkboxes, summary, morph."""

    def test_renders(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        assert multi.is_visible()

    def test_open_shows_checkboxes(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        summary = multi.locator("summary")
        summary.click()
        widget_page.wait_for_timeout(100)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() >= 2

    def test_select_multiple(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        multi.locator("summary").click()
        widget_page.wait_for_timeout(100)
        widget_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.multiselect');
            ['py', 'go'].forEach(v => {
                const cb = dd.querySelector(`input[value="${v}"]`);
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""")
        widget_page.wait_for_timeout(100)
        assert multi.locator('input[value="py"]').is_checked()
        assert multi.locator('input[value="go"]').is_checked()

    def test_summary_shows_selection(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        summary = multi.locator("summary")
        summary.click()
        widget_page.wait_for_timeout(100)
        widget_page.evaluate("""() => {
            const dd = document.querySelector('details.dropdown.multiselect');
            const cb = dd.querySelector('input[value="py"]');
            cb.checked = true;
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        widget_page.wait_for_timeout(100)
        summary_text = summary.text_content()
        assert "Python" in summary_text or "1" in summary_text

    def test_morph_preserves_values(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        widget_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = true;
        """)
        widget_page.wait_for_timeout(200)
        widget_page.evaluate("""
            const dd = document.querySelector('details.dropdown.multiselect');
            const cbs = dd.querySelectorAll('input[type="checkbox"]');
            cbs[0].checked = true;
            cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
            cbs[2].checked = true;
            cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
        """)
        widget_page.wait_for_timeout(200)
        widget_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = false;
        """)
        widget_page.wait_for_timeout(100)
        submit(widget_page)
        checked = widget_page.evaluate("""
            [...document.querySelectorAll('details.dropdown.multiselect input[type="checkbox"]:checked')]
                .map(cb => cb.value)
        """)
        assert "py" in checked
        assert "go" in checked

    def test_morph_preserves_dropdown_open(self, widget_page):
        widget_page.evaluate("""
            document.querySelector('details.dropdown.multiselect').open = true;
        """)
        widget_page.wait_for_timeout(200)
        widget_page.evaluate("""
            document.querySelector('#widget-form').noValidate = true;
            document.querySelector('#widget-form button[type="submit"]').click();
        """)
        widget_page.wait_for_timeout(500)
        multi = widget_page.locator("details.dropdown.multiselect").first
        assert multi.get_attribute("open") is not None

    def test_wrapper_has_id(self, widget_page):
        multi = widget_page.locator("details.dropdown.multiselect").first
        assert multi.get_attribute("id") is not None
        assert "_multiselect" in multi.get_attribute("id")


# ---------------------------------------------------------------------------
# MultiSelect with htmx
# ---------------------------------------------------------------------------


class TestMultiSelectHtmx:
    """MultiSelect with server-side search via htmx."""

    def _get_htmx_multi(self, widget_page):
        return widget_page.locator("details.dropdown.multiselect").nth(1)

    def _open_and_load(self, widget_page):
        multi = self._get_htmx_multi(widget_page)
        multi.locator("summary").click()
        widget_page.wait_for_timeout(200)
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.multiselect');
            const dd = dds[1];
            const search = dd.querySelector('input[type="text"]');
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=&type=multiselect&name=multi_select_htmx', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        checkboxes = multi.locator('input[type="checkbox"]')
        expect(checkboxes.first).to_be_attached(timeout=3000)
        return multi

    def test_renders(self, widget_page):
        multi = self._get_htmx_multi(widget_page)
        assert multi.is_visible()

    def test_open_loads_results(self, widget_page):
        multi = self._open_and_load(widget_page)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() >= 1

    def test_select_creates_hidden_inputs(self, widget_page):
        multi = self._open_and_load(widget_page)
        widget_page.evaluate("""() => {
            const dds = document.querySelectorAll('details.dropdown.multiselect');
            const dd = dds[1];
            const cbs = dd.querySelectorAll('input[type="checkbox"]');
            if (cbs.length >= 2) {
                cbs[0].checked = true;
                cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
                cbs[1].checked = true;
                cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""")
        widget_page.wait_for_timeout(300)
        hidden = multi.locator('input[type="hidden"][name="multi_select_htmx"]')
        assert hidden.count() >= 2


class TestComboBox:
    """ComboBox with client-side suggestions."""

    def test_renders(self, widget_page):
        combo = widget_page.locator(".dropdown.combobox").first
        assert combo.is_visible()

    def test_type_shows_suggestions(self, widget_page):
        inp = widget_page.locator('input[name="combobox"]')
        inp.click()
        inp.fill("Py")
        widget_page.wait_for_timeout(150)
        combo = widget_page.locator(".dropdown.combobox").first
        assert combo.locator("button", has_text="Python").is_visible()
        assert not combo.locator("button", has_text="Go").is_visible()

    def test_pick_suggestion(self, widget_page):
        inp = widget_page.locator('input[name="combobox"]')
        inp.click()
        inp.fill("Ru")
        widget_page.wait_for_timeout(150)
        combo = widget_page.locator(".dropdown.combobox").first
        combo.locator("button", has_text="Rust").click()
        widget_page.wait_for_timeout(100)
        assert inp.input_value() == "Rust"

    def test_free_text_allowed(self, widget_page):
        inp = widget_page.locator('input[name="combobox"]')
        inp.fill("Haskell")
        assert inp.input_value() == "Haskell"

    def test_morph_preserves_value(self, widget_page):
        inp = widget_page.locator('input[name="combobox"]')
        inp.fill("Haskell")
        submit(widget_page)
        assert inp.input_value() == "Haskell"

    def test_wrapper_has_id(self, widget_page):
        wrapper = widget_page.locator("div.combobox").first
        assert wrapper.get_attribute("id") is not None
        assert "_combobox" in wrapper.get_attribute("id")


class TestComboBoxMultiple:
    """ComboBox in multiple (comma-separated) mode with toggle."""

    def _get_combo(self, widget_page):
        return widget_page.locator(".dropdown.combobox").nth(1)

    def test_renders(self, widget_page):
        inp = widget_page.locator('input[name="combobox_multi"]')
        assert inp.is_visible()

    def test_pick_adds_value(self, widget_page):
        combo = self._get_combo(widget_page)
        inp = widget_page.locator('input[name="combobox_multi"]')
        inp.click()
        widget_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        widget_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()

    def test_pick_second_appends(self, widget_page):
        combo = self._get_combo(widget_page)
        inp = widget_page.locator('input[name="combobox_multi"]')
        inp.click()
        widget_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        widget_page.wait_for_timeout(100)
        combo.locator("button", has_text="Sushi").click()
        widget_page.wait_for_timeout(100)
        val = inp.input_value()
        assert "Pizza" in val
        assert "Sushi" in val

    def test_pick_toggle_off(self, widget_page):
        combo = self._get_combo(widget_page)
        inp = widget_page.locator('input[name="combobox_multi"]')
        inp.click()
        widget_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        widget_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()
        combo.locator("button", has_text="Pizza").click()
        widget_page.wait_for_timeout(100)
        assert "Pizza" not in inp.input_value()

    def test_checkmark_indicator(self, widget_page):
        combo = self._get_combo(widget_page)
        inp = widget_page.locator('input[name="combobox_multi"]')
        inp.click()
        widget_page.wait_for_timeout(150)
        pizza_btn = combo.locator("button", has_text="Pizza")
        checkmark = pizza_btn.locator(".formwork-check")
        assert checkmark.count() == 1
        pizza_btn.click()
        widget_page.wait_for_timeout(100)
        has_opacity = widget_page.evaluate("""() => {
            const combos = document.querySelectorAll('.combobox');
            const btn = combos[1].querySelector('button[data-suggestion="Pizza"] .formwork-check');
            return btn ? btn.classList.contains('opacity-100') : false;
        }""")
        assert has_opacity

    def test_morph_preserves_value(self, widget_page):
        combo = self._get_combo(widget_page)
        inp = widget_page.locator('input[name="combobox_multi"]')
        inp.click()
        widget_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        widget_page.wait_for_timeout(100)
        combo.locator("button", has_text="Sushi").click()
        widget_page.wait_for_timeout(100)
        val_before = inp.input_value()
        submit(widget_page)
        assert inp.input_value() == val_before
