"""E2e tests for simple custom widgets: Range, PasswordReveal, DataList, Rating.

Toggle has been migrated to tests/widgets/test_toggle.py as the canonical
exemplar.
"""

from .conftest import submit


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


class TestRating:
    """Star rating widget (5 stars, required)."""

    def test_renders_5_stars(self, simple_page):
        rating = simple_page.locator("#id_stars")
        stars = rating.locator('input[type="radio"]')
        assert stars.count() == 5

    def test_click_selects_star(self, simple_page):
        rating = simple_page.locator("#id_stars")
        third_star = rating.locator('input[type="radio"]').nth(2)
        third_star.click(force=True)
        assert third_star.is_checked()

    def test_has_mask_star_class(self, simple_page):
        star = simple_page.locator('#id_stars input[type="radio"]').first
        cls = star.get_attribute("class") or ""
        assert "mask-star-2" in cls

    def test_morph_preserves_value(self, simple_page):
        simple_page.evaluate("""
            const star = document.querySelector('#id_stars input[value="3"]');
            star.checked = true;
            star.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        submit(simple_page)
        checked = simple_page.evaluate(
            "document.querySelector('#id_stars input:checked')?.value || ''",
        )
        assert checked == "3"


class TestClearableRating:
    """Clearable rating variant (required=False, allow_clear=True)."""

    def test_renders_with_hidden_clear_option(self, simple_page):
        rating = simple_page.locator("#id_clearable_rating")
        stars = rating.locator('input[type="radio"]:not(.rating-hidden)')
        assert stars.count() == 5
        # Hidden clear radio is the first input inside .rating
        hidden = rating.locator("input.rating-hidden")
        assert hidden.count() == 1

    def test_hidden_clear_option_clears_selection(self, simple_page):
        # Select a star first
        simple_page.evaluate("""
            const star = document.querySelector('#id_clearable_rating input[value="3"]');
            star.checked = true;
            star.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        checked = simple_page.evaluate(
            "document.querySelector('#id_clearable_rating input:checked')?.value || ''",
        )
        assert checked == "3"
        # Click the hidden clear option (DaisyUI rating-hidden)
        simple_page.evaluate("""
            const hidden = document.querySelector('#id_clearable_rating .rating-hidden');
            hidden.checked = true;
            hidden.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        checked = simple_page.evaluate(
            "document.querySelector('#id_clearable_rating input:checked')?.value || ''",
        )
        assert checked == ""

    def test_no_error_when_empty(self, simple_page):
        """Clearable rating is not required — no error on empty submit."""
        submit(simple_page)
        tooltip = simple_page.locator("#id_clearable_rating_tooltip")
        assert tooltip.count() == 0
