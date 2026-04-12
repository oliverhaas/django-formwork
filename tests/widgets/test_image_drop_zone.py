"""Tests for the ImageDropZone widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_image_drop_zone.py                 # everything
    uv run pytest tests/widgets/ -m unit                                 # all widgets, unit only
    uv run pytest tests/widgets/test_image_drop_zone.py -m "not e2e"    # skip browser tests

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict, edge cases
    2. unit        — widget rendering: HTML structure, attributes, Alpine, icons
    3. integration — form integration: field template, error state, prefix
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: upload, preview, remove
    6. e2e         — error flow: SKIPPED (no dedicated error-flow page)
    7. e2e         — morph resilience: preview state preserved across morphs
    8. screenshot  — visual states: default, with-image
"""

from __future__ import annotations

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ImageDropZone

from .conftest import assert_html_equivalent, render_form, render_widget


# Pillow is not a project dependency so use FileField to avoid validation
# errors in integration tests that would require Pillow for ImageField.
class ImageDropZoneForm(FormworkForm):
    """Form fixture for ImageDropZone integration tests."""

    avatar = forms.FileField(widget=ImageDropZone, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_image_drop_zone_default_accept():
    """ImageDropZone defaults accept to 'image/*'."""
    widget = ImageDropZone()
    assert widget.attrs.get("accept") == "image/*"


@pytest.mark.unit
def test_image_drop_zone_accept_param_overrides_default():
    """Passing accept via attrs overrides the default 'image/*'."""
    widget = ImageDropZone(attrs={"accept": ".png,.jpg"})
    assert widget.attrs.get("accept") == ".png,.jpg"


@pytest.mark.unit
def test_image_drop_zone_max_size_stored():
    """max_size kwarg is stored on the widget instance."""
    widget = ImageDropZone(max_size=2 * 1024 * 1024)
    assert widget.max_size == 2 * 1024 * 1024


@pytest.mark.unit
def test_image_drop_zone_no_max_size_by_default():
    """Without max_size, the attribute is None."""
    widget = ImageDropZone()
    assert widget.max_size is None


@pytest.mark.unit
def test_image_drop_zone_get_context_has_accept_display():
    """get_context() adds accept_display when accept is set."""
    widget = ImageDropZone()
    ctx = widget.get_context("avatar", None, {"id": "id_avatar"})
    assert ctx["widget"].get("accept_display") == "Images"


@pytest.mark.unit
def test_image_drop_zone_get_context_accept_display_custom():
    """get_context() formats custom accept values for display."""
    widget = ImageDropZone(attrs={"accept": ".png,.jpg,.jpeg"})
    ctx = widget.get_context("avatar", None, {"id": "id_avatar"})
    assert ctx["widget"]["accept_display"] == "PNG, JPG, JPEG"


@pytest.mark.unit
def test_image_drop_zone_get_context_max_size_display():
    """get_context() adds max_size_display when max_size is set."""
    widget = ImageDropZone(max_size=2 * 1024 * 1024)
    ctx = widget.get_context("avatar", None, {"id": "id_avatar"})
    assert ctx["widget"]["max_size_display"] == "2 MB"


@pytest.mark.unit
def test_image_drop_zone_get_context_no_max_size_display_by_default():
    """Without max_size, max_size_display is absent from context."""
    widget = ImageDropZone()
    ctx = widget.get_context("avatar", None, {"id": "id_avatar"})
    assert "max_size_display" not in ctx["widget"]


@pytest.mark.unit
def test_image_drop_zone_value_from_datadict_returns_file():
    """value_from_datadict reads the uploaded file from FILES."""
    widget = ImageDropZone()
    fake_file = SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
    files = {"avatar": fake_file}
    result = widget.value_from_datadict({}, files, "avatar")
    assert result is fake_file


@pytest.mark.unit
def test_image_drop_zone_value_from_datadict_missing_returns_empty():
    """value_from_datadict returns None when field is absent from FILES."""
    widget = ImageDropZone()
    result = widget.value_from_datadict({}, {}, "avatar")
    assert result is None


@pytest.mark.unit
def test_image_drop_zone_get_context_name_and_id():
    """get_context() passes name and id through to the widget context."""
    widget = ImageDropZone()
    ctx = widget.get_context("avatar", None, {"id": "id_avatar"})
    assert ctx["widget"]["name"] == "avatar"
    assert ctx["widget"]["attrs"]["id"] == "id_avatar"


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_image_drop_zone_renders_image_upload_wrapper():
    """Rendered HTML contains a div.image-upload container."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", class_="image-upload")
    assert wrapper is not None


@pytest.mark.unit
def test_image_drop_zone_renders_file_input():
    """Rendered HTML contains a hidden file input with the correct name."""
    soup = render_widget(ImageDropZone(), name="avatar")
    inp = soup.find("input", {"type": "file"})
    assert inp is not None
    assert inp["name"] == "avatar"


@pytest.mark.unit
def test_image_drop_zone_accept_image_wildcard():
    """File input defaults to accept='image/*'."""
    soup = render_widget(ImageDropZone(), name="avatar")
    inp = soup.find("input", {"type": "file"})
    assert inp["accept"] == "image/*"


@pytest.mark.unit
def test_image_drop_zone_alpine_x_data_present():
    """The wrapper div has an x-data attribute."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper is not None


@pytest.mark.unit
def test_image_drop_zone_alpine_x_data_preview():
    """x-data includes a 'preview:' state property."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert "preview:" in wrapper["x-data"]


@pytest.mark.unit
def test_image_drop_zone_alpine_x_data_dragging():
    """x-data includes a 'dragging:' state property."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert "dragging:" in wrapper["x-data"]


@pytest.mark.unit
def test_image_drop_zone_drag_handlers_present():
    """Wrapper div has @dragover.prevent, @dragleave.prevent, and @drop.prevent."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", attrs={"x-data": True})
    assert wrapper.has_attr("@dragover.prevent")
    assert wrapper.has_attr("@dragleave.prevent")
    assert wrapper.has_attr("@drop.prevent")


@pytest.mark.unit
def test_image_drop_zone_image_preview_element():
    """Rendered HTML contains an <img> element with :src='preview'."""
    soup = render_widget(ImageDropZone())
    img = soup.find("img", {":src": "preview"})
    assert img is not None


@pytest.mark.unit
def test_image_drop_zone_remove_button():
    """Rendered HTML contains a remove button with correct type and aria-label."""
    soup = render_widget(ImageDropZone())
    btn = soup.find("button", class_="image-upload-remove")
    assert btn is not None
    assert btn["type"] == "button"
    assert btn.get("aria-label") == "Remove image"


@pytest.mark.unit
def test_image_drop_zone_image_icon():
    """Rendered HTML contains an SVG icon."""
    soup = render_widget(ImageDropZone())
    svg = soup.find("svg")
    assert svg is not None


@pytest.mark.unit
def test_image_drop_zone_browse_text():
    """Rendered HTML contains the word 'browse'."""
    soup = render_widget(ImageDropZone())
    text = soup.get_text()
    assert "browse" in text.lower()


@pytest.mark.unit
def test_image_drop_zone_custom_accept_override():
    """Passing a custom accept attr overrides image/* in the rendered input."""
    widget = ImageDropZone(attrs={"accept": ".png,.jpg"})
    soup = render_widget(widget, name="img")
    inp = soup.find("input", {"type": "file"})
    assert inp["accept"] == ".png,.jpg"


@pytest.mark.unit
def test_image_drop_zone_wrapper_id_derived_from_input_id():
    """Wrapper div gets id '<input-id>_upload' when an id attr is provided."""
    soup = render_widget(ImageDropZone(), attrs={"id": "id_avatar"})
    wrapper = soup.find("div", class_="image-upload")
    assert wrapper["id"] == "id_avatar_upload"


@pytest.mark.unit
def test_image_drop_zone_no_wrapper_id_without_input_id():
    """Wrapper div has no id when no id attr is provided."""
    soup = render_widget(ImageDropZone())
    wrapper = soup.find("div", class_="image-upload")
    assert not wrapper.has_attr("id")


@pytest.mark.unit
def test_image_drop_zone_id_on_file_input():
    """File input gets the id from attrs."""
    soup = render_widget(ImageDropZone(), name="img", attrs={"id": "id_img"})
    inp = soup.find("input", {"type": "file"})
    assert inp["id"] == "id_img"


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_image_drop_zone_renders_via_form(renderer):
    """ImageDropZone renders correctly when used inside a FormworkForm."""
    form = ImageDropZoneForm()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "avatar"})
    assert inp is not None


@pytest.mark.integration
def test_image_drop_zone_form_wraps_in_fieldset(renderer):
    """Field template wraps the ImageDropZone in a fieldset with a stable id."""
    form = ImageDropZoneForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_avatar_field")
    assert fieldset is not None


@pytest.mark.integration
def test_image_drop_zone_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the file input."""
    form = ImageDropZoneForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "avatar"})
    assert inp.get("aria-invalid") == "true"


@pytest.mark.integration
def test_image_drop_zone_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip with error text."""
    form = ImageDropZoneForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_avatar_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_image_drop_zone_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    form = ImageDropZoneForm(prefix="profile")
    soup = render_form(form, renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "profile-avatar"})
    assert inp is not None
    assert inp["id"] == "id_profile-avatar"


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_image_drop_zone_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """ImageDropZone produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(ImageDropZoneForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(ImageDropZoneForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_image_drop_zone_renders_on_page(uploads_page):
    """ImageDropZone widget is visible on the /uploads/ page."""
    zone = uploads_page.locator(".image-upload").first
    assert zone.is_visible()


@pytest.mark.e2e
def test_image_drop_zone_has_browse_text(uploads_page):
    """ImageDropZone prompts the user to 'browse'."""
    zone = uploads_page.locator(".image-upload").first
    assert "browse" in zone.text_content().lower()


@pytest.mark.e2e
def test_image_drop_zone_accept_image_attr(uploads_page):
    """File input on the /uploads/ page accepts image/*."""
    inp = uploads_page.locator('input[name="avatar"]')
    assert inp.get_attribute("accept") == "image/*"


@pytest.mark.e2e
def test_image_drop_zone_has_icon(uploads_page):
    """ImageDropZone displays the image icon in the prompt area."""
    zone = uploads_page.locator(".image-upload").first
    svg = zone.locator(".image-upload-prompt-icon")
    assert svg.is_visible()


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# There is no dedicated page with a required ImageDropZone that shows
# validation errors — the /uploads/ page marks the field as optional.
# Error-flow tests are deferred until a suitable page is added.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────
#
# ImageDropZone relies on Alpine.js FileReader-based preview (client-side
# blob URL).  After a form morph the server-rendered HTML has no
# preview, and idiomorph would normally clear it.  However the /uploads/
# page does not include htmx morph wiring, so morph resilience cannot
# currently be tested end-to-end.  These tests are left as a gap pending
# a dedicated uploads morph page.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only — produces PNG artifacts in `test-results/`.


@pytest.mark.screenshot
def test_image_drop_zone_screenshot_default(uploads_page, assert_screenshot):
    """Visual snapshot: ImageDropZone in default (empty) state."""
    wrapper = uploads_page.locator(".image-upload").first
    assert_screenshot(wrapper, "image-drop-zone-default.png")


@pytest.mark.screenshot
def test_image_drop_zone_screenshot_restricted(uploads_page, assert_screenshot):
    """Visual snapshot: ImageDropZone with PNG/JPEG restriction (second widget)."""
    wrapper = uploads_page.locator(".image-upload").nth(1)
    assert_screenshot(wrapper, "image-drop-zone-restricted.png")
