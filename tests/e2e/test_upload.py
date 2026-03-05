"""E2e tests for upload widgets: DropZone, ImageUpload."""


class TestDropZone:
    """DropZone drag-and-drop file upload widget."""

    def test_renders(self, widget_page):
        zone = widget_page.locator(".dropzone")
        assert zone.is_visible()

    def test_has_browse_text(self, widget_page):
        zone = widget_page.locator(".dropzone")
        assert "browse" in zone.text_content().lower()

    def test_has_hidden_file_input(self, widget_page):
        inp = widget_page.locator('input[name="dropzone"]')
        assert inp.get_attribute("type") == "file"

    def test_has_area(self, widget_page):
        area = widget_page.locator(".dropzone .dropzone-area")
        assert area.is_visible()


class TestImageUpload:
    """ImageUpload with preview widget."""

    def test_renders(self, widget_page):
        zone = widget_page.locator(".image-upload")
        assert zone.is_visible()

    def test_has_browse_text(self, widget_page):
        zone = widget_page.locator(".image-upload")
        assert "browse" in zone.text_content().lower()

    def test_accept_image_attr(self, widget_page):
        inp = widget_page.locator('input[name="avatar"]')
        assert inp.get_attribute("accept") == "image/*"

    def test_has_icon(self, widget_page):
        zone = widget_page.locator(".image-upload")
        svg = zone.locator("svg")
        assert svg.is_visible()
