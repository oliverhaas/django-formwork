"""E2e tests for custom simple widgets: Toggle, Range, Rating, PasswordReveal, DataList."""

from .conftest import submit


class TestToggle:
    """Toggle switch widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        toggle = widget_page.locator('input[name="toggle"]')
        assert toggle.count() == 1

    def test_toggle_on_off(self, widget_page):
        toggle = widget_page.locator('input[name="toggle"]')
        assert not toggle.is_checked()
        toggle.click()
        assert toggle.is_checked()
        toggle.click()
        assert not toggle.is_checked()

    def test_morph_preserves_checked(self, widget_page):
        toggle = widget_page.locator('input[name="toggle"]')
        toggle.check()
        assert toggle.is_checked()
        submit(widget_page)
        assert widget_page.locator('input[name="toggle"]').is_checked()

    def test_morph_preserves_unchecked(self, widget_page):
        toggle = widget_page.locator('input[name="toggle"]')
        assert not toggle.is_checked()
        submit(widget_page)
        assert not widget_page.locator('input[name="toggle"]').is_checked()


class TestRange:
    """Range slider widget functionality and morph resilience."""

    def test_renders_with_attrs(self, widget_page):
        rng = widget_page.locator('input[name="volume"]')
        assert rng.get_attribute("type") == "range"
        assert rng.get_attribute("min") == "0"
        assert rng.get_attribute("max") == "100"
        assert rng.get_attribute("step") == "10"

    def test_set_value(self, widget_page):
        widget_page.evaluate("""
            const r = document.querySelector('input[name="volume"]');
            r.value = '70';
            r.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        assert widget_page.locator('input[name="volume"]').input_value() == "70"

    def test_morph_preserves_value(self, widget_page):
        widget_page.evaluate("""
            const r = document.querySelector('input[name="volume"]');
            r.value = '70';
            r.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        submit(widget_page)
        assert widget_page.locator('input[name="volume"]').input_value() == "70"


class TestRating:
    """Rating star widget functionality and morph resilience."""

    def test_renders_stars(self, widget_page):
        rating = widget_page.locator(".rating")
        stars = rating.locator('input[type="radio"]')
        assert stars.count() == 5

    def test_click_selects_star(self, widget_page):
        rating = widget_page.locator(".rating")
        third_star = rating.locator('input[type="radio"]').nth(2)
        third_star.click(force=True)
        assert third_star.is_checked()

    def test_morph_preserves_value(self, widget_page):
        widget_page.evaluate("""
            const star = document.querySelector('#id_rating input[value="3"]');
            star.checked = true;
            star.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        submit(widget_page)
        checked = widget_page.evaluate(
            "document.querySelector('#id_rating input:checked')?.value || ''",
        )
        assert checked == "3"


class TestPasswordReveal:
    """PasswordReveal widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        inp = widget_page.locator('input[name="password"]')
        assert inp.is_visible()

    def test_type_password(self, widget_page):
        inp = widget_page.locator('input[name="password"]')
        assert inp.get_attribute("type") == "password"

    def test_toggle_visibility(self, widget_page):
        inp = widget_page.locator('input[name="password"]')
        assert inp.get_attribute("type") == "password"
        # Click reveal button
        widget_page.locator("label.input button").click()
        widget_page.wait_for_timeout(100)
        assert inp.get_attribute("type") == "text"
        # Click again to hide
        widget_page.locator("label.input button").click()
        widget_page.wait_for_timeout(100)
        assert inp.get_attribute("type") == "password"

    def test_morph_clears_value(self, widget_page):
        """Django's PasswordInput doesn't render values for security — morph clears them."""
        inp = widget_page.locator('input[name="password"]')
        inp.fill("secret123")
        submit(widget_page)
        assert inp.input_value() == ""

    def test_morph_preserves_reveal_state(self, widget_page):
        """Show/hide toggle state persists through morph."""
        inp = widget_page.locator('input[name="password"]')
        inp.fill("secret")
        # Toggle to show
        widget_page.locator("label.input button").click()
        widget_page.wait_for_timeout(200)
        assert (
            widget_page.evaluate(
                "document.querySelector('input[name=\"password\"]').type",
            )
            == "text"
        )
        submit(widget_page)
        # After morph, show state persists (x-data preserved)
        assert (
            widget_page.evaluate(
                "document.querySelector('input[name=\"password\"]').type",
            )
            == "text"
        )

    def test_wrapper_has_id(self, widget_page):
        wrapper = widget_page.locator("label.input")
        assert wrapper.get_attribute("id") is not None
        assert "_wrapper" in wrapper.get_attribute("id")


class TestDataList:
    """DataList widget functionality and morph resilience."""

    def test_renders_with_datalist(self, widget_page):
        dl = widget_page.locator("datalist")
        assert dl.count() >= 1

    def test_has_list_attribute(self, widget_page):
        inp = widget_page.locator('input[name="datalist"]')
        list_attr = inp.get_attribute("list")
        assert list_attr is not None
        # The datalist element with that ID should exist
        dl = widget_page.locator(f"#{list_attr}")
        assert dl.count() == 1

    def test_datalist_has_options(self, widget_page):
        inp = widget_page.locator('input[name="datalist"]')
        list_id = inp.get_attribute("list")
        options = widget_page.locator(f"#{list_id} option")
        assert options.count() == 4  # Alpha, Beta, Gamma, Delta

    def test_fill_value(self, widget_page):
        inp = widget_page.locator('input[name="datalist"]')
        inp.fill("Custom value")
        assert inp.input_value() == "Custom value"

    def test_morph_preserves_value(self, widget_page):
        inp = widget_page.locator('input[name="datalist"]')
        inp.fill("Alpha")
        submit(widget_page)
        assert inp.input_value() == "Alpha"
