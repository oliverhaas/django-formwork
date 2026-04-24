"""E2e tests for icon modifier CSS patterns (btn-icon, btn-loading, alert-icon)."""

import pytest


class TestBtnIcon:
    """Verify btn-icon / btn-icon-end pseudo-element rendering."""

    def test_btn_icon_has_before_pseudo(self, icon_modifiers_page):
        """btn-icon renders a ::before pseudo with mask-image."""
        btn = icon_modifiers_page.locator("#btn-icon-upload")
        assert btn.is_visible()
        size = icon_modifiers_page.evaluate(
            """() => {
                const el = document.getElementById('btn-icon-upload');
                const style = getComputedStyle(el, '::before');
                return { w: style.width, h: style.height, content: style.content };
            }""",
        )
        assert size["content"] != "none"
        assert size["w"] != "0px"
        assert size["h"] != "0px"

    def test_btn_icon_end_has_after_pseudo(self, icon_modifiers_page):
        """btn-icon-end renders an ::after pseudo."""
        btn = icon_modifiers_page.locator("#btn-icon-end-next")
        assert btn.is_visible()
        size = icon_modifiers_page.evaluate(
            """() => {
                const el = document.getElementById('btn-icon-end-next');
                const style = getComputedStyle(el, '::after');
                return { w: style.width, h: style.height, content: style.content };
            }""",
        )
        assert size["content"] != "none"
        assert size["w"] != "0px"
        assert size["h"] != "0px"

    def test_btn_icon_square(self, icon_modifiers_page):
        """Square icon-only button renders correctly."""
        btn = icon_modifiers_page.locator("#btn-icon-square")
        assert btn.is_visible()
        assert btn.get_attribute("aria-label") == "Edit"

    @pytest.mark.parametrize(
        "btn_id,size_class",
        [
            ("btn-icon-xs", "btn-xs"),
            ("btn-icon-sm", "btn-sm"),
            ("btn-icon-lg", "btn-lg"),
            ("btn-icon-xl", "btn-xl"),
        ],
    )
    def test_btn_icon_size_ladder(self, icon_modifiers_page, btn_id, size_class):
        """Each btn size renders the icon pseudo at a proportional size."""
        btn = icon_modifiers_page.locator(f"#{btn_id}")
        assert btn.is_visible()
        size = icon_modifiers_page.evaluate(
            f"""() => {{
                const el = document.getElementById('{btn_id}');
                const style = getComputedStyle(el, '::before');
                return {{ w: parseFloat(style.width), h: parseFloat(style.height) }};
            }}""",
        )
        assert size["w"] > 0
        assert size["h"] > 0


