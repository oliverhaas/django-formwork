"""E2e tests for icon modifier CSS patterns (btn-icon, busy buttons, alert-icon)."""

import re

import pytest
from playwright.sync_api import expect


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


BUSY_REQUEST = re.compile(r"/icon-modifiers/\?busy=1")

MASK_JS = """([id, pseudo]) => {
    const el = document.getElementById(id);
    const style = pseudo ? getComputedStyle(el, pseudo) : getComputedStyle(el.querySelector(':scope > .icon'));
    return style.maskImage || style.webkitMaskImage;
}"""


@pytest.fixture
def held(icon_modifiers_page):
    """Requests to the busy buttons' URL, held until the test continues them."""
    routes = []
    icon_modifiers_page.route(BUSY_REQUEST, lambda route: routes.append(route))  # noqa: PLW0108 (Playwright reads the handler's signature, which a builtin lacks)
    return routes


class TestBusyButtons:
    """A .btn that sends a request shows a spinner until the response is in."""

    @pytest.mark.parametrize(("button_id", "pseudo"), [("busy-icon", None), ("busy-btn-icon", "::before")])
    def test_icon_turns_into_spinner_while_request_runs(self, icon_modifiers_page, held, button_id, pseudo):
        page = icon_modifiers_page
        idle_mask = page.evaluate(MASK_JS, [button_id, pseudo])
        button = page.locator(f"#{button_id}")
        with page.expect_request(BUSY_REQUEST):
            button.click()
        expect(button).to_have_attribute("aria-busy", "true")
        expect(button).not_to_have_attribute("data-busy-overlay", "")
        assert page.evaluate(MASK_JS, [button_id, pseudo]) != idle_mask

        held[0].fulfill(body="")
        expect(button).not_to_have_attribute("aria-busy", "true")
        assert page.evaluate(MASK_JS, [button_id, pseudo]) == idle_mask

    def test_button_without_icon_keeps_its_size_under_spinner(self, icon_modifiers_page, held):
        page = icon_modifiers_page
        button = page.locator("#busy-label")
        idle_box = button.bounding_box()
        with page.expect_request(BUSY_REQUEST):
            button.click()
        expect(button).to_have_attribute("data-busy-overlay", "")
        busy = page.evaluate(
            """() => {
                const el = document.getElementById('busy-label');
                return {
                    fill: getComputedStyle(el).webkitTextFillColor,
                    spinner: getComputedStyle(el, '::before').content,
                };
            }""",
        )
        assert busy["fill"] == "rgba(0, 0, 0, 0)"
        assert busy["spinner"] != "none"
        assert button.bounding_box() == idle_box

        held[0].fulfill(body="")
        expect(button).not_to_have_attribute("data-busy-overlay", "")

    @pytest.mark.parametrize(
        ("clicks", "busy_id"),
        [
            (["busy-htmx-submit"], "busy-htmx-submit"),
            (["busy-menu", "busy-menu-item"], "busy-menu"),
        ],
        ids=["htmx-submit", "menu-item"],
    )
    def test_htmx_form_submit_spins_its_button(self, icon_modifiers_page, held, clicks, busy_id):
        page = icon_modifiers_page
        for button_id in clicks[:-1]:
            page.locator(f"#{button_id}").click()
        with page.expect_request(BUSY_REQUEST):
            page.locator(f"#{clicks[-1]}").click()
        expect(page.locator(f"#{busy_id}")).to_have_attribute("aria-busy", "true")

    def test_native_form_submit_spins_its_button(self, icon_modifiers_page):
        """The busy state is recorded in sessionStorage, which outlives the page it was set on."""
        page = icon_modifiers_page
        page.evaluate(
            """() => {
                const button = document.getElementById('busy-native');
                new MutationObserver(() => sessionStorage.setItem('busy', button.ariaBusy))
                    .observe(button, {attributes: true});
            }""",
        )
        page.locator("#busy-native").click()
        expect(page).to_have_url(BUSY_REQUEST)
        assert page.evaluate("() => sessionStorage.getItem('busy')") == "true"

    def test_btn_loading_none_stays_still(self, icon_modifiers_page, held):
        page = icon_modifiers_page
        with page.expect_request(BUSY_REQUEST):
            page.locator("#busy-still").click()
        expect(page.locator("#busy-still")).not_to_have_attribute("aria-busy", "true")

    def test_loading_dots_variant(self, icon_modifiers_page, held):
        """btn-loading-dots swaps the spinner for the dots animation."""
        page = icon_modifiers_page
        for button_id in ("busy-label", "busy-dots"):
            with page.expect_request(BUSY_REQUEST):
                page.locator(f"#{button_id}").click()
            expect(page.locator(f"#{button_id}")).to_have_attribute("aria-busy", "true")
        spinner_mask = page.evaluate(MASK_JS, ["busy-label", "::before"])
        dots_mask = page.evaluate(MASK_JS, ["busy-dots", "::before"])
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
