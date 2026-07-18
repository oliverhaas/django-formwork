"""E2e tests for standalone HTML elements auto-styled by formwork.css."""


class TestStandaloneElements:
    """Verify that raw HTML inputs get DaisyUI styling from formwork.css."""

    def _card(self, page):
        return page.locator(".card-body")

    def test_page_loads(self, elements_page):
        assert elements_page.title() == "Standalone Elements"

    def test_text_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="text"]:not(.input-soft)')
        assert inp.is_visible()

    def test_email_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="email"]')
        assert inp.is_visible()

    def test_password_input_renders(self, elements_page):
        inp = self._card(elements_page).locator('input[type="password"]')
        assert inp.is_visible()

    def test_select_renders(self, elements_page):
        sel = self._card(elements_page).locator("select:not(.select-soft)")
        assert sel.is_visible()
        options = sel.locator("option")
        assert options.count() == 4  # empty + 3 options

    def test_textarea_renders(self, elements_page):
        ta = self._card(elements_page).locator("textarea:not(.textarea-soft)")
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

    # --- Soft colour variant (select-soft / input-soft / textarea-soft) ---

    def test_soft_variant_controls_render(self, elements_page):
        card = self._card(elements_page)
        assert card.locator("select.select-soft.select-accent").is_visible()
        assert card.locator("select.select-soft.select-error").is_visible()
        assert card.locator("input.input-soft.input-accent").is_visible()
        assert card.locator("textarea.textarea-soft.textarea-accent").is_visible()

    def test_soft_select_is_tinted(self, elements_page):
        # The -soft variant fills the whole control: its text takes the accent
        # colour and its background is an accent-tinted mix, both different from
        # the plain (border-only) base select.
        card = self._card(elements_page)
        base = card.locator("select:not(.select-soft)")
        soft = card.locator("select.select-soft.select-accent")
        assert soft.evaluate("el => getComputedStyle(el).color") != base.evaluate("el => getComputedStyle(el).color")
        assert soft.evaluate("el => getComputedStyle(el).backgroundColor") != base.evaluate(
            "el => getComputedStyle(el).backgroundColor",
        )

    def test_soft_variant_composes_with_colour_modifier(self, elements_page):
        # select-soft keys off --input-color, so swapping the colour modifier
        # (accent vs error) re-tints the fill and text.
        card = self._card(elements_page)
        accent = card.locator("select.select-soft.select-accent")
        error = card.locator("select.select-soft.select-error")
        assert accent.evaluate("el => getComputedStyle(el).color") != error.evaluate("el => getComputedStyle(el).color")

    def test_soft_select_border_snaps_on_focus(self, elements_page):
        # Regression: the -soft border must brighten to the full colour on
        # focus (like a plain control whose border snaps to --input-color),
        # not stay its faint resting tint. Otherwise focus/open shows no border.
        soft = self._card(elements_page).locator("select.select-soft.select-accent")
        rest = soft.evaluate("el => getComputedStyle(el).borderColor")
        soft.focus()
        focused = soft.evaluate("el => getComputedStyle(el).borderColor")
        assert focused != rest

    def test_soft_input_and_textarea_are_tinted(self, elements_page):
        card = self._card(elements_page)
        base_input = card.locator('input[type="text"]:not(.input-soft)')
        soft_input = card.locator("input.input-soft")
        soft_textarea = card.locator("textarea.textarea-soft")
        assert soft_input.evaluate("el => getComputedStyle(el).color") != base_input.evaluate(
            "el => getComputedStyle(el).color",
        )
        assert soft_textarea.evaluate("el => getComputedStyle(el).color") != base_input.evaluate(
            "el => getComputedStyle(el).color",
        )
