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
