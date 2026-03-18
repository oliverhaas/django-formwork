"""Server-side views for formwork widgets.

:class:`FormworkSearchView` is the base class for dropdown search endpoints.
:class:`FormworkValidateView` is the base class for textarea validation endpoints.
"""

from __future__ import annotations

from html import escape as html_escape
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, HttpResponse
from django.template import Context
from django.template.engine import Engine
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

if TYPE_CHECKING:
    from django.template.base import Template


class FormworkSearchView(View):
    """Base view for server-side widget search.

    Subclass and implement :meth:`get_results` to return search results.
    The view renders the results as HTML ``<li>`` elements that htmx swaps
    into the widget's option list.

    Usage::

        class CitySearchView(FormworkSearchView):
            def get_results(self, query: str) -> list[dict]:
                return [
                    {"value": "nyc", "label": "New York"},
                    {"value": "ldn", "label": "London"},
                ]

        # urls.py
        urlpatterns = [
            path("search/cities/", CitySearchView.as_view(), name="city-search"),
        ]

        # forms.py
        city = forms.ChoiceField(
            widget=SearchSelect(search_url=reverse_lazy("city-search")),
        )

    Results dict keys:

    - ``label`` (required): display text
    - ``value`` (optional): key value for SearchSelect, not used for ComboBox
    - ``icon`` (optional): icon markup wrapped in ``mark_safe()``
      (plain strings are auto-escaped)
    """

    #: Template for SearchSelect results (value + label, for select-style)
    SEARCH_SELECT_TEMPLATE = """{% for item in results %}
<li role="option"><button type="button" class="flex w-full items-center gap-2 px-3 py-1.5 rounded-btn cursor-pointer hover:bg-base-200 text-left" data-value="{{ item.value }}" data-label="{{ item.label }}"{% if item.icon %} data-icon="{{ item.icon }}"{% endif %}>
  <span class="formwork-check shrink-0 opacity-0" :class="value === '{{ item.value }}' && 'opacity-100'" aria-hidden="true">&#x2713;</span>{% if item.icon %}<span class="shrink-0">{{ item.icon }}</span>{% endif %}<span class="flex flex-col"><span class="select-none">{{ item.label }}</span>{% if item.description %}<span class="text-xs text-base-content/50">{{ item.description }}</span>{% endif %}</span>
</button></li>{% endfor %}
{% if not results %}<li class="px-3 py-2 text-base-content/50">No results</li>{% endif %}"""

    #: Template for ComboBox results (label only, for autocomplete-style)
    COMBOBOX_TEMPLATE = """{% for item in results %}
<li role="option"><button type="button" class="flex w-full items-center gap-2 px-3 py-1.5 rounded-btn cursor-pointer hover:bg-base-200 text-left" data-suggestion="{{ item.label }}"{% if item.icon %} data-icon="{{ item.icon }}"{% endif %}>
  {% if item.icon %}<span class="shrink-0">{{ item.icon }}</span>{% endif %}<span class="flex flex-col"><span class="select-none">{{ item.label }}</span>{% if item.description %}<span class="text-xs text-base-content/50">{{ item.description }}</span>{% endif %}</span>
</button></li>{% endfor %}
{% if not results %}<li class="px-3 py-2 text-base-content/50">No results</li>{% endif %}"""

    #: Template for MultiSelect results (checkbox options).
    #: Checkboxes have no ``name`` — hidden inputs in the widget template
    #: handle form submission.  Alpine directives sync checked state with
    #: the parent ``x-data`` scope (the widget wrapper).
    MULTISELECT_TEMPLATE = """{% for item in results %}
<li><label class="flex items-center gap-2 px-3 py-1.5 rounded-btn cursor-pointer hover:bg-base-200">
  <input type="checkbox" value="{{ item.value }}" class="multiselect hidden" x-init="$el.checked = selected.has('{{ item.value|escapejs }}')" @change="toggle('{{ item.value|escapejs }}', '{{ item.label|escapejs }}', '{{ item.icon|escapejs }}')">
  <span class="formwork-check shrink-0 opacity-0" aria-hidden="true">&#x2713;</span>
  {% if item.icon %}<span class="shrink-0">{{ item.icon }}</span>{% endif %}<span class="select-none">{{ item.label }}</span>
</label></li>{% endfor %}
{% if not results %}<li class="px-3 py-2 text-base-content/50">No results</li>{% endif %}"""

    #: Which template to use.  Set by the widget type or override in subclass.
    widget_type: str = "search_select"

    #: Cached template engine and compiled templates (class-level, shared).
    _engine: Engine | None = None
    _compiled_templates: dict[str, Template] | None = None

    @classmethod
    def _get_template(cls, widget_type: str) -> Template:
        """Return a compiled template for the given widget type, using cache."""
        if cls._engine is None:
            cls._engine = Engine()
        if cls._compiled_templates is None:
            cls._compiled_templates = {
                "search_select": cls._engine.from_string(cls.SEARCH_SELECT_TEMPLATE),
                "combobox": cls._engine.from_string(cls.COMBOBOX_TEMPLATE),
                "multiselect": cls._engine.from_string(cls.MULTISELECT_TEMPLATE),
            }
        return cls._compiled_templates[widget_type]

    def get_results(self, query: str, **kwargs: Any) -> list[dict[str, str]]:  # noqa: ARG002
        """Return search results for the given query.

        Override this in your subclass.  Each result should be a dict with
        at least a ``label`` key, and optionally ``value`` and ``icon``.

        ``icon`` values should be wrapped in ``mark_safe()`` — plain strings
        are auto-escaped by the template engine.

        Args:
            query: The search string from the user's input.
            **kwargs: Additional context (e.g. request).

        Returns:
            List of result dicts.
        """
        return []

    #: Valid widget types for the ``type`` query parameter.
    VALID_WIDGET_TYPES = frozenset({"search_select", "combobox", "multiselect"})

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "").strip()
        widget_type = request.GET.get("type", self.widget_type)
        field_name = request.GET.get("name", "")

        if widget_type not in self.VALID_WIDGET_TYPES:
            widget_type = self.widget_type

        results = self.get_results(query, request=request)

        template = self._get_template(widget_type)
        html = template.render(Context({"results": results, "field_name": field_name}))
        return HttpResponse(html.strip())


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
        text = request.POST.get("text", "")
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
        spans = sorted(
            [
                (max(0, e["start"]), min(text_len, e["end"]))
                for e in errors
                if "start" in e and "end" in e and e["start"] < e["end"]
            ],
            key=lambda x: x[0],
        )
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
