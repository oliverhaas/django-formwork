"""Percy visual regression tests.

percy_snapshot() is a no-op when not running under ``npx percy exec``,
so these tests run harmlessly in the regular test suite.
"""

import pytest
from percy import percy_snapshot

from .conftest import submit

pytestmark = pytest.mark.screenshot


class TestVisualDefault:
    """Snapshots of widgets in their default (empty) state."""

    def test_full_page(self, widget_page):
        percy_snapshot(widget_page, "Full Page - Default")


class TestVisualErrors:
    """Snapshots after submitting an empty form (validation errors)."""

    def test_error_state(self, widget_page):
        submit(widget_page)
        percy_snapshot(widget_page, "Full Page - Validation Errors")


class TestVisualWidgets:
    """Snapshots of individual widget states."""

    def test_search_select_open(self, widget_page):
        widget_page.evaluate(
            "document.querySelector('details.dropdown.search-select').open = true",
        )
        widget_page.wait_for_timeout(200)
        percy_snapshot(widget_page, "SearchSelect - Open")

    def test_multi_select_open(self, widget_page):
        widget_page.evaluate(
            "document.querySelector('details.dropdown.multiselect').open = true",
        )
        widget_page.wait_for_timeout(200)
        percy_snapshot(widget_page, "MultiSelect - Open")

    def test_password_reveal_toggled(self, widget_page):
        widget_page.locator("label.password-reveal button").first.click()
        widget_page.wait_for_timeout(200)
        percy_snapshot(widget_page, "PasswordReveal - Revealed")

    def test_toggle_checked(self, widget_page):
        widget_page.locator("input.toggle").check()
        percy_snapshot(widget_page, "Toggle - Checked")

    def test_rating_selected(self, widget_page):
        widget_page.evaluate("""
            document.querySelector('#id_rating input[value="3"]').checked = true;
            document.querySelector('#id_rating input[value="3"]').dispatchEvent(
                new Event('change', {bubbles: true})
            );
        """)
        percy_snapshot(widget_page, "Rating - 3 Stars")

    def test_checkbox_checked(self, widget_page):
        widget_page.locator("input[name='checkbox']").check()
        percy_snapshot(widget_page, "Checkbox - Checked")
