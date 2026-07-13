"""Tests for the FileDropZone widget.

Levels:
    1. unit (widget object): instantiation, get_context, value_from_datadict
    2. unit (widget rendering): HTML structure, Alpine bindings, attributes
    3. integration (form integration): fieldset, error state, prefix
    4. integration (Jinja2/DTL parity): identical HTML across engines
    5. e2e (user interaction): renders, browse text, file input, area
    6. e2e (error flow): SKIPPED (no required FileDropZone on /uploads/ page)
    7. e2e (morph resilience): file state preserved across htmx morphs
    8. screenshot (visual states): default, with-file
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import FileDropZone

from .conftest import assert_html_equivalent, render_form, render_widget


class FileDropZoneForm(FormworkForm):
    """Form fixture for FileDropZone integration tests."""

    upload = forms.FileField(widget=FileDropZone, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_file_drop_zone_instantiation_default():
    """FileDropZone can be instantiated with no arguments."""
    widget = FileDropZone()
    assert isinstance(widget, FileDropZone)


@pytest.mark.unit
def test_file_drop_zone_instantiation_with_max_size():
    """FileDropZone stores max_size when provided."""
    widget = FileDropZone(max_size=5 * 1024 * 1024)
    assert widget.max_size == 5 * 1024 * 1024


@pytest.mark.unit
def test_file_drop_zone_instantiation_max_size_none_by_default():
    """max_size defaults to None when not provided."""
    widget = FileDropZone()
    assert widget.max_size is None


@pytest.mark.unit
def test_file_drop_zone_instantiation_with_attrs():
    """Attrs are passed through to the widget."""
    widget = FileDropZone(attrs={"multiple": True, "accept": ".pdf"})
    assert widget.attrs.get("multiple") is True
    assert widget.attrs.get("accept") == ".pdf"


@pytest.mark.unit
def test_file_drop_zone_get_context_no_accept():
    """get_context() with no accept attr does not add accept_display."""
    widget = FileDropZone()
    ctx = widget.get_context("upload", None, {"id": "id_upload"})
    assert "accept_display" not in ctx["widget"]


@pytest.mark.unit
def test_file_drop_zone_get_context_with_accept():
    """get_context() with accept attr populates accept_display."""
    widget = FileDropZone(attrs={"accept": ".pdf"})
    ctx = widget.get_context("upload", None, {"id": "id_upload"})
    assert ctx["widget"]["accept_display"] == "PDF"


@pytest.mark.unit
def test_file_drop_zone_get_context_accept_image():
    """get_context() formats image/* accept attr as 'Images'."""
    widget = FileDropZone(attrs={"accept": "image/*"})
    ctx = widget.get_context("upload", None, {"id": "id_upload"})
    assert ctx["widget"]["accept_display"] == "Images"


@pytest.mark.unit
def test_file_drop_zone_get_context_with_max_size():
    """get_context() with max_size populates max_size and max_size_display."""
    widget = FileDropZone(max_size=5 * 1024 * 1024)
    ctx = widget.get_context("upload", None, {"id": "id_upload"})
    assert ctx["widget"]["max_size"] == 5 * 1024 * 1024
    assert ctx["widget"]["max_size_display"] == "5 MB"


@pytest.mark.unit
def test_file_drop_zone_get_context_no_max_size():
    """get_context() without max_size does not add max_size keys."""
    widget = FileDropZone()
    ctx = widget.get_context("upload", None, {"id": "id_upload"})
    assert "max_size" not in ctx["widget"]
    assert "max_size_display" not in ctx["widget"]


@pytest.mark.unit
def test_file_drop_zone_value_from_datadict_returns_file():
    """value_from_datadict() reads from files dict, not POST data."""
    widget = FileDropZone()
    mock_file = MagicMock()
    files = {"upload": mock_file}
    result = widget.value_from_datadict({}, files, "upload")
    assert result is mock_file


@pytest.mark.unit
def test_file_drop_zone_value_from_datadict_missing_returns_none():
    """value_from_datadict() returns None when no file uploaded."""
    widget = FileDropZone()
    result = widget.value_from_datadict({}, {}, "upload")
    assert result is None


@pytest.mark.unit
def test_file_drop_zone_allow_multiple_selected():
    """FileDropZone has allow_multiple_selected = True."""
    widget = FileDropZone()
    assert widget.allow_multiple_selected is True


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_file_drop_zone_renders_dropzone_wrapper():
    """Rendered output contains a div with class 'dropzone'."""
    soup = render_widget(FileDropZone())
    wrapper = soup.find("div", class_="dropzone")
    assert wrapper is not None


@pytest.mark.unit
def test_file_drop_zone_renders_file_input():
    """Rendered output contains a file input with the correct name."""
    soup = render_widget(FileDropZone(), name="file")
    inp = soup.find("input", {"type": "file"})
    assert inp is not None
    assert inp["name"] == "file"


@pytest.mark.unit
def test_file_drop_zone_alpine_x_data():
    """Root div binds to the formworkDropZone Alpine.data component."""
    soup = render_widget(FileDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper is not None
    assert wrapper["x-data"] == "formworkDropZone"


@pytest.mark.unit
def test_file_drop_zone_data_max_size_default_zero():
    """Without max_size, data-max-size renders '0' (client-side check disabled)."""
    soup = render_widget(FileDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper["data-max-size"] == "0"


@pytest.mark.unit
def test_file_drop_zone_data_max_size_attribute():
    """max_size rides in the data-max-size attribute read by the component."""
    soup = render_widget(FileDropZone(max_size=5 * 1024 * 1024))
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper["data-max-size"] == "5242880"


@pytest.mark.unit
def test_file_drop_zone_drag_event_handlers():
    """Root div has @dragover.prevent, @dragleave.prevent, @drop.prevent."""
    soup = render_widget(FileDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper.has_attr("@dragover.prevent")
    assert wrapper.has_attr("@dragleave.prevent")
    assert wrapper.has_attr("@drop.prevent")


@pytest.mark.unit
def test_file_drop_zone_drop_area():
    """Rendered output contains a div with class 'dropzone-area'."""
    soup = render_widget(FileDropZone())
    zone = soup.find("div", class_="dropzone-area")
    assert zone is not None


@pytest.mark.unit
def test_file_drop_zone_click_to_browse():
    """The dropzone-area has a @click handler to trigger the file input."""
    soup = render_widget(FileDropZone())
    zone = soup.find("div", class_="dropzone-area")
    assert "@click" in str(zone)


@pytest.mark.unit
def test_file_drop_zone_file_input_change_handler():
    """The file input has a @change handler."""
    soup = render_widget(FileDropZone())
    inp = soup.find("input", {"type": "file"})
    assert inp.has_attr("@change")


@pytest.mark.unit
def test_file_drop_zone_upload_icon():
    """Rendered output contains an upload icon."""
    soup = render_widget(FileDropZone())
    icon = soup.find("i", class_="icon")
    assert icon is not None
    assert "icon-cloud-upload" in icon.get("class", [])


@pytest.mark.unit
def test_file_drop_zone_browse_text():
    """Rendered output contains the word 'browse'."""
    soup = render_widget(FileDropZone())
    text = soup.get_text()
    assert "browse" in text.lower()


@pytest.mark.unit
def test_file_drop_zone_error_element_role_alert():
    """The client-side error <p> has role='alert' so rejected files are announced."""
    soup = render_widget(FileDropZone())
    error = soup.find("p", class_="dropzone-error")
    assert error is not None
    assert error.get("role") == "alert"


@pytest.mark.unit
def test_file_drop_zone_multiple_attr_passthrough():
    """multiple attr on the widget is passed through to the file input."""
    widget = FileDropZone(attrs={"multiple": True})
    soup = render_widget(widget, name="files")
    inp = soup.find("input", {"type": "file"})
    assert inp.has_attr("multiple")


@pytest.mark.unit
def test_file_drop_zone_id_on_input():
    """The id attr is applied to the file input element."""
    soup = render_widget(FileDropZone(), name="file", attrs={"id": "id_file"})
    inp = soup.find("input", {"type": "file"})
    assert inp["id"] == "id_file"


@pytest.mark.unit
def test_file_drop_zone_wrapper_has_id():
    """When id is provided, wrapper gets id='{id}_dropzone'."""
    soup = render_widget(FileDropZone(), attrs={"id": "id_file"})
    wrapper = soup.find("div", class_="dropzone")
    assert wrapper["id"] == "id_file_dropzone"


@pytest.mark.unit
def test_file_drop_zone_no_wrapper_id_without_id():
    """When no id is provided, wrapper has no id attr."""
    soup = render_widget(FileDropZone())
    wrapper = soup.find("div", class_="dropzone")
    assert not wrapper.has_attr("id")


@pytest.mark.unit
def test_file_drop_zone_accept_display_shown():
    """When accept attr is set, accept_display text appears in the output."""
    widget = FileDropZone(attrs={"accept": ".pdf"})
    soup = render_widget(widget, attrs={"id": "id_upload"})
    text = soup.get_text()
    assert "PDF" in text


@pytest.mark.unit
def test_file_drop_zone_max_size_display_shown():
    """When max_size is set, the formatted size appears in the output."""
    widget = FileDropZone(max_size=5 * 1024 * 1024)
    soup = render_widget(widget, attrs={"id": "id_upload"})
    text = soup.get_text()
    assert "5 MB" in text


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_file_drop_zone_renders_via_form(renderer):
    """FileDropZone renders correctly when used inside a FormworkForm."""
    form = FileDropZoneForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "upload"})
    assert inp is not None


@pytest.mark.integration
def test_file_drop_zone_form_wraps_in_fieldset(renderer):
    """Field template wraps the FileDropZone in a fieldset with a stable id."""
    form = FileDropZoneForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_upload_field")
    assert fieldset is not None


@pytest.mark.integration
def test_file_drop_zone_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the file input."""
    form = FileDropZoneForm(data={}, files={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "upload"})
    assert inp is not None
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_file_drop_zone_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip with error text."""
    form = FileDropZoneForm(data={}, files={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_upload_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_file_drop_zone_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = FileDropZoneForm(prefix="doc")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "doc-upload"})
    assert inp is not None
    assert inp["id"] == "id_doc-upload"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_file_drop_zone_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """FileDropZone produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(FileDropZoneForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(FileDropZoneForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_file_drop_zone_renders_on_page(uploads_page):
    """FileDropZone widget is visible on the /uploads/ page."""
    zone = uploads_page.locator(".dropzone").first
    assert zone.is_visible()


@pytest.mark.e2e
def test_file_drop_zone_has_browse_text(uploads_page):
    """FileDropZone contains the word 'browse'."""
    zone = uploads_page.locator(".dropzone").first
    assert "browse" in zone.text_content().lower()


@pytest.mark.e2e
def test_file_drop_zone_has_hidden_file_input(uploads_page):
    """FileDropZone has a hidden file input with correct name."""
    inp = uploads_page.locator('input[name="dropzone"]')
    assert inp.get_attribute("type") == "file"


@pytest.mark.e2e
def test_file_drop_zone_has_area(uploads_page):
    """FileDropZone renders the .dropzone-area element."""
    area = uploads_page.locator(".dropzone .dropzone-area").first
    assert area.is_visible()


@pytest.mark.e2e
def test_file_drop_zone_accepts_multiple(uploads_page):
    """FileDropZone with multiple=True has the multiple attr on input."""
    inp = uploads_page.locator('input[name="dropzone"]')
    assert inp.get_attribute("multiple") is not None


@pytest.mark.e2e
def test_file_drop_zone_restricted_renders(uploads_page):
    """Restricted FileDropZone (PDF only) is visible on the /uploads/ page."""
    zone = uploads_page.locator(".dropzone").nth(1)
    assert zone.is_visible()


@pytest.mark.e2e
def test_file_drop_zone_restricted_accept_attribute(uploads_page):
    """Restricted FileDropZone has the correct accept attr."""
    inp = uploads_page.locator('input[name="dropzone_restricted"]')
    assert inp.get_attribute("accept") == ".pdf"


@pytest.mark.e2e
def test_file_drop_zone_restricted_shows_size_limit(uploads_page):
    """Restricted FileDropZone shows the 5 MB size limit."""
    zone = uploads_page.locator(".dropzone").nth(1)
    text = zone.text_content().lower()
    assert "5 mb" in text or "5mb" in text


@pytest.mark.e2e
def test_file_drop_zone_restricted_shows_file_type(uploads_page):
    """Restricted FileDropZone shows the PDF file type restriction."""
    zone = uploads_page.locator(".dropzone").nth(1)
    text = zone.text_content().upper()
    assert "PDF" in text


@pytest.mark.e2e
def test_file_drop_zone_selecting_file_shows_preview(uploads_page):
    """Choosing a file shows its name and formatted size in the preview area."""
    from playwright.sync_api import expect

    uploads_page.locator('input[name="dropzone"]').set_input_files(
        [{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"formwork"}],
    )
    zone = uploads_page.locator(".dropzone").first
    expect(zone.locator(".dropzone-file-name")).to_have_text("notes.txt")
    expect(zone.locator(".dropzone-file-size")).to_have_text("8 B")


@pytest.mark.e2e
def test_file_drop_zone_rejects_wrong_type_with_alert(uploads_page):
    """The restricted zone rejects a non-PDF file and announces the error."""
    from playwright.sync_api import expect

    uploads_page.locator('input[name="dropzone_restricted"]').set_input_files(
        [{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"formwork"}],
    )
    error = uploads_page.locator(".dropzone").nth(1).locator(".dropzone-error")
    expect(error).to_have_text("1 file(s) wrong type")


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# SKIPPED: There is no required FileDropZone field on the /uploads/ page
# (all file fields are required=False), so a dedicated error-flow test
# would require a separate page.  Tracked as a gap for future work.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# FileDropZone state (files list) is held in Alpine.js memory and the
# actual files in the input element.  After a form morph the Alpine x-data
# is preserved (formwork.js blocks x-data updates) so the files list
# survives the morph.  However, triggering a real file upload in Playwright
# and then morphing requires a round-trip with multipart/form-data, which
# the current /uploads/ page does not support in a testable way.
# This is left as a gap until a dedicated morph-resilience page exists.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only, producing PNG artifacts in test-results/ for manual
# review.  True baseline comparison requires pytest-playwright-visual.
# See issue #26.


@pytest.mark.screenshot
def test_file_drop_zone_screenshot_default(uploads_page, assert_screenshot):
    """Visual snapshot: FileDropZone in default (empty) state."""
    wrapper = uploads_page.locator(".dropzone").first
    assert_screenshot(wrapper, "file-drop-zone-default.png")


@pytest.mark.screenshot
def test_file_drop_zone_screenshot_restricted(uploads_page, assert_screenshot):
    """Visual snapshot: FileDropZone with PDF restriction and size limit."""
    wrapper = uploads_page.locator(".dropzone").nth(1)
    assert_screenshot(wrapper, "file-drop-zone-restricted.png")
