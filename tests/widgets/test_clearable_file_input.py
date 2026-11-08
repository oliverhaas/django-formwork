"""Django's built-in ClearableFileInput under formwork styling, and formwork's one-row ClearableFileInput."""

from __future__ import annotations

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.utils.datastructures import MultiValueDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ClearableFileInput

from .conftest import render_form, render_widget, submit


class _StoredFile:
    """A file a model already stores, as a FileField's initial value."""

    def __init__(self, name: str = "existing-file.txt") -> None:
        self.name = name
        self.url = f"/media/{name}"

    def __str__(self) -> str:
        return self.name


class ClearableFileForm(FormworkForm):
    """Form fixture for ClearableFileInput integration tests."""

    document = forms.FileField(
        widget=forms.ClearableFileInput,
        required=False,
        initial=_StoredFile(),
    )


class DocumentForm(FormworkForm):
    """Form fixture for formwork's ClearableFileInput."""

    document = forms.FileField(
        widget=ClearableFileInput, required=False, initial=_StoredFile("notes/delivery-note.pdf")
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_clearable_file_input_instantiation():
    """ClearableFileInput is a file-typed widget using the clearable template."""
    widget = forms.ClearableFileInput()
    assert widget.input_type == "file"
    assert widget.template_name == "django/forms/widgets/clearable_file_input.html"


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
    soup = render_widget(widget, name="document", value=_StoredFile())
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
    soup = render_widget(widget, name="document", value=_StoredFile())
    assert "existing-file.txt" in soup.get_text()


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_clearable_file_input_renders_via_form(renderer):
    """Field renders as a file input named after the form field."""
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
# Needs a page with a required ClearableFileInput; avatar on /builtin/ is optional.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_clearable_file_input_morph_preserves_clear_checkbox(builtin_page):
    """Checked clear checkbox state survives an htmx form morph."""
    from playwright.sync_api import expect

    checkbox = builtin_page.locator('input[name="avatar-clear"]')
    checkbox.check()
    expect(checkbox).to_be_checked()
    submit(builtin_page)
    expect(builtin_page.locator('input[name="avatar-clear"]')).to_be_checked()


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_clearable_file_input_screenshot_default(builtin_page, assert_screenshot):
    """Visual snapshot: ClearableFileInput in default state."""
    wrapper = builtin_page.locator("#id_avatar_field")
    assert_screenshot(wrapper, "clearable-file-input-default.png")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "name", "icon"),
    [
        ("delivery-notes/2026/delivery-note-0042.pdf", "delivery-note-0042.pdf", "icon-file-text"),
        ("contracts/Agreement.DOCX", "Agreement.DOCX", "icon-file-type"),
        ("exports/orders.csv", "orders.csv", "icon-file-spreadsheet"),
        ("backups/site.tar.gz", "site.tar.gz", "icon-file-archive"),
        ("scans/PDF", "PDF", "icon-file"),
    ],
)
def test_formwork_clearable_file_input_shows_the_stored_file_with_its_type_icon(path, name, icon):
    """The stored file shows by its base name, links to its URL and gets the icon of its type."""
    soup = render_widget(ClearableFileInput(), name="document", value=_StoredFile(path))
    assert soup.select_one(f'a[href="/media/{path}"]').get_text() == name
    assert icon in soup.select_one('i[x-show="storedShown"]')["class"]


@pytest.mark.unit
@pytest.mark.parametrize("required", [False, True])
def test_formwork_clearable_file_input_offers_clearing_only_when_optional(required):
    """An optional field gets the clear box and the restore button; a required one keeps its file."""
    widget = ClearableFileInput()
    widget.is_required = required
    soup = render_widget(widget, name="document", value=_StoredFile(), attrs={"id": "id_document"})
    assert (soup.select_one('input[type="checkbox"][name="document-clear"]') is None) is required
    assert (soup.select_one("#id_document_restore") is None) is required


@pytest.mark.unit
def test_formwork_clearable_file_input_disabled_has_no_buttons():
    """A disabled field shows the stored file without the browse, remove and restore buttons."""
    attrs = {"id": "id_document", "disabled": True}
    soup = render_widget(ClearableFileInput(), name="document", value=_StoredFile(), attrs=attrs)
    assert soup.select("button, .btn") == []
    assert soup.select_one('input[name="document-clear"]').has_attr("disabled")
    assert soup.select_one('input[type="file"]').has_attr("disabled")


@pytest.mark.unit
def test_formwork_clearable_file_input_names_the_accepted_types_and_size():
    """An empty row names the accepted types and the size limit, and the component gets the limit."""
    widget = ClearableFileInput(attrs={"accept": ".pdf"}, max_size=5 * 1024 * 1024)
    soup = render_widget(widget, name="document")
    assert "PDF · Max 5 MB" in soup.get_text()
    assert soup.select_one('[x-data="formworkClearableFileInput"]')["data-max-size"] == "5242880"
    assert soup.select_one('input[type="file"]')["accept"] == ".pdf"


@pytest.mark.unit
def test_formwork_clearable_file_input_multiple_returns_every_upload():
    """With ``multiple`` in attrs, every uploaded file is returned."""
    uploads = [SimpleUploadedFile("a.txt", b"a"), SimpleUploadedFile("b.txt", b"b")]
    widget = ClearableFileInput(attrs={"multiple": True})
    assert widget.value_from_datadict({}, MultiValueDict({"document": uploads}), "document") == uploads


@pytest.mark.integration
def test_formwork_clearable_file_input_keeps_the_clear_box_checked_on_rerender(renderer):
    """A bound form re-renders the clear box checked, and the file input gets no ``checked``."""
    form = DocumentForm(data={"document-clear": "on"})
    assert form.is_valid(), form.errors
    soup = render_form(form, renderer=renderer)
    assert soup.select_one('input[name="document-clear"]').has_attr("checked")
    assert not soup.select_one('input[type="file"]').has_attr("checked")


