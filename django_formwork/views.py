"""Server-side views for formwork widgets.

:class:`FormworkSearchView` serves every registered field search.
:class:`FormworkValidateView` is the base class for textarea validation endpoints.
"""

from __future__ import annotations

from html import escape as html_escape
from typing import TYPE_CHECKING, Any, ClassVar, final

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBase
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_formwork.search import SEARCH_PAGE_SIZE, declared_params, get_field
from django_formwork.widgets import ComboBox, Select, SelectMultiple
from django_formwork.widgets.select import label_extras

if TYPE_CHECKING:
    from collections.abc import Callable

    from django import forms
    from django.db.models import QuerySet

__all__ = [
    "FormworkSearchView",
    "FormworkValidateView",
]


@final
class FormworkSearchView(View):
    """Resolve a field by URL key and return its search's ``<li>`` option rows.

    Mounted by ``include("django_formwork.urls")``. Widgets configure their
    search with ``search_queryset``, ``search_fields`` and ``search_decorator``;
    the view is not meant to be subclassed.

    An anonymous request for an unknown key redirects to ``settings.LOGIN_URL``
    when ``django.contrib.auth`` is installed, so it cannot tell a missing key
    from one it may not reach.
    """

    field: forms.Field | None = None
    #: Maximum query length (characters). Longer queries are truncated.
    MAX_QUERY_LENGTH: ClassVar[int] = 200

    # The rows take the markup of the widget that asks, so one search serves every widget.
    option_templates: ClassVar[dict[str, str]] = {
        cls.search_variant: f"{cls.template_name}#option_list" for cls in (Select, SelectMultiple, ComboBox)
    }

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.field = get_field(kwargs.get("key", ""))

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if self.field is None:
            user = getattr(request, "user", None)
            if apps.is_installed("django.contrib.auth") and not (user and user.is_authenticated):
                # Deferred: the auth views need django.contrib.auth installed.
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            raise Http404
        # The key is a routing detail; get() does not accept it.
        kwargs.pop("key", None)
        decorator = self.field.widget.search_decorator
        if decorator is not None:
            return decorator(super().dispatch)(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def search(self, queryset: QuerySet[Any], *, widget: forms.Widget, query: str) -> QuerySet[Any]:
        """Narrow ``queryset`` to the rows matching ``query``.

        Without ``search_fields`` the ``search_queryset`` reads ``q`` itself
        and returns its rows best-first.
        """
        search_fields = getattr(widget, "search_fields", ())
        if not query or not search_fields:
            return queryset
        condition = Q()
        for field_name in search_fields:
            condition |= Q(**{f"{field_name}__icontains": query})
        return queryset.filter(condition)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:  # noqa: ARG002
        field = self.field
        if field is None:  # pragma: no cover (dispatch() already guards)
            raise Http404
        widget: Any = field.widget
        template = self.option_templates.get(request.GET.get("widget", ""))
        if template is None:
            raise Http404
        try:
            params = {name: kind(request.GET[name]) for name, kind in declared_params(widget.search_queryset).items()}
            offset = int(request.GET.get("offset", 0))
        except KeyError, ValueError:
            raise Http404 from None
        if offset < 0:
            raise Http404
        query = request.GET.get("q", "").strip()[: self.MAX_QUERY_LENGTH]
        to_field_name = getattr(field, "to_field_name", None) or "pk"
        queryset = widget.search_queryset(request, **params)
        try:
            queryset = queryset.exclude(**{f"{to_field_name}__in": request.GET.getlist("exclude")})
        except ValueError, ValidationError:
            raise Http404 from None
        queryset = self.search(queryset, widget=widget, query=query)
        # One row past the cap: cheaper than a COUNT and enough to say "there are more".
        rows = list(queryset[offset : offset + SEARCH_PAGE_SIZE + 1])
        truncated = len(rows) > SEARCH_PAGE_SIZE
        del rows[SEARCH_PAGE_SIZE:]
        # ModelChoiceField provides label_from_instance; a free-text ComboBox over a
        # CharField supplies its own (or falls back to str()).
        label_from_instance = (
            getattr(field, "label_from_instance", None) or getattr(widget, "label_from_instance", None) or str
        )
        options = []
        for obj in rows:
            label = label_from_instance(obj)
            options.append({"value": str(getattr(obj, to_field_name)), "label": str(label), **label_extras(label)})
        # Only an optional field clears, with the label of its blank choice.
        clear_label = None if field.required else getattr(field, "empty_label", None)
        if offset == 0 and clear_label is not None and request.GET.get("allow_clear") == "1":
            options.insert(0, {"value": "", "label": str(clear_label)})
        more = request.GET.copy()
        more["offset"] = str(offset + SEARCH_PAGE_SIZE)
        html = render_to_string(
            template,
            {
                "options": options,
                "truncated": truncated,
                "shown": offset + len(rows),
                "more_url": f"{request.path}?{more.urlencode()}",
            },
            request=request,
        )
        return HttpResponse(html)


# SECURITY: CSRF-exempt because this view performs read-only validation
# (no side effects, no data mutation).  The POST body contains only the
# textarea text and an errors_id for OOB swap targeting.
@method_decorator(csrf_exempt, name="dispatch")
class FormworkValidateView(View):
    """Base view for server-side textarea validation with highlighting.

    Subclass and implement :meth:`get_errors` to return validation errors.
    The view renders highlighted HTML (with ``<mark>`` tags around errors)
    that htmx swaps into the widget's highlight overlay, plus error messages
    via out-of-band swap.

    The view is CSRF-exempt because it performs read-only validation.

    Usage::

        class SpellCheckView(FormworkValidateView):
            def get_errors(self, text: str, **kwargs) -> list[dict]:
                errors = []
                for match in find_misspellings(text):
                    errors.append({
                        "message": f"Misspelled: {match.word}",
                        "start": match.start,
                        "end": match.end,
                    })
                return errors

        # urls.py
        urlpatterns = [
            path("validate/spell/", SpellCheckView.as_view(), name="spell-check"),
        ]

        # forms.py
        content = forms.CharField(
            widget=ValidatedTextarea(validate_url=reverse_lazy("spell-check")),
        )

    Error dict keys:

    - ``message`` (required): error description shown below the textarea
    - ``start`` (optional): start character index in the text
    - ``end`` (optional): end character index in the text

    When ``start`` and ``end`` are provided, the corresponding text span is
    wrapped in a ``<mark>`` tag in the highlight overlay.
    """

    #: Optional decorator (e.g. ``login_required``) applied to ``dispatch``,
    #: the same access-control hook the search side exposes via
    #: ``search_decorator``.  ``None`` means public.
    validate_decorator: Callable | None = None

    #: Maximum text length (characters). Longer texts are truncated before
    #: validation, mirroring ``FormworkSearchView.MAX_QUERY_LENGTH``.
    MAX_TEXT_LENGTH = 50_000

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        # Class-level access: instance access would bind a plain function
        # (e.g. login_required) as a method and pass ``self`` into it.
        decorator = type(self).validate_decorator
        if decorator is not None:
            decorated = decorator(super().dispatch)
            return decorated(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_errors(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:  # noqa: ARG002
        """Return validation errors for the given text.

        Override this in your subclass.

        Args:
            text: The textarea content.
            **kwargs: Additional context (e.g. ``request``).

        Returns:
            List of error dicts.
        """
        return []

    def post(self, request: HttpRequest) -> HttpResponse:
        text = request.POST.get("text", "")[: self.MAX_TEXT_LENGTH]
        errors_id = request.POST.get("errors_id", "")

        errors = self.get_errors(text, request=request)
        highlighted = self._build_highlighted(text, errors)

        parts = [highlighted]
        if errors_id:
            parts.append(self._build_errors(errors, errors_id))

        return HttpResponse("\n".join(parts))

    @staticmethod
    def _build_highlighted(text: str, errors: list[dict[str, Any]]) -> str:
        """Build HTML with ``<mark>`` tags around error spans."""
        text_len = len(text)
        clamped = (
            (max(0, e["start"]), min(text_len, e["end"]))
            for e in errors
            if "start" in e and "end" in e and e["start"] < e["end"]
        )
        # Drop spans clamped to nothing (entirely outside the text) so no
        # empty <mark> is emitted.
        spans = sorted((s for s in clamped if s[0] < s[1]), key=lambda x: x[0])
        if not spans:
            return html_escape(text)

        # Merge overlapping spans.
        merged = [list(spans[0])]
        for start, end in spans[1:]:
            if start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        result: list[str] = []
        pos = 0
        for start, end in merged:
            if start > pos:
                result.append(html_escape(text[pos:start]))
            result.append(f"<mark>{html_escape(text[start:end])}</mark>")
            pos = end
        if pos < len(text):
            result.append(html_escape(text[pos:]))
        return "".join(result)

    @staticmethod
    def _build_errors(errors: list[dict[str, Any]], errors_id: str) -> str:
        """Build out-of-band swap HTML for error messages."""
        messages = [e["message"] for e in errors if "message" in e]
        escaped_id = html_escape(errors_id)
        if not messages:
            return f'<div id="{escaped_id}" hx-swap-oob="innerHTML"></div>'
        msg_html = "".join(f"<p>{html_escape(m)}</p>" for m in messages)
        return f'<div id="{escaped_id}" hx-swap-oob="innerHTML">{msg_html}</div>'
