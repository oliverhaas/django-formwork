from __future__ import annotations

import json
import re

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from django_formwork.fields import MultipleFileField
from django_formwork.forms import FormworkForm
from django_formwork.widgets import FileDropzoneInput

from .conftest import render_form, render_widget


class FileDropzoneForm(FormworkForm):
    """Form fixture for FileDropzoneInput integration tests."""

    upload = forms.FileField(widget=FileDropzoneInput, required=True)


def _multiple_file_form(*uploads, required=False):
    class MultipleFileForm(FormworkForm):
        files = MultipleFileField(required=required)

    return MultipleFileForm(data={}, files=MultiValueDict({"files": list(uploads)}))


def _root(soup):
    return soup.select_one('[x-data="formworkFileDropzone"]')


@pytest.mark.unit
@pytest.mark.parametrize(
    ("attrs", "max_size", "text"),
    [
        ({"accept": ".pdf"}, 5 * 1024 * 1024, "PDF · Max 5 MB"),
        ({"accept": "image/*"}, None, "Images"),
        ({}, 512, "Max 512 B"),
    ],
)
def test_file_dropzone_names_the_accepted_types_and_size(attrs, max_size, text):
    """The prompt names the accepted types and the size limit."""
    soup = render_widget(FileDropzoneInput(attrs=attrs, max_size=max_size), name="upload")
    assert soup.select_one(".dropzone-accept-text").get_text() == text


@pytest.mark.unit
def test_file_dropzone_without_restrictions_has_no_accept_line():
    """With no ``accept`` and no ``max_size`` the restriction line is left out."""
    soup = render_widget(FileDropzoneInput(), name="upload")
    assert soup.select_one(".dropzone-accept-text") is None
    assert not _root(soup).has_attr("data-max-size")


@pytest.mark.unit
def test_file_dropzone_max_size_reaches_the_component():
    """``max_size`` rides in a data attribute the component checks picks against."""
    soup = render_widget(FileDropzoneInput(max_size=5 * 1024 * 1024), name="upload")
    assert _root(soup)["data-max-size"] == "5242880"


@pytest.mark.unit
def test_file_dropzone_messages_come_from_the_template():
    """Client-side text rides in data attributes, so it is translatable (D8)."""
    root = _root(render_widget(FileDropzoneInput(), name="upload"))
    assert root["data-type-error"] == "File type not accepted"
    assert root["data-size-error"] == "File too large"
    assert json.loads(root["data-count-text"]) == {
        "one": "%(count)s file selected",
        "other": "%(count)s files selected",
    }


@pytest.mark.unit
def test_file_dropzone_file_input_keeps_id_and_attrs_but_not_class():
    """The file input carries the id and the caller's attributes; the template owns the class."""
    widget = FileDropzoneInput(attrs={"multiple": True, "accept": ".pdf", "class": "x"})
    soup = render_widget(widget, name="upload", attrs={"id": "id_upload"})
    inp = soup.select_one('input[type="file"]')
    assert inp["id"] == "id_upload"
    assert inp["name"] == "upload"
    assert inp["accept"] == ".pdf"
    assert inp.has_attr("multiple")
    assert "x" not in inp["class"]
    assert soup.select_one(".dropzone")["id"] == "id_upload_dropzone"


@pytest.mark.unit
def test_file_dropzone_single_file_by_default():
    """Without ``multiple`` the input picks one file."""
    soup = render_widget(FileDropzoneInput(), name="upload")
    assert not soup.select_one('input[type="file"]').has_attr("multiple")


@pytest.mark.unit
def test_file_dropzone_remove_button_and_error_line():
    """The remove button is named, and the error line is announced."""
    soup = render_widget(FileDropzoneInput(), name="upload")
    button = soup.select_one(".dropzone-remove")
    assert button["type"] == "button"
    assert button["aria-label"] == "Remove file"
    assert soup.select_one(".dropzone-error")["role"] == "alert"


@pytest.mark.unit
def test_file_dropzone_icons_are_hidden_from_screen_readers():
    """All icons are decoration."""
    icons = render_widget(FileDropzoneInput(), name="upload").select("i.icon")
    assert icons
    assert all(i["aria-hidden"] == "true" for i in icons)


@pytest.mark.unit
def test_file_dropzone_value_from_datadict_single_file():
    """A single upload in a real MultiValueDict yields the file, not a list."""
    upload = SimpleUploadedFile("notes.txt", b"formwork")
    result = FileDropzoneInput().value_from_datadict({}, MultiValueDict({"upload": [upload]}), "upload")
    assert result is upload


@pytest.mark.unit
def test_file_dropzone_value_from_datadict_multiple_returns_list():
    """With ``multiple`` in attrs, every uploaded file is returned."""
    uploads = [SimpleUploadedFile("a.txt", b"a"), SimpleUploadedFile("b.txt", b"b")]
    widget = FileDropzoneInput(attrs={"multiple": True})
    assert widget.value_from_datadict({}, MultiValueDict({"upload": uploads}), "upload") == uploads


@pytest.mark.unit
def test_file_dropzone_value_from_datadict_missing_returns_none():
    """No upload reads as None."""
    assert FileDropzoneInput().value_from_datadict({}, {}, "upload") is None


@pytest.mark.integration
def test_file_dropzone_single_upload_form_is_valid():
    """A FileField with the widget cleans a single upload."""
    upload = SimpleUploadedFile("notes.txt", b"formwork")
    form = FileDropzoneForm(data={}, files=MultiValueDict({"upload": [upload]}))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["upload"].name == "notes.txt"


