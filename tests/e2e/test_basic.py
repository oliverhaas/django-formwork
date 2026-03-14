"""E2e tests for standard Django widgets on the Basic Forms page."""

from percy import percy_snapshot

from .conftest import submit


class TestTextInput:
    """TextInput widget functionality and morph resilience."""

    def test_renders(self, basic_page):
        inp = basic_page.locator('input[name="name"]')
        assert inp.is_visible()

    def test_placeholder(self, basic_page):
        inp = basic_page.locator('input[name="name"]')
        assert inp.get_attribute("placeholder") == "Your name"

    def test_fill_value(self, basic_page):
        inp = basic_page.locator('input[name="name"]')
        inp.fill("Hello World")
        assert inp.input_value() == "Hello World"

    def test_submit_empty_shows_error(self, basic_page):
        submit(basic_page)
        tooltip = basic_page.locator("#id_name_tooltip")
        assert tooltip.count() == 1

    def test_submit_valid_clears_error(self, basic_page):
        submit(basic_page)
        assert basic_page.locator("#id_name_tooltip").count() == 1
        basic_page.locator('input[name="name"]').fill("Valid text")
        submit(basic_page)
        assert basic_page.locator("#id_name_tooltip").count() == 0

    def test_morph_preserves_value(self, basic_page):
        inp = basic_page.locator('input[name="name"]')
        inp.fill("Hello World")
        submit(basic_page)
        assert inp.input_value() == "Hello World"


class TestEmailInput:
    """EmailInput widget functionality and morph resilience."""

    def test_renders(self, basic_page):
        inp = basic_page.locator('input[name="email"]')
        assert inp.is_visible()
        assert inp.get_attribute("type") == "email"

    def test_submit_empty_shows_error(self, basic_page):
        submit(basic_page)
        errors = basic_page.locator("#id_email_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, basic_page):
        inp = basic_page.locator('input[name="email"]')
        inp.fill("test@example.com")
        submit(basic_page)
        assert inp.input_value() == "test@example.com"


class TestTextarea:
    """Textarea widget functionality and morph resilience."""

    def test_renders(self, basic_page):
        ta = basic_page.locator('textarea[name="message"]')
        assert ta.is_visible()

    def test_rows_attr(self, basic_page):
        ta = basic_page.locator('textarea[name="message"]')
        assert ta.get_attribute("rows") == "3"

    def test_fill_value(self, basic_page):
        ta = basic_page.locator('textarea[name="message"]')
        ta.fill("Multiline\ntext")
        assert ta.input_value() == "Multiline\ntext"

    def test_submit_empty_shows_error(self, basic_page):
        submit(basic_page)
        errors = basic_page.locator("#id_message_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, basic_page):
        ta = basic_page.locator('textarea[name="message"]')
        ta.fill("Multiline\ntext content")
        submit(basic_page)
        assert ta.input_value() == "Multiline\ntext content"


class TestSelect:
    """Select widget functionality and morph resilience."""

    def test_renders_with_options(self, basic_page):
        sel = basic_page.locator('select[name="priority"]')
        assert sel.is_visible()
        options = sel.locator("option")
        assert options.count() == 4  # empty + 3 choices

    def test_select_option(self, basic_page):
        sel = basic_page.locator('select[name="priority"]')
        sel.select_option("medium")
        assert sel.input_value() == "medium"

    def test_submit_empty_shows_error(self, basic_page):
        submit(basic_page)
        errors = basic_page.locator("#id_priority_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, basic_page):
        sel = basic_page.locator('select[name="priority"]')
        sel.select_option("medium")
        submit(basic_page)
        assert sel.input_value() == "medium"


class TestRadioSelect:
    """RadioSelect widget functionality and morph resilience."""

    def test_renders_options(self, basic_page):
        radios = basic_page.locator('input[name="notify"]')
        assert radios.count() == 3

    def test_select_option(self, basic_page):
        radio = basic_page.locator('input[name="notify"][value="sms"]')
        radio.click(force=True)
        assert radio.is_checked()

    def test_submit_empty_shows_error(self, basic_page):
        submit(basic_page)
        invalid = basic_page.locator('input[name="notify"][aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_morph_preserves_value(self, basic_page):
        basic_page.evaluate("""
            const radio = document.querySelector('input[name="notify"][value="sms"]');
            radio.checked = true;
            radio.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        submit(basic_page)
        checked = basic_page.evaluate(
            'document.querySelector(\'input[name="notify"]:checked\')?.value || ""',
        )
        assert checked == "sms"


class TestCheckbox:
    """Checkbox widget functionality and morph resilience."""

    def test_renders(self, basic_page):
        cb = basic_page.locator('input[name="agree"]')
        assert cb.count() == 1

    def test_toggle_checked(self, basic_page):
        cb = basic_page.locator('input[name="agree"]')
        assert not cb.is_checked()
        cb.click()
        assert cb.is_checked()
        percy_snapshot(basic_page, "Checkbox - Checked")

    def test_submit_unchecked_shows_error(self, basic_page):
        submit(basic_page)
        errors = basic_page.locator("#id_agree_errors")
        assert errors.count() == 1

    def test_morph_preserves_checked(self, basic_page):
        cb = basic_page.locator('input[name="agree"]')
        cb.check()
        submit(basic_page)
        assert basic_page.locator('input[name="agree"]').is_checked()


class TestFileInput:
    """FileInput widget rendering."""

    def test_renders(self, basic_page):
        inp = basic_page.locator('input[name="attachment"]')
        assert inp.count() == 1

    def test_has_file_type(self, basic_page):
        inp = basic_page.locator('input[name="attachment"]')
        assert inp.get_attribute("type") == "file"
