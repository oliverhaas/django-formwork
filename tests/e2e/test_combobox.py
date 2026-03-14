"""E2e tests for ComboBox widget: single, multiple, icons, and htmx."""

from percy import percy_snapshot
from playwright.sync_api import expect

from .conftest import submit


class TestComboBoxSingle:
    """ComboBox with single-value client-side suggestions."""

    def _get(self, page):
        return page.locator(".dropdown.combobox").first

    def test_renders(self, combobox_page):
        combo = self._get(combobox_page)
        assert combo.is_visible()
        percy_snapshot(combobox_page, "ComboBox - Default")

    def test_type_shows_suggestions(self, combobox_page):
        inp = combobox_page.locator('input[name="language_single"]')
        inp.click()
        inp.fill("Py")
        combobox_page.wait_for_timeout(150)
        combo = self._get(combobox_page)
        assert combo.locator("button", has_text="Python").is_visible()
        assert not combo.locator("button", has_text="Go").is_visible()

    def test_pick_suggestion(self, combobox_page):
        inp = combobox_page.locator('input[name="language_single"]')
        inp.click()
        inp.fill("Ru")
        combobox_page.wait_for_timeout(150)
        combo = self._get(combobox_page)
        combo.locator("button", has_text="Rust").click()
        combobox_page.wait_for_timeout(100)
        assert inp.input_value() == "Rust"

    def test_free_text_allowed(self, combobox_page):
        inp = combobox_page.locator('input[name="language_single"]')
        inp.fill("Haskell")
        assert inp.input_value() == "Haskell"

    def test_morph_preserves_value(self, combobox_page):
        inp = combobox_page.locator('input[name="language_single"]')
        inp.fill("Haskell")
        submit(combobox_page)
        assert inp.input_value() == "Haskell"

    def test_wrapper_has_id(self, combobox_page):
        wrapper = combobox_page.locator("div.combobox").first
        assert wrapper.get_attribute("id") is not None
        assert "_combobox" in wrapper.get_attribute("id")


class TestComboBoxMultiple:
    """ComboBox in multiple (comma-separated) mode with toggle."""

    def _get(self, page):
        return page.locator(".dropdown.combobox").nth(1)

    def test_renders(self, combobox_page):
        inp = combobox_page.locator('input[name="toppings_multi"]')
        assert inp.is_visible()

    def test_pick_adds_value(self, combobox_page):
        combo = self._get(combobox_page)
        inp = combobox_page.locator('input[name="toppings_multi"]')
        inp.click()
        combobox_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        combobox_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()

    def test_pick_second_appends(self, combobox_page):
        combo = self._get(combobox_page)
        inp = combobox_page.locator('input[name="toppings_multi"]')
        inp.click()
        combobox_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        combobox_page.wait_for_timeout(100)
        combo.locator("button", has_text="Sushi").click()
        combobox_page.wait_for_timeout(100)
        val = inp.input_value()
        assert "Pizza" in val
        assert "Sushi" in val

    def test_pick_toggle_off(self, combobox_page):
        combo = self._get(combobox_page)
        inp = combobox_page.locator('input[name="toppings_multi"]')
        inp.click()
        combobox_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        combobox_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()
        combo.locator("button", has_text="Pizza").click()
        combobox_page.wait_for_timeout(100)
        assert "Pizza" not in inp.input_value()

    def test_checkmark_indicator(self, combobox_page):
        combo = self._get(combobox_page)
        inp = combobox_page.locator('input[name="toppings_multi"]')
        inp.click()
        combobox_page.wait_for_timeout(150)
        pizza_btn = combo.locator("button", has_text="Pizza")
        checkmark = pizza_btn.locator(".formwork-check")
        assert checkmark.count() == 1
        pizza_btn.click()
        combobox_page.wait_for_timeout(100)
        has_opacity = combobox_page.evaluate("""() => {
            const combos = document.querySelectorAll('.combobox');
            const btn = combos[1].querySelector('button[data-suggestion="Pizza"] .formwork-check');
            return btn ? btn.classList.contains('opacity-100') : false;
        }""")
        assert has_opacity

    def test_morph_preserves_value(self, combobox_page):
        combo = self._get(combobox_page)
        inp = combobox_page.locator('input[name="toppings_multi"]')
        inp.click()
        combobox_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        combobox_page.wait_for_timeout(100)
        combo.locator("button", has_text="Sushi").click()
        combobox_page.wait_for_timeout(100)
        # Press Escape to close the dropdown, then blur strips trailing comma
        combobox_page.keyboard.press("Escape")
        combobox_page.wait_for_timeout(200)
        inp.blur()
        combobox_page.wait_for_timeout(100)
        val_before = inp.input_value()
        submit(combobox_page)
        assert inp.input_value() == val_before


class TestComboBoxIcons:
    """ComboBox with icon suggestions."""

    def _get(self, page):
        return page.locator(".dropdown.combobox").nth(2)

    def test_renders(self, combobox_page):
        combo = self._get(combobox_page)
        assert combo.is_visible()

    def test_type_shows_filtered_suggestions(self, combobox_page):
        inp = combobox_page.locator('input[name="language_icons"]')
        inp.click()
        inp.fill("Py")
        combobox_page.wait_for_timeout(150)
        combo = self._get(combobox_page)
        assert combo.locator("button", has_text="Python").is_visible()
        assert not combo.locator("button", has_text="Go").is_visible()
        percy_snapshot(combobox_page, "ComboBox Icons - Filtered")


class TestComboBoxHtmx:
    """ComboBox with server-side search via htmx."""

    def _get(self, page):
        return page.locator(".dropdown.combobox").nth(3)

    def test_renders(self, combobox_page):
        combo = self._get(combobox_page)
        assert combo.is_visible()

    def test_type_loads_suggestions(self, combobox_page):
        inp = combobox_page.locator('input[name="language_htmx"]')
        inp.click()
        combobox_page.evaluate("""() => {
            const inp = document.querySelector('input[name="language_htmx"]');
            inp.value = 'Py';
            inp.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        combo = self._get(combobox_page)
        expect(combo.locator("button", has_text="Python")).to_be_visible(timeout=3000)