@pytest.mark.integration
def test_multiple_file_field_cleans_every_upload_to_a_list():
    """The default multi-file dropzone hands over every file, and the field keeps them all."""
    form = _multiple_file_form(SimpleUploadedFile("a.txt", b"a"), SimpleUploadedFile("b.txt", b"b"))
    assert form.is_valid(), form.errors
    assert [upload.name for upload in form.cleaned_data["files"]] == ["a.txt", "b.txt"]


@pytest.mark.integration
@pytest.mark.parametrize(("required", "errors"), [(True, ["required"]), (False, [])])
def test_multiple_file_field_without_files(required, errors):
    """No upload fails a required field and cleans to an empty list otherwise."""
    form = _multiple_file_form(required=required)
    assert form.is_valid() is (not errors)
    assert [error["code"] for error in form.errors.get_json_data().get("files", [])] == errors
    assert form.has_changed() is False
    if not errors:
        assert form.cleaned_data["files"] == []


@pytest.mark.integration
def test_multiple_file_field_checks_each_file():
    """An empty file among several fails the field like a single empty upload would."""
    form = _multiple_file_form(SimpleUploadedFile("a.txt", b"a"), SimpleUploadedFile("empty.txt", b""))
    assert not form.is_valid()
    assert form.errors.get_json_data()["files"][0]["code"] == "empty"


@pytest.mark.integration
def test_file_dropzone_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the file input."""
    form = FileDropzoneForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert soup.find("input", {"type": "file", "name": "upload"})["aria-invalid"] == "true"


@pytest.mark.integration
def test_file_dropzone_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip with error text."""
    form = FileDropzoneForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    assert "required" in soup.find(id="id_upload_error", class_="tooltip-content").text.lower()


@pytest.mark.integration
def test_file_dropzone_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id."""
    soup = render_form(FileDropzoneForm(prefix="doc"), renderer=renderer)
    assert soup.find("input", {"type": "file", "name": "doc-upload"})["id"] == "id_doc-upload"


@pytest.mark.e2e
def test_file_dropzone_selecting_file_shows_preview(uploads_page):
    """Choosing a file shows its name, formatted size and type icon; remove empties the input."""
    from playwright.sync_api import expect

    inp = uploads_page.locator('input[name="dropzone"]')
    inp.set_input_files([{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"formwork"}])
    zone = uploads_page.locator("#id_dropzone_dropzone")
    expect(zone.locator(".dropzone-file-name")).to_have_text("notes.txt")
    expect(zone.locator(".dropzone-file-size")).to_have_text("8 B")
    expect(zone.locator(".dropzone-file-icon")).to_have_class(re.compile(r"\bicon-file-type\b"))
    zone.locator(".dropzone-remove").click()
    expect(zone.locator(".dropzone-browse")).to_be_visible()
    assert inp.evaluate("el => el.files.length") == 0


@pytest.mark.e2e
def test_file_dropzone_field_label_names_a_focusable_input(uploads_page):
    """The field label targets the file input, which takes the focus and opens the picker (R9)."""
    from playwright.sync_api import expect

    inp = uploads_page.get_by_label("Drop zone (multi)")
    inp.focus()
    expect(inp).to_be_focused()
    with uploads_page.expect_file_chooser(timeout=3000):
        uploads_page.keyboard.press("Space")


@pytest.mark.e2e
def test_file_dropzone_multiple_files_show_a_count(uploads_page):
    """Several files show their count, their names and the icon for several files."""
    from playwright.sync_api import expect

    uploads_page.locator('input[name="dropzone"]').set_input_files(
        [
            {"name": "a.txt", "mimeType": "text/plain", "buffer": b"a"},
            {"name": "b.txt", "mimeType": "text/plain", "buffer": b"b"},
        ],
    )
    zone = uploads_page.locator("#id_dropzone_dropzone")
    expect(zone.locator(".dropzone-file-name")).to_have_text("2 files selected")
    expect(zone.locator(".dropzone-file-size")).to_have_text("a.txt, b.txt")
    expect(zone.locator(".dropzone-file-icon")).to_have_class(re.compile(r"\bicon-files\b"))


@pytest.mark.e2e
def test_file_dropzone_multiple_files_submit(uploads_page):
    """Several files picked in the browser reach a MultipleFileField and the form saves."""
    from playwright.sync_api import expect

    uploads_page.locator('input[name="dropzone"]').set_input_files(
        [
            {"name": "a.txt", "mimeType": "text/plain", "buffer": b"a"},
            {"name": "b.txt", "mimeType": "text/plain", "buffer": b"b"},
        ],
    )
    uploads_page.get_by_role("button", name="Submit").click()
    expect(uploads_page.get_by_role("button", name="Delete")).to_be_visible()


@pytest.mark.e2e
def test_file_dropzone_rejects_wrong_type_with_alert(uploads_page):
    """The restricted zone rejects a non-PDF file, announces it and empties the input."""
    from playwright.sync_api import expect

    inp = uploads_page.locator('input[name="dropzone_restricted"]')
    inp.set_input_files([{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"formwork"}])
    error = uploads_page.locator("#id_dropzone_restricted_dropzone .dropzone-error")
    expect(error).to_have_text("File type not accepted")
    assert inp.evaluate("el => el.files.length") == 0


@pytest.mark.screenshot
def test_file_dropzone_screenshot_default(uploads_page, assert_screenshot):
    """Visual snapshot: FileDropzoneInput in default (empty) state."""
    assert_screenshot(uploads_page.locator("#id_dropzone_dropzone"), "file-drop-zone-default.png")


@pytest.mark.screenshot
def test_file_dropzone_screenshot_restricted(uploads_page, assert_screenshot):
    """Visual snapshot: FileDropzoneInput with PDF restriction and size limit."""
    assert_screenshot(uploads_page.locator("#id_dropzone_restricted_dropzone"), "file-drop-zone-restricted.png")
