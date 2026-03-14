"""E2e tests for simple custom widgets: Toggle, Range, PasswordReveal, DataList."""

from percy import percy_snapshot

from .conftest import submit


class TestToggle:
    """Toggle switch widget functionality and morph resilience."""

    def test_renders(self, simple_page):
        toggle = simple_page.locator('input[name="toggle"]')
        assert toggle.count() == 1

    def test_toggle_on_off(self, simple_page):
        toggle = simple_page.locator('input[name="toggle"]')
        assert not toggle.is_checked()
        toggle.click()
        assert toggle.is_checked()
        percy_snapshot(simple_page, "Toggle - Checked")
        toggle.click()
        assert not toggle.is_checked()

    def test_morph_preserves_checked(self, simple_page):
        toggle = simple_page.locator('input[name="toggle"]')
        toggle.check()
        assert toggle.is_checked()
        submit(simple_page)
        assert simple_page.locator('input[name="toggle"]').is_checked()

    def test_morph_preserves_unchecked(self, simple_page):
        toggle = simple_page.locator('input[name="toggle"]')
        assert not toggle.is_checked()
        submit(simple_page)
        assert not simple_page.locator('input[name="toggle"]').is_checked()


class TestRange:
    """Range slider widget functionality and morph resilience."""

    def test_renders_with_attrs(self, simple_page):
        rng = simple_page.locator('input[name="volume"]')
        assert rng.get_attribute("type") == "range"
        assert rng.get_attribute("min") == "0"
        assert rng.get_attribute("max") == "100"
        assert rng.get_attribute("step") == "10"

    def test_set_value(self, simple_page):
        simple_page.evaluate("""
            const r = document.querySelector('input[name="volume"]');
            r.value = '70';
            r.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        assert simple_page.locator('input[name="volume"]').input_value() == "70"

    def test_morph_preserves_value(self, simple_page):
        simple_page.evaluate("""
            const r = document.querySelector('input[name="volume"]');
            r.value = '70';
            r.dispatchEvent(new Event('input', {bubbles: true}));
        """)
        submit(simple_page)
        assert simple_page.locator('input[name="volume"]').input_value() == "70"


class TestPasswordReveal:
    """PasswordReveal widget functionality and morph resilience."""

    def test_renders(self, simple_page):
        inp = simple_page.locator('input[name="password"]')
        assert inp.is_visible()

    def test_type_password(self, simple_page):
        inp = simple_page.locator('input[name="password"]')
        assert inp.get_attribute("type") == "password"

    def test_toggle_visibility(self, simple_page):
        inp = simple_page.locator('input[name="password"]')
        assert inp.get_attribute("type") == "password"
        simple_page.locator("label.password-reveal button").click()
        simple_page.wait_for_timeout(100)
        assert inp.get_attribute("type") == "text"
        percy_snapshot(simple_page, "PasswordReveal - Revealed")
        simple_page.locator("label.password-reveal button").click()
        simple_page.wait_for_timeout(100)
        assert inp.get_attribute("type") == "password"

    def test_morph_clears_value(self, simple_page):
        """Django's PasswordInput doesn't render values for security."""
        inp = simple_page.locator('input[name="password"]')
        inp.fill("secret123")
        submit(simple_page)
        assert inp.input_value() == ""

    def test_morph_preserves_reveal_state(self, simple_page):
        """Show/hide toggle state persists through morph."""
        inp = simple_page.locator('input[name="password"]')
        inp.fill("secret")
        simple_page.locator("label.password-reveal button").click()
        simple_page.wait_for_timeout(200)
        assert (
            simple_page.evaluate(
                "document.querySelector('input[name=\"password\"]').type",
            )
            == "text"
        )
        submit(simple_page)
        assert (
            simple_page.evaluate(
                "document.querySelector('input[name=\"password\"]').type",
            )
            == "text"
        )

    def test_wrapper_has_id(self, simple_page):
        wrapper = simple_page.locator("label.password-reveal")
        assert wrapper.get_attribute("id") is not None
        assert "_wrapper" in wrapper.get_attribute("id")


class TestDataList:
    """DataList widget functionality and morph resilience."""

    def test_renders_with_datalist(self, simple_page):
        dl = simple_page.locator("datalist")
        assert dl.count() >= 1

    def test_has_list_attribute(self, simple_page):
        inp = simple_page.locator('input[name="browser"]')
        list_attr = inp.get_attribute("list")
        assert list_attr is not None
        dl = simple_page.locator(f"#{list_attr}")
        assert dl.count() == 1

    def test_datalist_has_options(self, simple_page):
        inp = simple_page.locator('input[name="browser"]')
        list_id = inp.get_attribute("list")
        options = simple_page.locator(f"#{list_id} option")
        assert options.count() == 5  # Chrome, Firefox, Safari, Edge, Opera

    def test_fill_value(self, simple_page):
        inp = simple_page.locator('input[name="browser"]')
        inp.fill("Custom value")
        assert inp.input_value() == "Custom value"

    def test_morph_preserves_value(self, simple_page):
        inp = simple_page.locator('input[name="browser"]')
        inp.fill("Chrome")
        submit(simple_page)
        assert inp.input_value() == "Chrome"
