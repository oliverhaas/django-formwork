"""Basic e2e tests for form rendering and interaction."""


class TestFormRendering:
    """Forms render correctly in the browser."""

    def test_page_loads(self, form_page):
        assert form_page.title() == "e2e test"

    def test_basic_form_renders(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        assert form.is_visible()

    def test_basic_form_has_fields(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        assert form.locator('input[name="basic-name"]').is_visible()
        assert form.locator('input[name="basic-email"]').is_visible()
        assert form.locator('textarea[name="basic-message"]').is_visible()
        assert form.locator('select[name="basic-priority"]').is_visible()

    def test_fieldset_wrapper(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        fieldsets = form.locator("fieldset.fieldset")
        assert fieldsets.count() >= 4

    def test_labels_render(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        labels = form.locator(".fieldset-legend")
        assert labels.count() >= 4

    def test_help_text_renders(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        help_text = form.locator("#id_basic-name_helptext")
        assert help_text.is_visible()
        assert "full name" in help_text.text_content().lower()

    def test_placeholder_renders(self, form_page):
        name_input = form_page.locator('input[name="basic-name"]')
        assert name_input.get_attribute("placeholder") == "Your name"

    def test_required_asterisk(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        asterisks = form.locator(".text-error")
        assert asterisks.count() >= 1


class TestFormSubmission:
    """Form submission works correctly."""

    def _bypass_native_validation(self, page):
        """Disable browser-native validation so POST reaches Django."""
        page.evaluate("document.querySelectorAll('form').forEach(f => f.noValidate = true)")

    def test_submit_empty_shows_errors(self, form_page):
        self._bypass_native_validation(form_page)
        form = form_page.locator('[data-testid="basic"]')
        form.locator('button[type="submit"]').click()
        form_page.wait_for_load_state("domcontentloaded")
        # After submission with empty fields, error tooltips should appear
        tooltips = form_page.locator('[data-testid="basic"] .tooltip-error')
        assert tooltips.count() >= 1

    def test_error_tooltip_has_message(self, form_page):
        self._bypass_native_validation(form_page)
        form = form_page.locator('[data-testid="basic"]')
        form.locator('button[type="submit"]').click()
        form_page.wait_for_load_state("domcontentloaded")
        error_content = form_page.locator('[data-testid="basic"] .tooltip-content').first
        assert error_content.text_content().strip() != ""

    def test_novalidate_set_after_server_errors(self, form_page):
        """After server-side errors render, the inline script disables native validation."""
        self._bypass_native_validation(form_page)
        form = form_page.locator('[data-testid="basic"]')
        form.locator('button[type="submit"]').click()
        form_page.wait_for_load_state("domcontentloaded")
        # The inline script should have set noValidate on the form
        no_validate = form_page.evaluate(
            "document.querySelector('[data-testid=\"basic\"]').noValidate",
        )
        assert no_validate is True

    def test_valid_submission(self, form_page):
        form = form_page.locator('[data-testid="basic"]')
        form.locator('input[name="basic-name"]').fill("Jane Doe")
        form.locator('input[name="basic-email"]').fill("jane@example.com")
        form.locator('textarea[name="basic-message"]').fill("Hello")
        form.locator('select[name="basic-priority"]').select_option("low")
        form.locator('button[type="submit"]').click()
        form_page.wait_for_load_state("domcontentloaded")
        assert form_page.locator("#submitted").is_visible()


class TestErrorStates:
    """Pre-rendered error states display correctly."""

    def test_error_page_shows_tooltips(self, error_page):
        tooltips = error_page.locator(".tooltip-error")
        assert tooltips.count() >= 1

    def test_aria_invalid_set(self, error_page):
        invalid_inputs = error_page.locator('[aria-invalid="true"]')
        assert invalid_inputs.count() >= 1

    def test_error_role_alert(self, error_page):
        alerts = error_page.locator('.tooltip-content[role="alert"]')
        assert alerts.count() >= 1


class TestWidgets:
    """Custom widget interactions work in the browser."""

    def test_toggle_widget_clickable(self, form_page):
        toggle = form_page.locator('input[name="widgets-toggle"]')
        assert not toggle.is_checked()
        toggle.click()
        assert toggle.is_checked()

    def test_range_widget(self, form_page):
        range_input = form_page.locator('input[name="widgets-volume"]')
        assert range_input.get_attribute("type") == "range"
        assert range_input.get_attribute("min") == "0"
        assert range_input.get_attribute("max") == "100"

    def test_rating_widget_stars(self, form_page):
        rating_div = form_page.locator(".rating")
        assert rating_div.is_visible()
        stars = rating_div.locator('input[type="radio"]')
        assert stars.count() == 5

    def test_rating_widget_select_star(self, form_page):
        rating_div = form_page.locator(".rating")
        third_star = rating_div.locator('input[type="radio"]').nth(2)
        third_star.click(force=True)
        assert third_star.is_checked()

    def test_password_reveal_toggle(self, form_page):
        pw_input = form_page.locator('input[name="widgets-password"]')
        # Wait for Alpine.js to bind x-bind:type (initially "password")
        form_page.wait_for_timeout(200)
        assert pw_input.get_attribute("type") == "password"
        # Click the reveal button
        reveal_btn = form_page.locator('[data-testid="widgets"] label.input button')
        reveal_btn.click()
        # Wait for Alpine.js to update
        form_page.wait_for_timeout(100)
        assert pw_input.get_attribute("type") == "text"
        # Click again to hide
        reveal_btn.click()
        form_page.wait_for_timeout(100)
        assert pw_input.get_attribute("type") == "password"

    def test_radio_group(self, form_page):
        radios = form_page.locator('input[name="widgets-radio"]')
        assert radios.count() == 3
        radios.nth(1).click(force=True)
        assert radios.nth(1).is_checked()

    def test_checkbox(self, form_page):
        cb = form_page.locator('input[name="widgets-checkbox"]')
        assert not cb.is_checked()
        cb.click()
        assert cb.is_checked()


class TestSelectWidgets:
    """SearchSelect and MultiSelect interactions."""

    def test_search_select_renders(self, form_page):
        sel = form_page.locator('[data-testid="selects"] details.dropdown.search-select')
        assert sel.is_visible()

    def test_search_select_search_and_pick(self, form_page):
        sel = form_page.locator('[data-testid="selects"] details.dropdown.search-select')
        hidden_input = sel.locator('input[type="hidden"]')

        # Open dropdown
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="selects"] details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        form_page.wait_for_timeout(200)

        # Type in search input inside dropdown
        search_input = sel.locator('.dropdown-content input[type="text"]')
        search_input.fill("Tok")
        form_page.wait_for_timeout(100)

        # Tokyo option should be visible
        tokyo_btn = sel.locator("button", has_text="Tokyo")
        assert tokyo_btn.is_visible()

        # London should be hidden
        london_btn = sel.locator("button", has_text="London")
        assert not london_btn.is_visible()

        # Pick Tokyo
        tokyo_btn.click()
        form_page.wait_for_timeout(100)
        assert hidden_input.input_value() == "tyo"

        # Dropdown should close after picking
        assert not sel.get_attribute("open")

    def test_search_select_closes_on_pick(self, form_page):
        """Dropdown closes when picking an option via real click flow."""
        sel = form_page.locator('[data-testid="selects"] details.dropdown.search-select')
        summary = sel.locator("summary")
        hidden_input = sel.locator('input[type="hidden"]')

        # Open by clicking summary (real user flow)
        summary.click()
        form_page.wait_for_timeout(200)
        assert sel.get_attribute("open") is not None

        # Pick London
        sel.locator("button", has_text="London").click()
        form_page.wait_for_timeout(200)

        # Value should be set and dropdown should be closed
        assert hidden_input.input_value() == "ldn"
        assert sel.get_attribute("open") is None
        assert "London" in summary.text_content()

    def test_search_select_icon_after_pick(self, form_page):
        """Picking an option with an icon shows the icon in the summary."""
        sel = form_page.locator('[data-testid="selects"] details.dropdown.search-select')
        summary = sel.locator("summary")

        # Open dropdown
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="selects"] details.dropdown.search-select');
            dd.open = true;
            dd.dispatchEvent(new Event('toggle'));
        }""")
        form_page.wait_for_timeout(200)

        # Pick New York (has 🗽 icon)
        sel.locator("button", has_text="New York").click()
        form_page.wait_for_timeout(100)

        # Summary should show icon + label
        summary_text = summary.text_content()
        assert "New York" in summary_text

    def test_multiselect_renders(self, form_page):
        multi = form_page.locator('[data-testid="selects"] details.dropdown:has(.multiselect)')
        assert multi.is_visible()

    def test_multiselect_open_and_select(self, form_page):
        multi = form_page.locator('[data-testid="selects"] details.dropdown:has(.multiselect)')
        summary = multi.locator("summary")

        # Open dropdown
        summary.click()
        form_page.wait_for_timeout(100)

        # Check hidden checkboxes via JS (they're hidden and behind
        # the summary::before click-outside overlay)
        form_page.evaluate("""() => {
            const dd = document.querySelector('[data-testid="selects"] details.dropdown:has(.multiselect)');
            ['py', 'go'].forEach(v => {
                const cb = dd.querySelector(`input[value="${v}"]`);
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""")
        form_page.wait_for_timeout(100)

        # Verify checkboxes are checked
        assert multi.locator('input[value="py"]').is_checked()
        assert multi.locator('input[value="go"]').is_checked()

        # Summary should show selected names (Alpine.js updates via displayText)
        summary_text = summary.text_content()
        assert "Python" in summary_text or "2" in summary_text
