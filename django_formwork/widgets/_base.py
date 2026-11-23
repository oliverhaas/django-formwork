"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django.utils.formats import number_format
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import get_language, ngettext
from django.utils.translation import gettext_lazy as _
from markupsafe import escape

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.forms.renderers import BaseRenderer

_KB = 1024
_MB = 1024 * 1024

# A count in each CLDR plural category, in every language that uses the category.
_PLURAL_SAMPLES = {"zero": 0, "one": 1, "two": 2, "few": 3, "many": 11, "other": 100}

_ACCEPT_WILDCARDS = {"audio": _("Audio files"), "image": _("Images"), "video": _("Videos")}

# The Lucide icon for each common kind of file, with the extensions it covers.
_FILE_ICONS = {
    "file-text": "pdf",
    "file-type": "doc docx odt rtf txt md pages",
    "file-spreadsheet": "xls xlsx xlsm ods csv tsv numbers",
    "file-chart-pie": "ppt pptx odp key",
    "file-image": "jpg jpeg png gif webp svg avif heic heif bmp tif tiff",
    "file-archive": "zip rar 7z tar gz tgz bz2 xz",
    "file-music": "mp3 wav ogg oga m4a flac aac",
    "file-video-camera": "mp4 m4v mov avi mkv webm",
    "file-code": "json xml html htm css js ts py yaml yml sql",
}
# The component picks the icon of a file the user picks from the same lists.
_FILE_ICONS_JSON = json.dumps(_FILE_ICONS)


def widget_of[W](field: Any, kind: type[W]) -> W | None:  # noqa: ANN401 (a form field, or None)
    """The widget of ``kind`` that ``field`` renders, also inside a widget that wraps it as ``widget``."""
    widget = getattr(field, "widget", None)
    while widget is not None and not isinstance(widget, kind):
        widget = getattr(widget, "widget", None)
    return widget


class _FormworkTemplatesMixin:
    """Render through a ``FormworkRenderer``, the one renderer that loads formwork's Jinja2 widget templates."""

    def _render(self, template_name: str, context: dict[str, Any], renderer: BaseRenderer | None = None) -> SafeString:
        from django_formwork.renderers import formwork_renderer

        return mark_safe(formwork_renderer(renderer).render(template_name, context))  # noqa: S308


# Stand in for a row's name and stub URL in the HTML that the rows of a column share. Mixed case, so that a
# template that changes the case leaves a NUL behind.
_NAME = "\x00Name\x00"
_URL = "\x00Url\x00"
# What a template leaves of a stand-in that it changed: its NUL as is, as JSON, in a URL.
_LEFTOVERS = ("\x00", "\\u0000", "%00")
_MISSING = object()


class CellCache:
    """The widget HTML of a table column by value, which the rows that hold the same value render once.

    The HTML holds stand-ins for what tells the rows apart, their name and their stub URL. The first row of
    each kind, stub or full widget, also renders as usual; HTML that differs turns the cache off."""

    def __init__(self) -> None:
        self.cells: dict[tuple[Any, ...], str | None] = {}
        self.checked: set[bool] = set()
        self.on = True

    def render(
        self,
        widget: _StubMixin,
        name: str,
        value: Any,  # noqa: ANN401 (widget data)
        attrs: dict[str, Any] | None,
        renderer: BaseRenderer | None,
    ) -> SafeString:
        url = widget.stub_url
        found = self._key(widget, name, value, attrs, renderer) if self.on else None
        if found is None:
            return widget.render_cell(name, value, attrs, renderer, url)
        key, stand_in_attrs = found
        html = self.cells.get(key, _MISSING)
        if html is _MISSING:
            html = self.cells[key] = self._stand_in(widget, value, stand_in_attrs, renderer, url)
        if html is None:
            return widget.render_cell(name, value, attrs, renderer, url)
        html = html.replace(_NAME, name)
        if url is not None:
            html = html.replace(_URL, escape(url))
        if key[0] not in self.checked:
            self.checked.add(key[0])
            rendered = widget.render_cell(name, value, attrs, renderer, url)
            self.on = rendered == html
            return rendered
        return mark_safe(html)  # noqa: S308

    @staticmethod
    def _key(
        widget: _StubMixin,
        name: str,
        value: Any,  # noqa: ANN401 (widget data)
        attrs: dict[str, Any] | None,
        renderer: BaseRenderer | None,
    ) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        """The key of the row's HTML, and the attributes with the name's stand-in; None for a row the cache skips."""
        # The template escapes the stand-in, and the name takes its place as is.
        if "\x00" in name or escape(name) != name:
            return None
        stand_in_attrs = {}
        for attr, attr_value in (attrs or {}).items():
            if type(attr_value) is str:
                if "\x00" in attr_value:
                    return None
                stand_in_attrs[attr] = attr_value.replace(name, _NAME)
            elif attr_value is None or type(attr_value) in {bool, int}:
                stand_in_attrs[attr] = attr_value
            else:
                return None
        # A select renders the formatted value, a list of strings.
        shown = [(attr, type(attr_value), attr_value) for attr, attr_value in stand_in_attrs.items()]
        key = (widget.stub_url is None, tuple(widget.format_value(value)), tuple(shown), renderer, get_language())  # type: ignore[attr-defined]
        try:
            hash(key)
        except TypeError:
            return None
        return key, stand_in_attrs

    @staticmethod
    def _stand_in(
        widget: _StubMixin,
        value: Any,  # noqa: ANN401 (widget data)
        attrs: dict[str, Any],
        renderer: BaseRenderer | None,
        url: str | None,
    ) -> str | None:
        """The HTML with the stand-ins; None when the template changed a stand-in, which it then cannot hold."""
        html = str(widget.render_cell(_NAME, value, attrs, renderer, None if url is None else _URL))
        rest = html.replace(_NAME, "").replace(_URL, "")
        if any(leftover in rest for leftover in _LEFTOVERS):
            return None
        return html


