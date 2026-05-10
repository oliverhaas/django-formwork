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

    def test_js_registers_htmx_morph_extension(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        assert "htmx.registerExtension" in content
        assert "htmx_before_morph_node" in content

    def test_js_blocks_x_data(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        assert "x-data" in content

    def test_js_preserves_details_open(self):
        result = find("formwork/formwork.js")
        assert result is not None
        content = Path(result).read_text()
        # `open` is added to htmx.config.morphIgnore so the user-toggled
        # state of <details> dropdowns is preserved across morph swaps.
        assert '"open"' in content

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

    def test_css_has_btn_loading(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".btn-loading" in content
        assert "htmx-request" in content

    def test_css_has_btn_loading_variants(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        for variant in ("dots", "ring", "ball", "bars", "infinity"):
            assert f".btn-loading-{variant}" in content, f"Missing btn-loading-{variant}"

    def test_css_has_alert_icon(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".alert-icon::before" in content

    def test_css_has_alert_col(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".alert.alert-col" in content

    def test_css_has_alert_soft(self):
        result = find("formwork/formwork.css")
        assert result is not None
        content = Path(result).read_text()
        assert ".alert-soft" in content