@pytest.mark.e2e
def test_formwork_clearable_file_input_pick_shows_name_size_and_type_icon(uploads_page):
    """A picked file shows its name, size and type icon; remove empties the input."""
    from playwright.sync_api import expect

    inp = uploads_page.locator('input[name="document"]')
    inp.set_input_files([{"name": "invoice.pdf", "mimeType": "application/pdf", "buffer": b"formwork"}])
    row = uploads_page.locator("#id_document_picker")
    expect(row.get_by_text("invoice.pdf")).to_be_visible()
    expect(row.get_by_text("8 B", exact=True)).to_be_visible()
    expect(row.locator("i.icon-file-text")).to_be_visible()
    uploads_page.locator("#id_document_remove").click()
    expect(row.get_by_text("No file chosen")).to_be_visible()
    assert inp.evaluate("el => el.files.length") == 0


@pytest.mark.e2e
def test_formwork_clearable_file_input_row_and_label_open_the_picker(uploads_page):
    """A click anywhere on the row opens the file picker, and the label names a focusable input."""
    from playwright.sync_api import expect

    with uploads_page.expect_file_chooser(timeout=3000):
        uploads_page.locator("#id_document_picker").get_by_text("No file chosen").click()
    inp = uploads_page.get_by_label("Document", exact=True)
    inp.focus()
    expect(inp).to_be_focused()
    with uploads_page.expect_file_chooser(timeout=3000):
        uploads_page.keyboard.press("Space")


@pytest.mark.e2e
def test_formwork_clearable_file_input_remove_and_restore_a_stored_file(uploads_page):
    """Remove checks the clear box and offers to keep the file; keep unchecks it again."""
    from playwright.sync_api import expect

    clear = uploads_page.locator('input[name="document_stored-clear"]')
    restore = uploads_page.locator("#id_document_stored_restore")
    expect(restore).to_be_hidden()
    uploads_page.locator("#id_document_stored_remove").click()
    expect(clear).to_be_checked()
    restore.click()
    expect(clear).not_to_be_checked()
    expect(uploads_page.locator("#id_document_stored_remove")).to_be_visible()


@pytest.mark.e2e
def test_formwork_clearable_file_input_pick_after_clear_saves_the_new_file(uploads_page):
    """A pick after remove unchecks the clear box, so Django gets no contradiction and the form saves."""
    from playwright.sync_api import expect

    clear = uploads_page.locator('input[name="document_stored-clear"]')
    uploads_page.locator("#id_document_stored_remove").click()
    expect(clear).to_be_checked()
    uploads_page.locator('input[name="document_stored"]').set_input_files(
        [{"name": "photo.JPG", "mimeType": "image/jpeg", "buffer": b"formwork"}],
    )
    expect(clear).not_to_be_checked()
    expect(uploads_page.locator("#id_document_stored_picker i.icon-file-image")).to_be_visible()
    uploads_page.get_by_role("button", name="Submit").click()
    expect(uploads_page.get_by_role("button", name="Delete")).to_be_visible()


@pytest.mark.e2e
def test_formwork_clearable_file_input_required_stored_file_has_no_remove(uploads_page):
    """A required field keeps its stored file; only a picked replacement can be removed."""
    from playwright.sync_api import expect

    remove = uploads_page.locator("#id_contract_remove")
    expect(remove).to_be_hidden()
    uploads_page.locator('input[name="contract"]').set_input_files(
        [{"name": "contract.docx", "mimeType": "application/octet-stream", "buffer": b"formwork"}],
    )
    expect(remove).to_be_visible()
    remove.click()
    expect(uploads_page.locator("#id_contract_picker").get_by_text("framework-agreement.docx")).to_be_visible()


@pytest.mark.e2e
def test_formwork_clearable_file_input_multiple_files_show_a_count(uploads_page):
    """Several files show their count, their total size and the icon for several files."""
    from playwright.sync_api import expect

    uploads_page.locator('input[name="documents"]').set_input_files(
        [
            {"name": "a.txt", "mimeType": "text/plain", "buffer": b"a"},
            {"name": "b.pdf", "mimeType": "application/pdf", "buffer": b"bb"},
        ],
    )
    row = uploads_page.locator("#id_documents_picker")
    expect(row.get_by_text("2 files selected")).to_be_visible()
    expect(row.get_by_text("3 B", exact=True)).to_be_visible()
    expect(row.locator("i.icon-files")).to_be_visible()


@pytest.mark.e2e
def test_formwork_clearable_file_input_rejects_wrong_type_with_alert(uploads_page):
    """The PDF-only row rejects another type, announces it and empties the input."""
    from playwright.sync_api import expect

    inp = uploads_page.locator('input[name="document_restricted"]')
    inp.set_input_files([{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"formwork"}])
    expect(uploads_page.locator("#id_document_restricted_picker").get_by_role("alert")).to_have_text(
        "File type not accepted",
    )
    assert inp.evaluate("el => el.files.length") == 0


@pytest.mark.screenshot
def test_formwork_clearable_file_input_screenshot_stored(uploads_page, assert_screenshot):
    """Visual snapshot: formwork's ClearableFileInput with a stored file."""
    assert_screenshot(uploads_page.locator("#id_document_stored_field"), "clearable-file-input-stored.png")


@pytest.mark.screenshot
def test_formwork_clearable_file_input_screenshot_restricted(uploads_page, assert_screenshot):
    """Visual snapshot: formwork's ClearableFileInput, empty, with a PDF restriction and a size limit."""
    assert_screenshot(uploads_page.locator("#id_document_restricted_field"), "clearable-file-input-restricted.png")