class _StubMixin(_FormworkTemplatesMixin):
    """A widget that renders as a stub while ``stub_url`` is set: the closed widget and its value, and no more.

    The stub loads the full widget from ``stub_url`` on first hover, focus or press, and puts it in its place.
    """

    stub_template_name: str
    #: Set for each row of an editable list, see ``django_formwork.widgets._stub``.
    stub_url: str | None = None
    #: Set for the rows of a table column that share their choices, see ``cache_cells()``.
    cell_cache: CellCache | None = None

    def render(
        self,
        name: str,
        value: Any,  # noqa: ANN401 (widget data)
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        if self.cell_cache is not None:
            return self.cell_cache.render(self, name, value, attrs, renderer)
        return self.render_cell(name, value, attrs, renderer, self.stub_url)

    def render_cell(
        self,
        name: str,
        value: Any,  # noqa: ANN401 (widget data)
        attrs: dict[str, Any] | None,
        renderer: BaseRenderer | None,
        stub_url: str | None,
    ) -> SafeString:
        """The widget, or its stub that loads from ``stub_url``."""
        if stub_url is None:
            return super().render(name, value, attrs, renderer)  # type: ignore[misc]
        context = self.get_stub_context(name, value, attrs)
        context["widget"]["stub_url"] = stub_url
        return self._render(self.stub_template_name, context, renderer)

    def get_stub_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:  # noqa: ANN401
        """The context of the stub, which leaves out what only the open widget shows."""
        raise NotImplementedError


class _ModuleScript(str):
    """Static path that ``forms.Media`` renders as ``<script type="module">``.

    Django's ``Media.render_js`` calls ``path.__html__()`` when the path
    object provides it; otherwise it emits a plain ``<script src=...>``.
    Subclassing ``str`` keeps the instance interoperable with the rest of
    Django's media plumbing (deduplication, ordering, ``__add__``) while
    overriding only the rendered HTML.
    """

    __slots__ = ()

    def __html__(self) -> str:
        from django.templatetags.static import static
        from django.utils.html import format_html

        return format_html('<script type="module" src="{}"></script>', static(self))


def _plural_forms(text_for: Callable[[int], str]) -> str:
    """The ``ngettext`` forms of ``text_for`` as JSON keyed by CLDR plural category.

    The browser picks one with ``Intl.PluralRules``. Forms equal to ``other`` are left out.
    """
    other = text_for(_PLURAL_SAMPLES["other"])
    forms = {category: text for category, count in _PLURAL_SAMPLES.items() if (text := text_for(count)) != other}
    return json.dumps({**forms, "other": other}, ensure_ascii=False)


def _files_selected_text(count: int) -> str:
    return ngettext("%(count)s file selected", "%(count)s files selected", count)


def _format_size(size: int) -> str:
    """Format a byte count for human-readable display, in the active locale."""
    if size < _KB:
        return f"{size} B"
    value, unit = (size / _KB, "KB") if size < _MB else (size / _MB, "MB")
    return f"{number_format(value, decimal_pos=0 if value == int(value) else 1)} {unit}"


def _format_accept(accept: str) -> str:
    """Format an HTML ``accept`` attribute value for human-readable display."""
    parts = [p.strip() for p in accept.split(",") if p.strip()]
    labels: list[str] = []
    for part in parts:
        if part.endswith("/*"):
            kind = part.split("/")[0].lower()
            labels.append(str(_ACCEPT_WILDCARDS[kind]) if kind in _ACCEPT_WILDCARDS else part)
        elif part.startswith("."):
            labels.append(part[1:].upper())
        elif "/" in part:
            labels.append(part.split("/")[1].upper())
        else:
            labels.append(part.upper())
    return ", ".join(labels)


class _UploadHintsMixin(_FormworkTemplatesMixin):
    """Adds the readable ``accept`` list and the ``max_size`` limit of an upload widget to its context."""

    max_size: int | None

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)  # type: ignore[misc]
        accept = context["widget"]["attrs"].get("accept", "")
        if accept:
            context["widget"]["accept_display"] = _format_accept(accept)
        if self.max_size is not None:
            context["widget"]["max_size"] = self.max_size
            context["widget"]["max_size_display"] = _format_size(self.max_size)
            # Built here, not in the template: makemessages finds no Jinja trans block.
            context["widget"]["max_size_text"] = _("Max %(size)s") % {"size": context["widget"]["max_size_display"]}
        return context
