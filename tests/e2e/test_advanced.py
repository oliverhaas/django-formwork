"""E2e tests for advanced widgets: ComboBox, DropZone, ImageUpload, ValidatedTextarea, htmx search."""

from playwright.sync_api import expect


class TestComboBox:
    """ComboBox with client-side suggestions."""

    def test_combobox_renders(self, form_page):
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').first
        assert combo.is_visible()

    def test_combobox_text_input(self, form_page):
        inp = form_page.locator('input[name="adv-tags"]')
        assert inp.is_visible()
        assert inp.get_attribute("type") == "text"
        assert inp.get_attribute("role") == "combobox"

    def test_combobox_type_shows_suggestions(self, form_page):
        inp = form_page.locator('input[name="adv-tags"]')
        inp.click()
        inp.fill("Py")
        form_page.wait_for_timeout(150)
        # Python should be visible, Go should not
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').first
        python_btn = combo.locator("button", has_text="Python")
        assert python_btn.is_visible()
        go_btn = combo.locator("button", has_text="Go")
        assert not go_btn.is_visible()

    def test_combobox_pick_suggestion(self, form_page):
        inp = form_page.locator('input[name="adv-tags"]')
        inp.click()
        inp.fill("Ru")
        form_page.wait_for_timeout(150)
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').first
        combo.locator("button", has_text="Rust").click()
        form_page.wait_for_timeout(100)
        assert inp.input_value() == "Rust"

    def test_combobox_free_text(self, form_page):
        """User can type anything — not limited to suggestions."""
        inp = form_page.locator('input[name="adv-tags"]')
        inp.fill("Haskell")
        assert inp.input_value() == "Haskell"


class TestComboBoxMultiple:
    """ComboBox in multiple (comma-separated) mode with toggle."""

    def test_multiple_combobox_renders(self, form_page):
        inp = form_page.locator('input[name="adv-multi_tags"]')
        assert inp.is_visible()

    def test_multiple_comma_separated(self, form_page):
        inp = form_page.locator('input[name="adv-multi_tags"]')
        inp.fill("Pizza, Pasta")
        assert inp.input_value() == "Pizza, Pasta"

    def test_multiple_pick_adds_value(self, form_page):
        """Clicking a suggestion adds it to the comma-separated value."""
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').nth(1)
        inp = form_page.locator('input[name="adv-multi_tags"]')
        inp.click()
        form_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        form_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()

    def test_multiple_pick_second_appends(self, form_page):
        """Clicking another suggestion appends without replacing."""
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').nth(1)
        inp = form_page.locator('input[name="adv-multi_tags"]')
        inp.click()
        form_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        form_page.wait_for_timeout(100)
        combo.locator("button", has_text="Sushi").click()
        form_page.wait_for_timeout(100)
        val = inp.input_value()
        assert "Pizza" in val
        assert "Sushi" in val

    def test_multiple_pick_toggle_off(self, form_page):
        """Clicking an already-selected suggestion removes it."""
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').nth(1)
        inp = form_page.locator('input[name="adv-multi_tags"]')
        inp.click()
        form_page.wait_for_timeout(150)
        combo.locator("button", has_text="Pizza").click()
        form_page.wait_for_timeout(100)
        assert "Pizza" in inp.input_value()
        # Click Pizza again to remove
        combo.locator("button", has_text="Pizza").click()
        form_page.wait_for_timeout(100)
        assert "Pizza" not in inp.input_value()

    def test_multiple_checkmark_indicator(self, form_page):
        """Selected suggestions show a checkmark indicator."""
        combo = form_page.locator('[data-testid="advanced"] .dropdown.combobox').nth(1)
        inp = form_page.locator('input[name="adv-multi_tags"]')
        inp.click()
        form_page.wait_for_timeout(150)
        # Check the checkmark is initially hidden (opacity-0)
        pizza_btn = combo.locator("button", has_text="Pizza")
        checkmark = pizza_btn.locator(".formwork-check")
        assert checkmark.count() == 1
        # Pick Pizza
        pizza_btn.click()
        form_page.wait_for_timeout(100)
        # Checkmark should now be visible (opacity-100)
        has_opacity = form_page.evaluate("""() => {
            const btn = document.querySelectorAll('[data-testid="advanced"] .combobox')[1]
                .querySelector('button[data-suggestion="Pizza"] .formwork-check');
            return btn ? btn.classList.contains('opacity-100') : false;
        }""")
        assert has_opacity


