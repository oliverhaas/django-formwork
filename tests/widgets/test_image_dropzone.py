from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.widgets import FILE_INPUT_CONTRADICTION

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ImageDropzoneInput

from .conftest import render_form, render_widget

STORED = SimpleNamespace(url="/media/logo.png")
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
)


class ImageDropzoneForm(FormworkForm):
    """FileField instead of ImageField: Pillow is not a project dependency."""

    avatar = forms.FileField(widget=ImageDropzoneInput, required=True)


class OptionalImageForm(FormworkForm):
    avatar = forms.FileField(widget=ImageDropzoneInput, required=False)


def _upload():
    return SimpleUploadedFile("dot.png", PNG_1X1, content_type="image/png")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "attrs", "src"),
    [
        (STORED, {}, "/media/logo.png"),
        (STORED, {"preview_url": ""}, None),
        (None, {"preview_url": "/temp/logo.png"}, "/temp/logo.png"),
    ],
)
def test_preview_url_overrides_the_stored_file(value, attrs, src):
    """An explicit ``preview_url`` wins over the stored file, and ``""`` hides the preview."""
    soup = render_widget(ImageDropzoneInput(), name="logo", value=value, attrs=attrs)
    img = soup.select_one("img[src]")
    assert (img["src"] if img else None) == src


@pytest.mark.unit
def test_image_dropzone_preview_url_kwarg():
    """``preview_url=`` on the widget previews a file the field does not store."""
    soup = render_widget(ImageDropzoneInput(preview_url="/temp/a.png"), name="logo")
    assert soup.select_one("img[src]")["src"] == "/temp/a.png"


@pytest.mark.unit
def test_image_dropzone_preview_attrs_do_not_leak_onto_the_input():
    """``hint`` and ``preview_url`` passed as attrs are consumed, not rendered as attributes."""
    soup = render_widget(ImageDropzoneInput(), name="logo", attrs={"hint": "Square works best", "preview_url": ""})
    inp = soup.select_one('input[type="file"]')
    assert not inp.has_attr("hint")
    assert not inp.has_attr("preview_url")
    assert "Square works best" in soup.get_text()


@pytest.mark.unit
def test_image_dropzone_stored_preview_has_a_clear_button():
    """A stored image shows a remove button that sets the clear flag."""
    soup = render_widget(ImageDropzoneInput(), name="logo", value=STORED, attrs={"id": "id_logo"})
    button = soup.select_one("#id_logo_clear")
    assert button["type"] == "button"
    assert button["@click"] == "clear()"
    assert button["aria-label"] == "Remove image"
    clear = soup.select_one('input[type="hidden"]')
    assert clear["name"] == "clear_logo"
    assert clear["value"] == ""


@pytest.mark.unit
@pytest.mark.parametrize(
    ("attrs", "expected"),
    [({}, "image/*"), ({"accept": ".png,.jpg"}, ".png,.jpg")],
)
def test_image_dropzone_accept(attrs, expected):
    """The file input accepts images unless the caller narrows it."""
    soup = render_widget(ImageDropzoneInput(attrs=attrs), name="logo")
    assert soup.select_one('input[type="file"]')["accept"] == expected


@pytest.mark.unit
def test_image_dropzone_shows_accept_and_max_size():
    """The prompt names the accepted types and the size limit."""
    widget = ImageDropzoneInput(attrs={"accept": ".png,.jpg"}, max_size=2 * 1024 * 1024)
    soup = render_widget(widget, name="logo")
    assert "PNG, JPG · Max 2 MB" in soup.get_text()
    assert soup.select_one('[x-data="formworkImageDropzone"]')["data-max-size"] == "2097152"


@pytest.mark.unit
def test_image_dropzone_without_max_size_has_no_size_limit():
    """Without ``max_size`` the component gets no limit to enforce."""
    soup = render_widget(ImageDropzoneInput(), name="logo")
    assert not soup.select_one('[x-data="formworkImageDropzone"]').has_attr("data-max-size")


