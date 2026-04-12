"""Tests for Django's built-in ClearableFileInput widget as styled by formwork.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_clearable_file_input.py                 # everything
    uv run pytest tests/widgets/ -m unit                                     # all widgets, unit only
    uv run pytest tests/widgets/test_clearable_file_input.py -m "not e2e"   # skip browser tests

Levels:
    1. unit        — widget object: instantiation, is_multipart, value_from_datadict
    2. unit        — widget rendering: file input, clear checkbox, filename display
    3. integration — form integration: fieldset, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: renders, filename, clear checkbox
    6. e2e         — error flow: SKIPPED (avatar is not required on /builtin/)
    7. e2e         — morph resilience: checked clear checkbox survives morph
    8. screenshot  — visual states: default
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm

from .conftest import assert_html_equivalent, render_form, render_widget


class _FakeFile:
    """Minimal file-like object so ClearableFileInput shows the clear checkbox."""

    url = "#"

    def __str__(self) -> str:
        return "existing-file.txt"


class ClearableFileForm(FormworkForm):
    """Form fixture for ClearableFileInput integration tests."""

    document = forms.FileField(
        widget=forms.ClearableFileInput,
        required=False,
        initial=_FakeFile(),
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_clearable_file_input_instantiation():
    """ClearableFileInput can be instantiated with no arguments."""
    widget = forms.ClearableFileInput()
    assert isinstance(widget, forms.ClearableFileInput)


@pytest.mark.unit
def test_clearable_file_input_is_multipart():
    """ClearableFileInput.needs_multipart_form() returns True."""
    widget = forms.ClearableFileInput()
    assert widget.needs_multipart_form is True


@pytest.mark.unit
def test_clearable_file_input_value_from_datadict():
    """value_from_datadict returns the uploaded file object from FILES."""
    from unittest.mock import MagicMock

    widget = forms.ClearableFileInput()
    mock_file = MagicMock()
    files = {"avatar": mock_file}
    result = widget.value_from_datadict(QueryDict(""), files, "avatar")
    assert result is mock_file


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_clearable_file_input_renders_file_input():
    """render() produces an <input type='file'>."""
    widget = forms.ClearableFileInput()
    soup = render_widget(widget, name="document", value=None)
    inp = soup.find("input", attrs={"type": "file"})
    assert inp is not None


@pytest.mark.unit
def test_clearable_file_input_renders_clear_checkbox_when_initial():
    """When a file-like value is provided, a clear checkbox is rendered."""
    widget = forms.ClearableFileInput()
    widget.is_required = False
    soup = render_widget(widget, name="document", value=_FakeFile())
    checkbox = soup.find("input", attrs={"type": "checkbox"})
    assert checkbox is not None


@pytest.mark.unit
def test_clearable_file_input_no_clear_without_initial():
    """No clear checkbox is rendered when value is None."""
    widget = forms.ClearableFileInput()
    soup = render_widget(widget, name="document", value=None)
    checkbox = soup.find("input", attrs={"type": "checkbox"})
    assert checkbox is None


@pytest.mark.unit
def test_clearable_file_input_shows_current_filename():
    """The current filename is included in the output when a file value is set."""
    widget = forms.ClearableFileInput()
    widget.is_required = False
    soup = render_widget(widget, name="document", value=_FakeFile())
    assert "existing-file.txt" in soup.get_text()


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_clearable_file_input_renders_via_form(renderer):
    """ClearableFileInput renders correctly inside a FormworkForm."""
    form = ClearableFileForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "document", "type": "file"})
    assert inp is not None


@pytest.mark.integration
def test_clearable_file_input_form_wraps_in_fieldset(renderer):
    """Field template wraps the widget in a fieldset with a stable id."""
    form = ClearableFileForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_document_field")
    assert fieldset is not None


@pytest.mark.integration
def test_clearable_file_input_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    form = ClearableFileForm(prefix="upload")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", attrs={"name": "upload-document", "type": "file"})
    assert inp is not None
    assert inp["id"] == "id_upload-document"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_clearable_file_input_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """ClearableFileInput produces equivalent HTML via DTL and Jinja2."""
    soup_dtl = render_form(ClearableFileForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(ClearableFileForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_clearable_file_input_renders_on_page(builtin_page):
    """File input is visible on the /builtin/ page."""
    from playwright.sync_api import expect

    file_input = builtin_page.locator('input[name="avatar"][type="file"]')
    expect(file_input).to_be_attached()


@pytest.mark.e2e
def test_clearable_file_input_shows_current_file(builtin_page):
    """The initial filename 'photo.jpg' is displayed on the page."""
    from playwright.sync_api import expect

    text = builtin_page.locator("#id_avatar_field")
    expect(text).to_contain_text("photo.jpg")


@pytest.mark.e2e
def test_clearable_file_input_clear_checkbox_visible(builtin_page):
    """The clear checkbox is present on the page when a file is set."""
    from playwright.sync_api import expect

    checkbox = builtin_page.locator('input[name="avatar-clear"]')
    expect(checkbox).to_be_attached()


@pytest.mark.e2e
def test_clearable_file_input_clear_checkbox_interaction(builtin_page):
    """User can check the clear checkbox."""
    from playwright.sync_api import expect

    checkbox = builtin_page.locator('input[name="avatar-clear"]')
    expect(checkbox).not_to_be_checked()
    checkbox.check()
    expect(checkbox).to_be_checked()


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# avatar is not required on the /builtin/ page, so a dedicated error-flow
# test would need a separate page with a required ClearableFileInput.
# Skipped for now — tracked as a gap in error-state coverage.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_clearable_file_input_morph_preserves_clear_checkbox(builtin_page):
    """Checked clear checkbox state survives an htmx form morph."""
    from playwright.sync_api import expect

    from tests.e2e.conftest import submit

    checkbox = builtin_page.locator('input[name="avatar-clear"]')
    checkbox.check()
    expect(checkbox).to_be_checked()
    submit(builtin_page)
    expect(builtin_page.locator('input[name="avatar-clear"]')).to_be_checked()


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — produces PNG artifacts in test-results/ for manual
# review.  True baseline comparison requires a visual-regression plugin.


@pytest.mark.screenshot
def test_clearable_file_input_screenshot_default(builtin_page, assert_screenshot):
    """Visual snapshot: ClearableFileInput in default state."""
    wrapper = builtin_page.locator("#id_avatar_field")
    assert_screenshot(wrapper, "clearable-file-input-default.png")
