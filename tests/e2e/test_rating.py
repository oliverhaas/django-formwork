"""E2e tests for Rating widget variations."""

from percy import percy_snapshot

from .conftest import submit


class TestRating5Stars:
    """Classic 5-star rating widget."""

    def test_renders_stars(self, rating_page):
        rating = rating_page.locator("#id_stars_5")
        stars = rating.locator('input[type="radio"]')
        assert stars.count() == 5
        percy_snapshot(rating_page, "Rating - Default")

    def test_click_selects_star(self, rating_page):
        rating = rating_page.locator("#id_stars_5")
        third_star = rating.locator('input[type="radio"]').nth(2)
        third_star.click(force=True)
        assert third_star.is_checked()
        percy_snapshot(rating_page, "Rating - 3 Stars")

    def test_morph_preserves_value(self, rating_page):
        rating_page.evaluate("""
            const star = document.querySelector('#id_stars_5 input[value="3"]');
            star.checked = true;
            star.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        submit(rating_page)
        checked = rating_page.evaluate(
            "document.querySelector('#id_stars_5 input:checked')?.value || ''",
        )
        assert checked == "3"

    def test_has_mask_star_class(self, rating_page):
        star = rating_page.locator('#id_stars_5 input[type="radio"]').first
        cls = star.get_attribute("class") or ""
        assert "mask-star-2" in cls


class TestRating3Stars:
    """3-star rating variant."""

    def test_renders_3_stars(self, rating_page):
        rating = rating_page.locator("#id_stars_3")
        stars = rating.locator('input[type="radio"]')
        assert stars.count() == 3

    def test_click_selects_star(self, rating_page):
        rating = rating_page.locator("#id_stars_3")
        second_star = rating.locator('input[type="radio"]').nth(1)
        second_star.click(force=True)
        assert second_star.is_checked()


class TestRatingHearts:
    """Heart-shaped rating variant."""

    def test_renders_hearts(self, rating_page):
        rating = rating_page.locator("#id_hearts")
        stars = rating.locator('input[type="radio"]')
        assert stars.count() == 5

    def test_has_mask_heart_class(self, rating_page):
        star = rating_page.locator('#id_hearts input[type="radio"]').first
        cls = star.get_attribute("class") or ""
        assert "mask-heart" in cls
        percy_snapshot(rating_page, "Rating - Hearts")

    def test_click_selects_heart(self, rating_page):
        rating = rating_page.locator("#id_hearts")
        fourth_heart = rating.locator('input[type="radio"]').nth(3)
        fourth_heart.click(force=True)
        assert fourth_heart.is_checked()


class TestRatingClearable:
    """Clearable rating variant (required=False, allow_clear=True)."""

    def test_renders(self, rating_page):
        rating = rating_page.locator("#id_clearable")
        stars = rating.locator('input[type="radio"]')
        # allow_clear adds a hidden "clear" radio at index 0
        assert stars.count() >= 5

    def test_no_error_when_empty(self, rating_page):
        """Clearable rating is not required — no error on empty submit."""
        submit(rating_page)
        tooltip = rating_page.locator("#id_clearable_tooltip")
        assert tooltip.count() == 0