@pytest.mark.unit
def test_image_dropzone_error_messages_come_from_the_template():
    """Client-side error text rides in data attributes, so it is translatable (D8)."""
    root = render_widget(ImageDropzoneInput(), name="logo").select_one('[x-data="formworkImageDropzone"]')
    assert root["data-type-error"] == "File type not accepted"
    assert root["data-size-error"] == "File too large"


@pytest.mark.unit
def test_image_dropzone_drop_area_is_the_file_input_label():
    """The drop area is the label of a focusable file input that carries the id (R9)."""
    soup = render_widget(ImageDropzoneInput(), name="logo", attrs={"id": "id_logo"})
    label = soup.select_one("label")
    assert label["for"] == "id_logo"
    assert label.has_attr("@drop.prevent")
    inp = label.select_one("input#id_logo")
    assert inp["type"] == "file"
    assert "sr-only" in inp["class"]


@pytest.mark.unit
def test_image_dropzone_error_element_role_alert():
    """The client-side error line is announced."""
    soup = render_widget(ImageDropzoneInput(), name="logo")
    assert soup.select_one("p[x-text='error']")["role"] == "alert"


@pytest.mark.unit
def test_image_dropzone_value_from_datadict_returns_the_upload():
    """An upload is read from FILES."""
    upload = _upload()
    assert ImageDropzoneInput().value_from_datadict({}, {"logo": upload}, "logo") is upload


@pytest.mark.unit
@pytest.mark.parametrize(("data", "files", "expected"), [({"clear_logo": "true"}, {}, False), ({}, {}, None)])
def test_image_dropzone_clear_flag(data, files, expected):
    """The clear flag reads as False, which tells a model form to drop the stored file."""
    assert ImageDropzoneInput().value_from_datadict(data, files, "logo") is expected


@pytest.mark.unit
def test_image_dropzone_clear_with_upload_contradicts():
    """Clearing and uploading at once is a contradiction, as in ClearableFileInput."""
    result = ImageDropzoneInput().value_from_datadict({"clear_logo": "true"}, {"logo": _upload()}, "logo")
    assert result is FILE_INPUT_CONTRADICTION


@pytest.mark.unit
def test_image_dropzone_required_ignores_the_clear_flag():
    """A required field cannot be cleared."""
    widget = ImageDropzoneInput()
    widget.is_required = True
    assert widget.value_from_datadict({"clear_logo": "true"}, {}, "logo") is None


@pytest.mark.unit
@pytest.mark.parametrize(("data", "omitted"), [({}, True), ({"clear_logo": "true"}, False)])
def test_image_dropzone_value_omitted_from_data(data, omitted):
    """A clear flag counts as submitted data, so a model form saves it."""
    assert ImageDropzoneInput().value_omitted_from_data(data, {}, "logo") is omitted


@pytest.mark.integration
def test_image_dropzone_clear_flag_empties_an_optional_field():
    """Submitting the clear flag cleans an optional field to False."""
    form = OptionalImageForm(data={"clear_avatar": "true"}, files={}, initial={"avatar": STORED})
    assert form.is_valid()
    assert form.cleaned_data["avatar"] is False


@pytest.mark.integration
def test_image_dropzone_renders_via_form(renderer):
    """Field renders a file input named after the form field, targeted by the field label."""
    soup = render_form(ImageDropzoneForm(), renderer=renderer)
    inp = soup.find("input", {"type": "file", "name": "avatar"})
    assert inp["id"] == "id_avatar"
    assert soup.find("label", id="id_avatar_label")["for"] == "id_avatar"


@pytest.mark.integration
def test_image_dropzone_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the file input."""
    form = ImageDropzoneForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", {"type": "file", "name": "avatar"})["aria-invalid"] == "true"


@pytest.mark.integration
def test_image_dropzone_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip with error text."""
    form = ImageDropzoneForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert "required" in soup.find(id="id_avatar_error", class_="tooltip-content").text.lower()