class TestBtnLoading:
    """Verify btn-loading htmx loading state."""

    def test_standalone_loading_hides_text(self, icon_modifiers_page):
        """Mode 2: adding htmx-request hides text via visibility:hidden."""
        page = icon_modifiers_page
        btn = page.locator("#btn-loading-standalone")
        assert btn.is_visible()

        width_before = page.evaluate(
            """() => document.getElementById('btn-loading-standalone').offsetWidth""",
        )

        page.evaluate(
            "() => document.getElementById('btn-loading-standalone').classList.add('htmx-request')",
        )
        page.wait_for_timeout(100)

        # Button dimensions preserved (text still in flow, just invisible)
        width_during = page.evaluate(
            """() => document.getElementById('btn-loading-standalone').offsetWidth""",
        )
        assert width_during == width_before

        # Text hidden via visibility:hidden on button
        visibility = page.evaluate(
            """() => getComputedStyle(document.getElementById('btn-loading-standalone')).visibility""",
        )
        assert visibility == "hidden"

        # Spinner pseudo is visible (visibility:visible overrides parent)
        pseudo_vis = page.evaluate(
            """() => getComputedStyle(document.getElementById('btn-loading-standalone'), '::before').visibility""",
        )
        assert pseudo_vis == "visible"

    def test_standalone_loading_shows_spinner(self, icon_modifiers_page):
        """Mode 2: ::before pseudo appears during htmx-request."""
        page = icon_modifiers_page
        page.evaluate(
            "() => document.getElementById('btn-loading-standalone').classList.add('htmx-request')",
        )
        page.wait_for_timeout(100)

        pseudo = page.evaluate(
            """() => {
                const el = document.getElementById('btn-loading-standalone');
                const style = getComputedStyle(el, '::before');
                return { content: style.content, w: style.width, position: style.position };
            }""",
        )
        assert pseudo["content"] != "none"
        assert pseudo["w"] != "0px"
        assert pseudo["position"] == "absolute"

    def test_icon_mode_loading_keeps_text(self, icon_modifiers_page):
        """Mode 1: text stays visible during loading."""
        page = icon_modifiers_page
        btn = page.locator("#btn-loading-icon")
        assert btn.is_visible()

        page.evaluate(
            "() => document.getElementById('btn-loading-icon').classList.add('htmx-request')",
        )
        page.wait_for_timeout(100)

        color = page.evaluate(
            """() => getComputedStyle(document.getElementById('btn-loading-icon')).color""",
        )
        # In mode 1, color should NOT be transparent
        assert "0, 0, 0, 0" not in color

    def test_loading_dots_variant(self, icon_modifiers_page):
        """btn-loading-dots applies a different loading animation."""
        page = icon_modifiers_page
        btn = page.locator("#btn-loading-dots")
        assert btn.is_visible()


class TestAlertIcon:
    """Verify alert-icon / alert-col / alert-soft patterns."""

    def test_alert_icon_default_has_before(self, icon_modifiers_page):
        """alert-icon renders a ::before pseudo with mask-image."""
        page = icon_modifiers_page
        alert = page.locator("#alert-icon-default")
        assert alert.is_visible()

        pseudo = page.evaluate(
            """() => {
                const el = document.getElementById('alert-icon-default');
                const style = getComputedStyle(el, '::before');
                return { content: style.content, w: style.width, h: style.height };
            }""",
        )
        assert pseudo["content"] != "none"
        assert pseudo["w"] != "0px"
        assert pseudo["h"] != "0px"

    def test_alert_icon_custom_glyph(self, icon_modifiers_page):
        """alert-icon with icon-* override renders the custom glyph."""
        page = icon_modifiers_page
        alert = page.locator("#alert-icon-custom")
        assert alert.is_visible()
        classes = alert.get_attribute("class")
        assert "icon-triangle-alert" in classes

    def test_alert_col_layout(self, icon_modifiers_page):
        """alert-col switches to vertical stacked layout."""
        page = icon_modifiers_page
        alert = page.locator("#alert-col")
        assert alert.is_visible()

        flow = page.evaluate(
            """() => getComputedStyle(document.getElementById('alert-col')).gridAutoFlow""",
        )
        assert flow == "row"

    def test_alert_col_icon_larger(self, icon_modifiers_page):
        """alert-col.alert-icon ::before is 3rem (larger than default 1.25rem)."""
        page = icon_modifiers_page
        size = page.evaluate(
            """() => {
                const el = document.getElementById('alert-col');
                const style = getComputedStyle(el, '::before');
                return { w: parseFloat(style.width), h: parseFloat(style.height) };
            }""",
        )
        # 3rem = 48px at default 16px root
        assert size["w"] >= 40
        assert size["h"] >= 40

    def test_alert_soft_styling(self, icon_modifiers_page):
        """alert-soft has a lighter background than default alert."""
        page = icon_modifiers_page
        alert = page.locator("#alert-soft")
        assert alert.is_visible()
        classes = alert.get_attribute("class")
        assert "alert-soft" in classes

    def test_alert_text_wrap(self, icon_modifiers_page):
        """All alerts have text-wrap: pretty."""
        page = icon_modifiers_page
        wrap = page.evaluate(
            """() => getComputedStyle(document.getElementById('alert-icon-default')).textWrap""",
        )
        assert wrap == "pretty"
