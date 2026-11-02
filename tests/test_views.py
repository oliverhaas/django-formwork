"""Tests for FormworkValidateView."""

from bs4 import BeautifulSoup
from django.test import Client, RequestFactory

from django_formwork.views import FormworkValidateView

factory = RequestFactory()


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

    def test_span_entirely_outside_text_ignored(self):
        """A span clamped to nothing produces no stray empty mark."""
        highlighted = FormworkValidateView._build_highlighted(
            "abc",
            [{"start": 5, "end": 10}],
        )
        assert "<mark>" not in highlighted
        assert highlighted == "abc"

    def test_span_entirely_before_text_ignored(self):
        """A fully negative span clamps to (0, 0) and is dropped."""
        highlighted = FormworkValidateView._build_highlighted(
            "abc",
            [{"start": -5, "end": 0}],
        )
        assert "<mark>" not in highlighted
        assert highlighted == "abc"


# ---------------------------------------------------------------------------
# Search view error handling
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# FormworkValidateView hardening (SECURITY)
# ---------------------------------------------------------------------------


class TestFormworkValidateViewHardening:
    def test_text_truncated_to_max_length(self):
        """Texts longer than MAX_TEXT_LENGTH are truncated before get_errors()."""
        received = {}

        class TrackingView(FormworkValidateView):
            MAX_TEXT_LENGTH = 10

            def get_errors(self, text, **kwargs):
                received["text"] = text
                return []

        request = factory.post("/validate/", {"text": "a" * 50, "errors_id": ""})
        TrackingView.as_view()(request)
        assert len(received["text"]) == 10

    def test_validate_decorator_applied(self):
        """A validate_decorator wraps dispatch, mirroring search_decorator."""
        from functools import wraps

        from django.http import HttpResponse

        def deny_all(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                return HttpResponse(status=403)

            return wrapper

        class ProtectedView(FormworkValidateView):
            validate_decorator = deny_all

        request = factory.post("/validate/", {"text": "hello", "errors_id": ""})
        response = ProtectedView.as_view()(request)
        assert response.status_code == 403

    def test_validate_decorator_none_allows_anonymous(self):
        """validate_decorator=None (the default) means public, no auth check."""
        request = factory.post("/validate/", {"text": "hello", "errors_id": ""})
        response = FormworkValidateView.as_view()(request)
        assert response.status_code == 200


def test_validate_view_csrf_exempt(settings):
    """A tokenless POST through the middleware stack succeeds because dispatch is csrf_exempt."""
    # Client(enforce_csrf_checks=True) only enforces when CsrfViewMiddleware
    # runs; the test settings do not install it, so add it here.
    settings.ROOT_URLCONF = "e2e.urls"
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "django.middleware.csrf.CsrfViewMiddleware"]
    client = Client(enforce_csrf_checks=True)
    response = client.post("/e2e/validate/bio/", {"text": "hello", "errors_id": ""})
    assert response.status_code == 200
    assert response.content.decode() == "hello"
