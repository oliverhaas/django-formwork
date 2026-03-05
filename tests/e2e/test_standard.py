"""E2e tests for standard Django widgets: TextInput, Email, Textarea, Select, Radio, Checkbox, File."""

from .conftest import submit


class TestTextInput:
    """TextInput widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        inp = widget_page.locator('input[name="text"]')
        assert inp.is_visible()

    def test_placeholder(self, widget_page):
        inp = widget_page.locator('input[name="text"]')
        assert inp.get_attribute("placeholder") == "Type here"

    def test_fill_value(self, widget_page):
        inp = widget_page.locator('input[name="text"]')
        inp.fill("Hello World")
        assert inp.input_value() == "Hello World"

    def test_submit_empty_shows_error(self, widget_page):
        submit(widget_page)
        tooltip = widget_page.locator("#id_text_tooltip")
        assert tooltip.count() == 1

    def test_submit_valid_clears_error(self, widget_page):
        submit(widget_page)
        assert widget_page.locator("#id_text_tooltip").count() == 1
        # Fill and re-submit
        widget_page.locator('input[name="text"]').fill("Valid text")
        submit(widget_page)
        assert widget_page.locator("#id_text_tooltip").count() == 0

    def test_morph_preserves_value(self, widget_page):
        inp = widget_page.locator('input[name="text"]')
        inp.fill("Hello World")
        submit(widget_page)
        assert inp.input_value() == "Hello World"


class TestEmailInput:
    """EmailInput widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        inp = widget_page.locator('input[name="email"]')
        assert inp.is_visible()
        assert inp.get_attribute("type") == "email"

    def test_submit_empty_shows_error(self, widget_page):
        submit(widget_page)
        errors = widget_page.locator("#id_email_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, widget_page):
        inp = widget_page.locator('input[name="email"]')
        inp.fill("test@example.com")
        submit(widget_page)
        assert inp.input_value() == "test@example.com"


class TestTextarea:
    """Textarea widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        ta = widget_page.locator('textarea[name="textarea"]')
        assert ta.is_visible()

    def test_rows_attr(self, widget_page):
        ta = widget_page.locator('textarea[name="textarea"]')
        assert ta.get_attribute("rows") == "3"

    def test_fill_value(self, widget_page):
        ta = widget_page.locator('textarea[name="textarea"]')
        ta.fill("Multiline\ntext")
        assert ta.input_value() == "Multiline\ntext"

    def test_submit_empty_shows_error(self, widget_page):
        submit(widget_page)
        errors = widget_page.locator("#id_textarea_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, widget_page):
        ta = widget_page.locator('textarea[name="textarea"]')
        ta.fill("Multiline\ntext content")
        submit(widget_page)
        assert ta.input_value() == "Multiline\ntext content"


class TestSelect:
    """Select widget functionality and morph resilience."""

    def test_renders_with_options(self, widget_page):
        sel = widget_page.locator('select[name="select"]')
        assert sel.is_visible()
        options = sel.locator("option")
        assert options.count() == 4  # empty + 3 choices

    def test_select_option(self, widget_page):
        sel = widget_page.locator('select[name="select"]')
        sel.select_option("b")
        assert sel.input_value() == "b"

    def test_submit_empty_shows_error(self, widget_page):
        submit(widget_page)
        errors = widget_page.locator("#id_select_errors")
        assert errors.count() == 1

    def test_morph_preserves_value(self, widget_page):
        sel = widget_page.locator('select[name="select"]')
        sel.select_option("b")
        submit(widget_page)
        assert sel.input_value() == "b"


class TestRadioSelect:
    """RadioSelect widget functionality and morph resilience."""

    def test_renders_options(self, widget_page):
        radios = widget_page.locator('input[name="radio"]')
        assert radios.count() == 3

    def test_select_option(self, widget_page):
        radio = widget_page.locator('input[name="radio"][value="y"]')
        radio.click(force=True)
        assert radio.is_checked()

    def test_submit_empty_shows_error(self, widget_page):
        submit(widget_page)
        # Individual radio inputs get aria-invalid
        invalid = widget_page.locator('input[name="radio"][aria-invalid="true"]')
        assert invalid.count() >= 1

    def test_morph_preserves_value(self, widget_page):
        widget_page.evaluate("""
            const radio = document.querySelector('input[name="radio"][value="y"]');
            radio.checked = true;
            radio.dispatchEvent(new Event('change', {bubbles: true}));
        """)
        submit(widget_page)
        checked = widget_page.evaluate(
            'document.querySelector(\'input[name="radio"]:checked\')?.value || ""',
        )
        assert checked == "y"


class TestCheckbox:
    """Checkbox widget functionality and morph resilience."""

    def test_renders(self, widget_page):
        cb = widget_page.locator('input[name="checkbox"]')
        assert cb.count() == 1

    def test_toggle_checked(self, widget_page):
        cb = widget_page.locator('input[name="checkbox"]')
        assert not cb.is_checked()
        cb.click()
        assert cb.is_checked()

    def test_submit_unchecked_shows_error(self, widget_page):
        submit(widget_page)
        errors = widget_page.locator("#id_checkbox_errors")
        assert errors.count() == 1

    def test_morph_preserves_checked(self, widget_page):
        cb = widget_page.locator('input[name="checkbox"]')
        cb.check()
        submit(widget_page)
        assert widget_page.locator('input[name="checkbox"]').is_checked()


class TestFileInput:
    """FileInput widget rendering."""

    def test_renders(self, widget_page):
        inp = widget_page.locator('input[name="file"]')
        assert inp.count() == 1

    def test_has_file_type(self, widget_page):
        inp = widget_page.locator('input[name="file"]')
        assert inp.get_attribute("type") == "file"