class TestDropZone:
    """DropZone drag-and-drop file upload."""

    def test_dropzone_renders(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .dropzone')
        assert zone.is_visible()

    def test_dropzone_has_browse_text(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .dropzone')
        text = zone.text_content()
        assert "browse" in text.lower()

    def test_dropzone_has_hidden_file_input(self, form_page):
        inp = form_page.locator('input[name="adv-documents"]')
        # File input is hidden (class="hidden")
        assert inp.get_attribute("type") == "file"

    def test_dropzone_area(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .dropzone .dropzone-area')
        assert zone.is_visible()


class TestImageUpload:
    """ImageUpload with preview."""

    def test_image_upload_renders(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .image-upload')
        assert zone.is_visible()

    def test_image_upload_has_browse_text(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .image-upload')
        text = zone.text_content()
        assert "browse" in text.lower()

    def test_image_upload_accept_image(self, form_page):
        inp = form_page.locator('input[name="adv-avatar"]')
        assert inp.get_attribute("accept") == "image/*"

    def test_image_upload_has_icon(self, form_page):
        zone = form_page.locator('[data-testid="advanced"] .image-upload')
        svg = zone.locator("svg")
        assert svg.is_visible()


class TestSearchSelectHtmx:
    """SearchSelect with server-side search (htmx)."""

    def _open_search_select(self, form_page):
        """Open search select dropdown via summary click and return container."""
        sel = form_page.locator('[data-testid="advanced"] details.dropdown.search-select')
        summary = sel.locator("summary")
        # summary::before overlay may block — use JS to open
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        form_page.wait_for_timeout(200)
        return sel

    def test_htmx_search_select_renders(self, form_page):
        sel = form_page.locator('[data-testid="advanced"] details.dropdown.search-select')
        assert sel.is_visible()

    def test_htmx_search_select_loads_results(self, form_page):
        sel = self._open_search_select(form_page)
        search = sel.locator('.dropdown-content input[type="text"]')
        # Focus the search input to trigger htmx load
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        form_page.wait_for_timeout(1000)
        buttons = sel.locator("ul button")
        assert buttons.count() >= 1

    def test_htmx_search_select_filter(self, form_page):
        sel = self._open_search_select(form_page)
        # Trigger focus to load all results
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        # Type to filter
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.value = 'Tok';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        expect(sel.locator("ul button")).to_have_count(1, timeout=3000)
        assert "Tokyo" in sel.locator("ul button").first.text_content()

    def test_htmx_search_select_pick(self, form_page):
        sel = self._open_search_select(form_page)
        hidden = sel.locator('input[type="hidden"]')
        # Trigger focus to load results
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        form_page.wait_for_timeout(1000)
        # Type to filter to London
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.value = 'Lon';
            search.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        form_page.wait_for_timeout(1000)
        sel.locator("ul button", has_text="London").click()
        form_page.wait_for_timeout(200)
        assert hidden.input_value() == "ldn"

        # Dropdown should close after picking
        assert not sel.get_attribute("open")

    def test_htmx_search_select_no_results(self, form_page):
        sel = self._open_search_select(form_page)
        # Trigger focus to load results
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.focus();
            search.dispatchEvent(new Event('focus'));
        }""")
        expect(sel.locator("ul button")).to_have_count(4, timeout=3000)
        # Search for something that doesn't exist
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.search-select');
            const search = dd.querySelector('.dropdown-content input[type="text"]');
            search.value = 'zzzzz';
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=zzzzz&type=search_select', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        no_results = sel.locator("li", has_text="No results")
        expect(no_results).to_be_visible(timeout=3000)


class TestMultiSelectHtmx:
    """MultiSelect with server-side search (htmx)."""

    def test_htmx_multiselect_renders(self, form_page):
        multi = form_page.locator('[data-testid="advanced"] details.dropdown.multiselect')
        assert multi.is_visible()

    def _open_multiselect_and_load(self, form_page):
        """Open multiselect dropdown and trigger htmx load."""
        multi = form_page.locator('[data-testid="advanced"] details.dropdown.multiselect')
        summary = multi.locator("summary")
        summary.click()
        form_page.wait_for_timeout(200)
        # Trigger htmx load via htmx.ajax() (summary::before overlay blocks clicks/focus)
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.multiselect');
            const search = dd.querySelector('input[type="text"]');
            htmx.ajax('GET', search.getAttribute('hx-get') + '?q=&type=multiselect&name=adv-lang_search', {
                target: search.getAttribute('hx-target'),
                swap: 'innerHTML',
            });
        }""")
        checkboxes = multi.locator('input[type="checkbox"]')
        expect(checkboxes.first).to_be_attached(timeout=3000)
        return multi

    def test_htmx_multiselect_loads_results(self, form_page):
        multi = self._open_multiselect_and_load(form_page)
        checkboxes = multi.locator('input[type="checkbox"]')
        assert checkboxes.count() >= 1

    def test_htmx_multiselect_select_options(self, form_page):
        multi = self._open_multiselect_and_load(form_page)

        # Select via JS (checkboxes are behind overlay)
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="advanced"] details.dropdown.multiselect');
            const cbs = dd.querySelectorAll('input[type="checkbox"]');
            if (cbs.length >= 2) {
                cbs[0].checked = true;
                cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
                cbs[1].checked = true;
                cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""")
        form_page.wait_for_timeout(300)

        # Hidden inputs should be created for selected values
        hidden_inputs = multi.locator('input[type="hidden"][name="adv-lang_search"]')
        assert hidden_inputs.count() >= 2


class TestValidatedTextarea:
    """ValidatedTextarea with server-side validation and highlighting."""

    def test_validated_textarea_renders(self, form_page):
        wrapper = form_page.locator('[data-testid="advanced"] .validated-textarea')
        assert wrapper.is_visible()

    def test_validated_textarea_has_overlay(self, form_page):
        highlights = form_page.locator('[data-testid="advanced"] .validated-textarea-highlights')
        assert highlights.count() == 1

    def test_validated_textarea_has_errors_div(self, form_page):
        errors_div = form_page.locator('[data-testid="advanced"] .validated-textarea-tooltip .formwork-errors')
        assert errors_div.count() == 1

    def _trigger_validation(self, form_page, text):
        """Trigger htmx validation POST via htmx.ajax() since Playwright fill() doesn't fire htmx events."""
        form_page.evaluate(
            """(text) => {
            const textarea = document.querySelector('textarea[name="adv-bio"]');
            textarea.value = text;
            const url = textarea.getAttribute('hx-post');
            const highlightsId = textarea.getAttribute('hx-target');
            const params = new URLSearchParams();
            params.append('text', text);
            params.append('field_name', 'adv-bio');
            params.append('errors_id', textarea.id + '_errors');
            fetch(url, {method: 'POST', body: params})
                .then(r => r.text())
                .then(html => {
                    // Parse the response: main content + OOB swap
                    const parser = new DOMParser();
                    const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
                    // Find OOB element
                    const oob = doc.querySelector('[hx-swap-oob]');
                    const errorsTarget = document.getElementById(textarea.id + '_errors');
                    if (oob && errorsTarget) {
                        errorsTarget.innerHTML = oob.innerHTML;
                        // Remove OOB from main content
                        oob.remove();
                    }
                    // Remaining content goes to highlights
                    const target = document.querySelector(highlightsId);
                    const remaining = doc.body.firstChild;
                    target.innerHTML = remaining.innerHTML;
                });
        }""",
            text,
        )

    def test_validated_textarea_type_clean_text(self, form_page):
        self._trigger_validation(form_page, "Hello world")
        form_page.wait_for_timeout(500)
        highlights = form_page.locator('[data-testid="advanced"] .validated-textarea-highlights')
        marks = highlights.locator("mark")
        assert marks.count() == 0

    def test_validated_textarea_type_bad_text(self, form_page):
        self._trigger_validation(form_page, "This has a badword in it")
        form_page.wait_for_timeout(500)
        highlights = form_page.locator('[data-testid="advanced"] .validated-textarea-highlights')
        marks = highlights.locator("mark")
        expect(marks).to_have_count(1, timeout=3000)
        assert marks.first.text_content() == "badword"

    def test_validated_textarea_error_messages(self, form_page):
        self._trigger_validation(form_page, "badword and spam here")
        form_page.wait_for_timeout(500)
        errors_div = form_page.locator('[data-testid="advanced"] .validated-textarea-tooltip .formwork-errors')
        messages = errors_div.locator("p")
        expect(messages).to_have_count(2, timeout=3000)

    def test_validated_textarea_errors_clear(self, form_page):
        # First, trigger errors
        self._trigger_validation(form_page, "badword")
        form_page.wait_for_timeout(500)
        highlights = form_page.locator('[data-testid="advanced"] .validated-textarea-highlights')
        expect(highlights.locator("mark")).to_have_count(1, timeout=3000)
        # Now send clean text
        self._trigger_validation(form_page, "All clean now")
        form_page.wait_for_timeout(500)
        expect(highlights.locator("mark")).to_have_count(0, timeout=3000)
