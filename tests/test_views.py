"""Tests for FormworkSearchView and FormworkValidateView."""

from bs4 import BeautifulSoup
from django.test import RequestFactory
from django.utils.safestring import mark_safe

from django_formwork.views import FormworkSearchView, FormworkValidateView


class CitySearchView(FormworkSearchView):
    """Test subclass returning city results."""

    def get_results(self, query, **kwargs):
        cities = [
            {"value": "nyc", "label": "New York"},
            {"value": "ldn", "label": "London"},
            {"value": "tyo", "label": "Tokyo"},
            {"value": "par", "label": "Paris"},
        ]
        if query:
            cities = [c for c in cities if query.lower() in c["label"].lower()]
        return cities


class IconSearchView(FormworkSearchView):
    """Test subclass returning results with icons."""

    def get_results(self, query, **kwargs):
        return [
            {"value": "py", "label": "Python", "icon": mark_safe('<img src="py.svg">')},
        ]


factory = RequestFactory()


class TestFormworkSearchViewSearchSelect:
    def test_returns_html(self):
        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/html; charset=utf-8"

    def test_returns_all_results_for_empty_query(self):
        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 4

    def test_filters_results(self):
        request = factory.get("/search/", {"q": "lon", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 1
        assert "London" in buttons[0].get_text()

    def test_no_results_message(self):
        request = factory.get("/search/", {"q": "zzz", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        assert b"No results" in response.content

    def test_data_value_and_label_attrs(self):
        request = factory.get("/search/", {"q": "new", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        btn = soup.find("button")
        assert btn["data-value"] == "nyc"
        assert btn["data-label"] == "New York"

    def test_option_role(self):
        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        options = soup.find_all("li", {"role": "option"})
        assert len(options) == 4

    def test_icon_support(self):
        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = IconSearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        icon = soup.find("img", {"src": "py.svg"})
        assert icon is not None


class TestFormworkSearchViewComboBox:
    def test_returns_suggestion_buttons(self):
        request = factory.get("/search/", {"q": "", "type": "combobox"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        buttons = soup.find_all("button")
        assert len(buttons) == 4

    def test_data_suggestion_attr(self):
        request = factory.get("/search/", {"q": "par", "type": "combobox"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        btn = soup.find("button")
        assert btn["data-suggestion"] == "Paris"

    def test_no_data_value_attr(self):
        """ComboBox buttons have data-suggestion, not data-value."""
        request = factory.get("/search/", {"q": "", "type": "combobox"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        btn = soup.find("button")
        assert not btn.has_attr("data-value")


class TestFormworkSearchViewMultiSelect:
    def test_returns_checkbox_options(self):
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        checkboxes = soup.find_all("input", {"type": "checkbox"})
        assert len(checkboxes) == 4

    def test_checkboxes_have_no_name(self):
        """htmx mode: checkboxes are visual only, hidden inputs handle submission."""
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        cb = soup.find("input", {"type": "checkbox"})
        assert not cb.has_attr("name")

    def test_alpine_x_init_on_checkboxes(self):
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        cb = soup.find("input", {"type": "checkbox"})
        assert cb.has_attr("x-init")
        assert "selected.has" in cb["x-init"]

    def test_alpine_change_handler_on_checkboxes(self):
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        cb = soup.find("input", {"type": "checkbox"})
        assert cb.has_attr("@change")
        assert "toggle(" in cb["@change"]

    def test_multiselect_class_on_checkboxes(self):
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        cb = soup.find("input", {"type": "checkbox"})
        assert "multiselect" in cb.get("class", [])

    def test_checkmark_span(self):
        request = factory.get("/search/", {"q": "", "type": "multiselect", "name": "lang"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        check = soup.find("span", class_="formwork-check")
        assert check is not None


class TestFormworkSearchViewDefaults:
    def test_default_widget_type(self):
        """Default widget_type is search_select."""
        request = factory.get("/search/", {"q": ""})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        # search_select has data-value attrs
        btn = soup.find("button")
        assert btn.has_attr("data-value")

    def test_type_override_via_query_param(self):
        request = factory.get("/search/", {"q": "", "type": "combobox"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        btn = soup.find("button")
        assert btn.has_attr("data-suggestion")

    def test_empty_base_class_results(self):
        """Base class returns empty results."""
        request = factory.get("/search/", {"q": "test"})
        response = FormworkSearchView.as_view()(request)
        assert b"No results" in response.content

    def test_request_passed_to_get_results(self):
        """get_results receives request as kwarg."""
        received = {}

        class TrackingView(FormworkSearchView):
            def get_results(self, query, **kwargs):
                received["request"] = kwargs.get("request")
                return []

        request = factory.get("/search/", {"q": "test"})
        TrackingView.as_view()(request)
        assert received["request"] is request

    def test_query_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped from query."""
        received = {}

        class TrackingView(FormworkSearchView):
            def get_results(self, query, **kwargs):
                received["query"] = query
                return []

        request = factory.get("/search/", {"q": "  hello  "})
        TrackingView.as_view()(request)
        assert received["query"] == "hello"


# ---------------------------------------------------------------------------
# FormworkValidateView tests
# ---------------------------------------------------------------------------


class SpellCheckView(FormworkValidateView):
    """Test subclass that flags 'badword' as an error."""

    def get_errors(self, text, **kwargs):
        errors = []
        start = 0
        while True:
            idx = text.find("badword", start)
            if idx == -1:
                break
            errors.append(
                {
                    "message": "Prohibited word found",
                    "start": idx,
                    "end": idx + 7,
                },
            )
            start = idx + 7
        return errors


class MessageOnlyView(FormworkValidateView):
    """Test subclass that returns errors without positions."""

    def get_errors(self, text, **kwargs):
        if len(text) > 10:
            return [{"message": "Text is too long"}]
        return []


class TestFormworkValidateViewHighlighting:
    def test_returns_html(self):
        request = factory.post("/validate/", {"text": "hello", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        assert response.status_code == 200

    def test_no_errors_returns_escaped_text(self):
        request = factory.post("/validate/", {"text": "hello world", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        assert response.content.decode() == "hello world"

    def test_marks_error_spans(self):
        request = factory.post("/validate/", {"text": "say badword here", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        mark = soup.find("mark")
        assert mark is not None
        assert mark.string == "badword"

    def test_preserves_surrounding_text(self):
        request = factory.post("/validate/", {"text": "say badword here", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        content = response.content.decode()
        assert "say " in content
        assert " here" in content

    def test_multiple_error_spans(self):
        request = factory.post("/validate/", {"text": "badword and badword", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        marks = soup.find_all("mark")
        assert len(marks) == 2

    def test_html_escapes_text(self):
        request = factory.post("/validate/", {"text": "<script>alert(1)</script>", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        content = response.content.decode()
        assert "<script>" not in content
        assert "&lt;script&gt;" in content

    def test_html_escapes_marked_text(self):
        """Text inside <mark> tags is also escaped."""

        # Create a view that marks the entire text
        class MarkAllView(FormworkValidateView):
            def get_errors(self, text, **kwargs):
                return [{"message": "bad", "start": 0, "end": len(text)}]

        request = factory.post("/validate/", {"text": "<b>bold</b>", "errors_id": ""})
        response = MarkAllView.as_view()(request)
        content = response.content.decode()
        assert "<b>" not in content
        assert "<mark>" in content


class TestFormworkValidateViewErrors:
    def test_oob_errors_div(self):
        request = factory.post("/validate/", {"text": "say badword here", "errors_id": "id_errors"})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        oob = soup.find("div", {"id": "id_errors"})
        assert oob is not None
        assert oob["hx-swap-oob"] == "innerHTML"

    def test_error_messages_in_oob(self):
        request = factory.post("/validate/", {"text": "say badword here", "errors_id": "id_errors"})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        oob = soup.find("div", {"id": "id_errors"})
        msgs = oob.find_all("p")
        assert len(msgs) == 1
        assert "Prohibited word" in msgs[0].string

    def test_empty_oob_when_no_errors(self):
        request = factory.post("/validate/", {"text": "clean text", "errors_id": "id_errors"})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        oob = soup.find("div", {"id": "id_errors"})
        assert oob is not None
        assert oob["hx-swap-oob"] == "innerHTML"
        assert oob.find("p") is None

    def test_no_oob_when_no_errors_id(self):
        request = factory.post("/validate/", {"text": "say badword here", "errors_id": ""})
        response = SpellCheckView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find("div", {"hx-swap-oob": True}) is None

    def test_message_only_errors(self):
        """Errors without start/end still produce messages but no marks."""
        request = factory.post("/validate/", {"text": "this text is too long", "errors_id": "id_errors"})
        response = MessageOnlyView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find("mark") is None
        oob = soup.find("div", {"id": "id_errors"})
        assert "too long" in oob.get_text()

    def test_error_messages_escaped(self):
        class XSSView(FormworkValidateView):
            def get_errors(self, text, **kwargs):
                return [{"message": "<script>alert(1)</script>"}]

        request = factory.post("/validate/", {"text": "test", "errors_id": "id_errors"})
        response = XSSView.as_view()(request)
        content = response.content.decode()
        assert "<script>" not in content


class TestFormworkValidateViewDefaults:
    def test_base_class_returns_no_errors(self):
        request = factory.post("/validate/", {"text": "hello", "errors_id": ""})
        response = FormworkValidateView.as_view()(request)
        assert response.content.decode() == "hello"

    def test_request_passed_to_get_errors(self):
        received = {}

        class TrackingView(FormworkValidateView):
            def get_errors(self, text, **kwargs):
                received["request"] = kwargs.get("request")
                return []

        request = factory.post("/validate/", {"text": "test", "errors_id": ""})
        TrackingView.as_view()(request)
        assert received["request"] is request

    def test_csrf_exempt(self):
        """POST without CSRF token should not be rejected."""
        request = factory.post("/validate/", {"text": "hello", "errors_id": ""})
        response = FormworkValidateView.as_view()(request)
        assert response.status_code == 200


class TestFormworkValidateViewMergeSpans:
    def test_overlapping_spans_merged(self):
        class OverlapView(FormworkValidateView):
            def get_errors(self, text, **kwargs):
                return [
                    {"message": "err1", "start": 0, "end": 5},
                    {"message": "err2", "start": 3, "end": 8},
                ]

        request = factory.post("/validate/", {"text": "abcdefghij", "errors_id": ""})
        response = OverlapView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        marks = soup.find_all("mark")
        # Overlapping spans should be merged into one
        assert len(marks) == 1
        assert marks[0].string == "abcdefgh"

    def test_adjacent_spans_not_merged(self):
        class AdjacentView(FormworkValidateView):
            def get_errors(self, text, **kwargs):
                return [
                    {"message": "err1", "start": 0, "end": 3},
                    {"message": "err2", "start": 5, "end": 8},
                ]

        request = factory.post("/validate/", {"text": "abcdefghij", "errors_id": ""})
        response = AdjacentView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        marks = soup.find_all("mark")
        assert len(marks) == 2

    def test_zero_length_span_ignored(self):
        """start == end produces no mark."""
        highlighted = FormworkValidateView._build_highlighted(
            "abcdef",
            [{"start": 2, "end": 2}],
        )
        assert "<mark>" not in highlighted
        assert highlighted == "abcdef"

    def test_fully_contained_span_merged(self):
        """A span fully inside another is absorbed by the merge."""
        highlighted = FormworkValidateView._build_highlighted(
            "abcdefghij",
            [{"start": 0, "end": 8}, {"start": 2, "end": 5}],
        )
        soup = BeautifulSoup(highlighted, "html.parser")
        marks = soup.find_all("mark")
        assert len(marks) == 1
        assert marks[0].string == "abcdefgh"

    def test_out_of_order_spans_sorted(self):
        """Spans provided in reverse order are sorted before processing."""
        highlighted = FormworkValidateView._build_highlighted(
            "abcdefghij",
            [{"start": 6, "end": 9}, {"start": 1, "end": 4}],
        )
        soup = BeautifulSoup(highlighted, "html.parser")
        marks = soup.find_all("mark")
        assert len(marks) == 2
        assert marks[0].string == "bcd"
        assert marks[1].string == "ghi"

    def test_span_at_text_boundaries(self):
        """Span covering the full text."""
        highlighted = FormworkValidateView._build_highlighted(
            "hello",
            [{"start": 0, "end": 5}],
        )
        assert highlighted == "<mark>hello</mark>"

    def test_span_clamped_to_text_length(self):
        """end beyond text length is clamped."""
        highlighted = FormworkValidateView._build_highlighted(
            "abc",
            [{"start": 1, "end": 100}],
        )
        soup = BeautifulSoup(highlighted, "html.parser")
        mark = soup.find("mark")
        assert mark.string == "bc"

    def test_negative_start_clamped_to_zero(self):
        """Negative start is clamped to 0."""
        highlighted = FormworkValidateView._build_highlighted(
            "abcdef",
            [{"start": -5, "end": 3}],
        )
        soup = BeautifulSoup(highlighted, "html.parser")
        mark = soup.find("mark")
        assert mark.string == "abc"

    def test_reversed_start_end_ignored(self):
        """start > end is filtered out."""
        highlighted = FormworkValidateView._build_highlighted(
            "abcdef",
            [{"start": 5, "end": 2}],
        )
        assert "<mark>" not in highlighted


# ---------------------------------------------------------------------------
# Search view error handling
# ---------------------------------------------------------------------------


class TestFormworkSearchViewErrorHandling:
    def test_missing_q_param(self):
        """Missing 'q' query param defaults to empty string."""
        request = factory.get("/search/")
        response = CitySearchView.as_view()(request)
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        # Should return all results (empty query)
        buttons = soup.find_all("button")
        assert len(buttons) == 4

    def test_invalid_widget_type_falls_back(self):
        """Invalid 'type' query param falls back to default widget_type."""
        request = factory.get("/search/", {"q": "", "type": "not_a_type"})
        response = CitySearchView.as_view()(request)
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        # Falls back to search_select (has data-value)
        btn = soup.find("button")
        assert btn.has_attr("data-value")

    def test_empty_type_falls_back(self):
        """Empty 'type' query param falls back to default widget_type."""
        request = factory.get("/search/", {"q": "", "type": ""})
        response = CitySearchView.as_view()(request)
        assert response.status_code == 200

    def test_total_count_oob_with_field_name(self):
        """search_select with name param includes OOB total count element."""
        request = factory.get("/search/", {"q": "", "type": "search_select", "name": "city"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        total = soup.find("input", {"id": "id_city_total"})
        assert total is not None
        assert total["value"] == "4"

    def test_no_total_count_without_field_name(self):
        """search_select without name param omits OOB total count."""
        request = factory.get("/search/", {"q": "", "type": "search_select"})
        response = CitySearchView.as_view()(request)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find("input", {"hx-swap-oob": "true"}) is None
