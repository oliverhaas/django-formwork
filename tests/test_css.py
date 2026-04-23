from pathlib import Path

from django.contrib.staticfiles.finders import find


class TestStaticFiles:
    def test_css_file_findable(self):
        result = find("formwork/formwork.css")
        assert result is not None

    def test_css_file_not_empty(self):
        result = find("formwork/formwork.css")
        assert result is not None
        path = Path(result)
        assert path.stat().st_size > 0

    def test_css_has_errorlist_reset(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".errorlist" in content

    def test_js_file_findable(self):
        result = find("formwork/formwork.js")
        assert result is not None

    def test_js_file_not_empty(self):
        result = find("formwork/formwork.js")
        assert result is not None
        path = Path(result)
        assert path.stat().st_size > 0

    def test_js_wraps_idiomorph_morph(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        assert "Idiomorph.morph" in content

    def test_js_blocks_x_data(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        assert "x-data" in content

    def test_js_preserves_details_open(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        assert "DETAILS" in content

    def test_css_has_btn_icon(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".btn-icon::before" in content

    def test_css_has_btn_icon_end(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".btn-icon-end::after" in content
