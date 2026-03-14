"""E2e tests for upload widgets: FileDropZone, ImageDropZone with variations."""

from percy import percy_snapshot


class TestFileDropZone:
    """FileDropZone drag-and-drop file upload widget (multi)."""

    def test_renders(self, uploads_page):
        zone = uploads_page.locator(".dropzone").first
        assert zone.is_visible()
        percy_snapshot(uploads_page, "File Uploads - Default")

    def test_has_browse_text(self, uploads_page):
        zone = uploads_page.locator(".dropzone").first
        assert "browse" in zone.text_content().lower()

    def test_has_hidden_file_input(self, uploads_page):
        inp = uploads_page.locator('input[name="dropzone"]')
        assert inp.get_attribute("type") == "file"

    def test_has_area(self, uploads_page):
        area = uploads_page.locator(".dropzone .dropzone-area").first
        assert area.is_visible()

    def test_accepts_multiple(self, uploads_page):
        inp = uploads_page.locator('input[name="dropzone"]')
        assert inp.get_attribute("multiple") is not None


class TestFileDropZoneRestricted:
    """FileDropZone with PDF-only restriction and 5MB max size."""

    def test_renders(self, uploads_page):
        zone = uploads_page.locator(".dropzone").nth(1)
        assert zone.is_visible()

    def test_accept_attribute(self, uploads_page):
        inp = uploads_page.locator('input[name="dropzone_restricted"]')
        assert inp.get_attribute("accept") == ".pdf"

    def test_shows_size_limit(self, uploads_page):
        zone = uploads_page.locator(".dropzone").nth(1)
        text = zone.text_content().lower()
        assert "5 mb" in text or "5mb" in text

    def test_shows_file_type(self, uploads_page):
        zone = uploads_page.locator(".dropzone").nth(1)
        text = zone.text_content().upper()
        assert "PDF" in text


class TestImageDropZone:
    """ImageDropZone with preview widget."""

    def test_renders(self, uploads_page):
        zone = uploads_page.locator(".image-upload").first
        assert zone.is_visible()

    def test_has_browse_text(self, uploads_page):
        zone = uploads_page.locator(".image-upload").first
        assert "browse" in zone.text_content().lower()

    def test_accept_image_attr(self, uploads_page):
        inp = uploads_page.locator('input[name="avatar"]')
        assert inp.get_attribute("accept") == "image/*"

    def test_has_icon(self, uploads_page):
        zone = uploads_page.locator(".image-upload").first
        svg = zone.locator("svg")
        assert svg.is_visible()


class TestImageDropZoneRestricted:
    """ImageDropZone with PNG/JPEG restriction and 2MB max size."""

    def test_renders(self, uploads_page):
        zone = uploads_page.locator(".image-upload").nth(1)
        assert zone.is_visible()

    def test_accept_attribute(self, uploads_page):
        inp = uploads_page.locator('input[name="avatar_restricted"]')
        assert inp.get_attribute("accept") == ".png,.jpg,.jpeg"

    def test_shows_size_limit(self, uploads_page):
        zone = uploads_page.locator(".image-upload").nth(1)
        text = zone.text_content().lower()
        assert "2 mb" in text or "2mb" in text
