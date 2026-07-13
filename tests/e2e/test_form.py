"""Form structure and morph infrastructure tests."""

from playwright.sync_api import expect

from .conftest import submit


def _after_content(page, selector):
    """Return the CSS ``content`` of an element's ``::after`` (the [more]/[less]
    affordance), e.g. ``'"[more]"'`` or ``'none'``."""
    return page.evaluate(
        "(sel) => getComputedStyle(document.querySelector(sel), '::after').content",
        selector,
    )


def _is_expandable(page, selector):
    """Whether measureDisclosures marked the <details> as having something to reveal."""
    return page.evaluate(
        "(sel) => document.querySelector(sel).hasAttribute('data-expandable')",
        selector,
    )


def _is_open(page, selector):
    return page.evaluate("(sel) => document.querySelector(sel).open", selector)


class TestFormStructure:
    """Form renders correctly with all expected structural elements."""

    def test_page_loads(self, basic_page):
        assert basic_page.title() == "Basic Form"

    def test_form_renders(self, basic_page):
        form = basic_page.locator("#basic-form")
        assert form.is_visible()

    def test_fieldset_wrappers(self, basic_page):
        fieldsets = basic_page.locator("#basic-form fieldset.fieldset")
        assert fieldsets.count() >= 5

    def test_labels_render(self, basic_page):
        labels = basic_page.locator("#basic-form .fieldset-legend")
        assert labels.count() >= 5

    def test_help_text_renders(self, basic_page):
        help_text = basic_page.locator("#id_name_helptext")
        assert help_text.is_visible()
        assert "textinput" in help_text.text_content().lower()

    def test_required_asterisk(self, basic_page):
        asterisks = basic_page.locator("#basic-form .text-error")
        assert asterisks.count() >= 1

    def test_submit_empty_shows_errors(self, basic_page):
        submit(basic_page)
        errors = basic_page.locator("#basic-form details.formwork-errors")
        assert errors.count() >= 1

    def test_error_has_role_alert(self, basic_page):
        submit(basic_page)
        alerts = basic_page.locator('#basic-form [role="alert"]')
        assert alerts.count() >= 1

    def test_aria_invalid_set(self, basic_page):
        submit(basic_page)
        invalid = basic_page.locator('#basic-form [aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_novalidate_set_on_form_with_errors(self, basic_page):
        """formwork.js disables native validation after errors appear via morph."""
        submit(basic_page)
        no_validate = basic_page.evaluate(
            "document.querySelector('#basic-form').noValidate",
        )
        assert no_validate is True


class TestHelpTextToggle:
    """Help text lives in a native <details>; when it overflows one line the
    summary gains a [more]/[less] affordance and truncates while closed."""

    def _narrow(self, basic_page):
        basic_page.set_viewport_size({"width": 480, "height": 720})
        basic_page.reload()
        basic_page.wait_for_load_state("domcontentloaded")
        basic_page.wait_for_timeout(300)

    def test_no_affordance_when_text_fits(self, basic_page):
        """The "message" help fits one line, so measureDisclosures leaves it
        non-expandable: no [more] on the summary."""
        disclosure = "#id_message_disclosure"
        assert _is_expandable(basic_page, disclosure) is False
        assert _after_content(basic_page, f"{disclosure} > summary") == "none"

    def test_affordance_shown_when_text_overflows(self, basic_page):
        self._narrow(basic_page)
        disclosure = "#id_agree_disclosure"
        assert _is_expandable(basic_page, disclosure) is True
        assert _after_content(basic_page, f"{disclosure} > summary") == '"[more]"'

    def test_affordance_re_derived_on_resize_without_reload(self, basic_page):
        """Overflow is re-measured on viewport resize (the same code path that
        re-runs once web fonts load, which previously left overflowing rows
        wrongly non-expandable). A help row that fits while wide gains [more]
        when the viewport narrows, with no reload, and stays a single line."""
        disclosure = "#id_message_disclosure"
        basic_page.set_viewport_size({"width": 1280, "height": 720})
        basic_page.wait_for_function(
            "() => !document.querySelector('#id_message_disclosure')"
            ".hasAttribute('data-expandable')",
        )
        # Narrow past the point where the multi-word help fits one line.
        basic_page.set_viewport_size({"width": 400, "height": 720})
        basic_page.wait_for_function(
            "() => document.querySelector('#id_message_disclosure')"
            ".hasAttribute('data-expandable')",
        )
        assert _after_content(basic_page, f"{disclosure} > summary") == '"[more]"'
        # Truncated to one line, not wrapped to two.
        height = basic_page.locator(f"{disclosure} > summary").bounding_box()["height"]
        assert height < 30

    def test_click_expands_and_collapses(self, basic_page):
        self._narrow(basic_page)
        disclosure = "#id_agree_disclosure"
        summary = basic_page.locator(f"{disclosure} > summary")

        assert _is_open(basic_page, disclosure) is False

        summary.click()
        assert _is_open(basic_page, disclosure) is True
        assert _after_content(basic_page, f"{disclosure} > summary") == '"[less]"'

        summary.click()
        assert _is_open(basic_page, disclosure) is False
        assert _after_content(basic_page, f"{disclosure} > summary") == '"[more]"'

    def test_expanded_state_survives_morph(self, basic_page):
        """Regression: an expanded disclosure used to collapse on the validation
        swap because Alpine re-ran the collapsed server markup.  Native <details
        open> is in htmx.config.morphIgnore, so it now stays open across the morph."""
        self._narrow(basic_page)
        disclosure = "#id_agree_disclosure"
        basic_page.locator(f"{disclosure} > summary").click()
        assert _is_open(basic_page, disclosure) is True

        submit(basic_page)

        assert _is_open(basic_page, disclosure) is True

    def test_expanded_icon_aligns_to_top(self, basic_page):
        """When expanded the leading icon pins to the first text line (top of
        the wrapped row) rather than centering."""
        self._narrow(basic_page)
        disclosure = "#id_agree_disclosure"
        basic_page.locator(f"{disclosure} > summary").click()

        icon_box = basic_page.locator(f"{disclosure} > summary > i").bounding_box()
        summary_box = basic_page.locator(f"{disclosure} > summary").bounding_box()
        assert abs(icon_box["y"] - summary_box["y"]) <= 4


class TestInlineErrorToggle:
    """Meta.error_display = "inline": the error renders in the summary (red, with
    a circle-x icon); help text moves into the <details> body, revealed with [more]."""

    def test_no_tooltip_wrapper(self, inline_errors_page):
        submit(inline_errors_page)
        assert inline_errors_page.locator("#inline-errors-form .tooltip").count() == 0

    def test_error_visible_help_hidden_when_collapsed(self, inline_errors_page):
        submit(inline_errors_page)
        error = inline_errors_page.locator("#id_name_error")
        helptext = inline_errors_page.locator("#id_name_helptext")
        expect(error).to_be_visible()
        # Help text is the <details> body, hidden while the disclosure is closed.
        expect(helptext).not_to_be_visible()

    def test_click_more_reveals_error_and_help_text_together(self, inline_errors_page):
        submit(inline_errors_page)
        disclosure = "#id_name_disclosure"
        summary = inline_errors_page.locator(f"{disclosure} > summary")
        assert _after_content(inline_errors_page, f"{disclosure} > summary") == '"[more]"'

        summary.click()
        assert _after_content(inline_errors_page, f"{disclosure} > summary") == '"[less]"'
        helptext = inline_errors_page.locator("#id_name_helptext")
        expect(helptext).to_be_visible()
        assert "government-issued" in helptext.text_content()

    def test_click_less_collapses_help_text_again(self, inline_errors_page):
        submit(inline_errors_page)
        disclosure = "#id_name_disclosure"
        summary = inline_errors_page.locator(f"{disclosure} > summary")
        summary.click()
        summary.click()
        assert _after_content(inline_errors_page, f"{disclosure} > summary") == '"[more]"'
        expect(inline_errors_page.locator("#id_name_helptext")).not_to_be_visible()

    def test_native_first_real_click_shows_inline_error(self, inline_errors_page):
        # No noValidate cheat: the real native-first click path. "Alice" is
        # native-valid (non-empty, >=3 chars) so it clears the browser gate; the
        # server-only clean_name then rejects the single word and renders inline.
        page = inline_errors_page
        page.locator("#id_name").fill("Alice")
        page.locator("form[hx-post] button[type='submit']").click()
        error_row = page.locator("#id_name_error")
        expect(error_row).to_be_visible()
        expect(error_row).to_contain_text("Enter your full name: first and last.")
        # The formwork-errors hook on the inline error disables native
        # validation (parity with tooltip mode), so later submits route every
        # error to the server instead of showing a native browser bubble.
        page.wait_for_function("() => document.querySelector('form[hx-post]').noValidate === true")


class TestMorphInfrastructure:
    """Verify htmx 4 morph swap and the formwork-morph extension are registered."""

    def test_htmx_loaded(self, basic_page):
        assert basic_page.evaluate("typeof htmx") == "object"

    def test_formwork_morph_extension_registered(self, basic_page):
        assert (
            basic_page.evaluate(
                "htmx.config.morphIgnore && htmx.config.morphIgnore.includes('x-data')",
            )
            is True
        )

    def test_morph_swap_works(self, basic_page):
        """After htmx POST, errors appear (form morphed in place)."""
        submit(basic_page)
        count = basic_page.evaluate(
            'document.querySelectorAll("#basic-form [aria-invalid]").length',
        )
        assert count >= 1

    def test_form_id_preserved(self, basic_page):
        submit(basic_page)
        assert basic_page.locator("#basic-form").count() == 1

    def test_csrf_token_exists(self, basic_page):
        submit(basic_page)
        token = basic_page.evaluate(
            "document.querySelector('#basic-form input[name=\"csrfmiddlewaretoken\"]').value",
        )
        assert token

    def test_no_duplicate_forms(self, basic_page):
        submit(basic_page)
        submit(basic_page)
        assert basic_page.locator("#basic-form").count() == 1

    def test_second_morph_clears_errors(self, basic_page):
        """Fill required fields and re-submit, errors should disappear."""
        submit(basic_page)
        assert basic_page.locator("#basic-form details.formwork-errors").count() >= 1

        # Fill all required fields on the basic form
        basic_page.locator('input[name="name"]').fill("Alice")
        basic_page.locator('input[name="email"]').fill("a@b.com")
        basic_page.locator('input[name="agree"]').check()
        submit(basic_page)
        # Name field errors should be gone
        name_errors = basic_page.locator("#id_name_error")
        assert name_errors.count() == 0
