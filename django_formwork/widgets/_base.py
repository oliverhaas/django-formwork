"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django.utils.formats import number_format
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Callable

_KB = 1024
_MB = 1024 * 1024

# A count in each CLDR plural category, in every language that uses the category.
_PLURAL_SAMPLES = {"zero": 0, "one": 1, "two": 2, "few": 3, "many": 11, "other": 100}

_ACCEPT_WILDCARDS = {"audio": _("Audio files"), "image": _("Images"), "video": _("Videos")}


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


class _DropZoneMixin:
    """Shared get_context logic for FileDropzoneInput and ImageDropzoneInput."""

    max_size: int | None

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)  # type: ignore[misc]
        accept = context["widget"]["attrs"].get("accept", "")
        if accept:
            context["widget"]["accept_display"] = _format_accept(accept)
        if self.max_size is not None:
            context["widget"]["max_size"] = self.max_size
            context["widget"]["max_size_display"] = _format_size(self.max_size)
        return context
