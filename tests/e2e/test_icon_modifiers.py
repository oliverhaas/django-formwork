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
        """Icon-only square button is visible and keeps its aria-label."""
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
        """Mode 2: adding htmx-request hides text via color:transparent."""
        page = icon_modifiers_page
        btn = page.locator("#btn-loading-standalone")
        assert btn.is_visible()

        width_before = page.evaluate(
            """() => document.getElementById('btn-loading-standalone').offsetWidth""",
        )

        page.evaluate(
            "() => document.getElementById('btn-loading-standalone').classList.add('htmx-request')",
        )
        page.wait_for_timeout(600)

        # Button dimensions preserved (text still in flow, just invisible)
        width_during = page.evaluate(
            """() => document.getElementById('btn-loading-standalone').offsetWidth""",
        )
        assert width_during == width_before

        # Text color is transparent
        color = page.evaluate(
            """() => getComputedStyle(document.getElementById('btn-loading-standalone')).color""",
        )
        assert "0, 0, 0, 0" in color or color == "transparent"

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
        """btn-loading-dots swaps the spinner mask for the dots animation."""
        page = icon_modifiers_page
        btn = page.locator("#btn-loading-dots")
        assert btn.is_visible()

        page.evaluate(
            """() => ['btn-loading-standalone', 'btn-loading-dots'].forEach(
                (id) => document.getElementById(id).classList.add('htmx-request'))""",
        )
        spinner_mask, dots_mask = page.evaluate(
            """() => ['btn-loading-standalone', 'btn-loading-dots'].map((id) => {
                const style = getComputedStyle(document.getElementById(id), '::before');
                return style.maskImage || style.webkitMaskImage;
            })""",
        )
        assert dots_mask not in ("", "none")
        assert dots_mask != spinner_mask


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
        """alert-icon with icon-* override renders a different ::before glyph than the default."""
        page = icon_modifiers_page
        alert = page.locator("#alert-icon-custom")
        assert alert.is_visible()
        default_mask, custom_mask = page.evaluate(
            """() => ['alert-icon-default', 'alert-icon-custom'].map((id) => {
                const style = getComputedStyle(document.getElementById(id), '::before');
                return style.maskImage || style.webkitMaskImage;
            })""",
        )
        assert custom_mask not in ("", "none")
        assert custom_mask != default_mask

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
        """alert-soft tints the background differently from a same-color default alert."""
        page = icon_modifiers_page
        alert = page.locator("#alert-soft")
        assert alert.is_visible()
        # Compare against a synthetic plain alert-info sibling, isolating the tint.
        soft_bg, default_bg = page.evaluate(
            """() => {
                const soft = document.getElementById('alert-soft');
                const plain = document.createElement('div');
                plain.className = 'alert alert-info alert-icon';
                soft.parentElement.appendChild(plain);
                const colors = [
                    getComputedStyle(soft).backgroundColor,
                    getComputedStyle(plain).backgroundColor,
                ];
                plain.remove();
                return colors;
            }""",
        )
        assert soft_bg not in ("", "rgba(0, 0, 0, 0)")
        assert soft_bg != default_bg

    def test_alert_text_wrap(self, icon_modifiers_page):
        """All alerts have text-wrap: pretty."""
        page = icon_modifiers_page
        wrap = page.evaluate(
            """() => getComputedStyle(document.getElementById('alert-icon-default')).textWrap""",
        )
        assert wrap == "pretty"