@pytest.mark.integration
def test_image_dropzone_form_prefix_handling(renderer):
    """Form prefix propagates to widget name, id and clear flag."""
    soup = render_form(ImageDropzoneForm(prefix="profile"), renderer=renderer)
    assert soup.find("input", {"type": "file", "name": "profile-avatar"})["id"] == "id_profile-avatar"
    assert soup.find("input", {"type": "hidden", "name": "clear_profile-avatar"}) is not None


def _pick(page, name, *, filename="dot.png", mime="image/png", buffer=PNG_1X1):
    page.locator(f'input[name="{name}"]').set_input_files([{"name": filename, "mimeType": mime, "buffer": buffer}])


@pytest.mark.e2e
def test_image_dropzone_preview_and_remove(uploads_page):
    """Selecting an image shows the FileReader preview; remove discards it."""
    from playwright.sync_api import expect

    _pick(uploads_page, "avatar")
    field = uploads_page.locator("#id_avatar_field")
    preview = field.locator("img[src^='data:image/png']")
    expect(preview).to_be_visible()
    field.get_by_role("button", name="Remove image").click()
    expect(preview).not_to_be_attached()
    expect(field.get_by_text("Drag and drop an image here")).to_be_visible()
    assert uploads_page.locator('input[name="avatar"]').evaluate("el => el.files.length") == 0


@pytest.mark.e2e
def test_image_dropzone_rejected_type_clears_stale_preview(uploads_page):
    """Picking a disallowed file type after a valid one shows the error, not the old preview."""
    from playwright.sync_api import expect

    _pick(uploads_page, "avatar_restricted")
    field = uploads_page.locator("#id_avatar_restricted_field")
    preview = field.locator("img[src^='data:image/png']")
    expect(preview).to_be_visible()
    _pick(uploads_page, "avatar_restricted", filename="anim.gif", mime="image/gif")
    error = field.locator("p[role='alert'][x-text='error']")
    expect(error).to_have_text("File type not accepted")
    expect(preview).not_to_be_attached()


@pytest.mark.e2e
def test_image_dropzone_oversize_pick_clears_stale_preview(uploads_page):
    """Picking an oversize file after a valid one shows the error, not the old preview."""
    from playwright.sync_api import expect

    _pick(uploads_page, "avatar_restricted")
    field = uploads_page.locator("#id_avatar_restricted_field")
    preview = field.locator("img[src^='data:image/png']")
    expect(preview).to_be_visible()
    _pick(uploads_page, "avatar_restricted", filename="big.png", buffer=b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 1))
    error = field.locator("p[role='alert'][x-text='error']")
    expect(error).to_have_text("File too large")
    expect(preview).not_to_be_attached()


@pytest.mark.e2e
def test_image_dropzone_stored_image_can_be_replaced(uploads_page):
    """After the stored image is removed, a new pick uploads in its place instead of contradicting the clear."""
    from playwright.sync_api import expect

    field = uploads_page.locator("#id_avatar_stored_field")
    stored = field.locator("img[src^='data:image/gif']")
    drop_area = field.get_by_text("Drag and drop an image here")
    clear = field.locator('input[name="clear_avatar_stored"]')
    expect(stored).to_be_visible()
    expect(drop_area).to_be_hidden()
    field.get_by_role("button", name="Remove image").click()
    expect(stored).to_be_hidden()
    expect(drop_area).to_be_visible()
    expect(clear).to_have_value("true")
    _pick(uploads_page, "avatar_stored")
    expect(field.locator("img[src^='data:image/png']")).to_be_visible()
    expect(clear).to_have_value("")


@pytest.mark.screenshot
def test_image_dropzone_screenshot_default(uploads_page, assert_screenshot):
    """Visual snapshot: ImageDropzoneInput in default (empty) state."""
    assert_screenshot(uploads_page.locator("#id_avatar_field"), "image-drop-zone-default.png")


@pytest.mark.screenshot
def test_image_dropzone_screenshot_restricted(uploads_page, assert_screenshot):
    """Visual snapshot: ImageDropzoneInput with a PNG/JPEG restriction."""
    assert_screenshot(uploads_page.locator("#id_avatar_restricted_field"), "image-drop-zone-restricted.png")
