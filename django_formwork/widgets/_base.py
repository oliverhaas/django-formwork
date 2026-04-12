"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

from typing import Any

# Sentinel: distinguishes "developer didn't pass search_decorator" from
# "developer explicitly passed None" (= no decorator, public endpoint).
_NOT_SET = object()

_KB = 1024
_MB = 1024 * 1024


def _format_size(size: int) -> str:
    """Format a byte count for human-readable display."""
    if size < _KB:
        return f"{size} B"
    if size < _MB:
        kb = size / _KB
        return f"{kb:.0f} KB" if kb == int(kb) else f"{kb:.1f} KB"
    mb = size / _MB
    return f"{mb:.0f} MB" if mb == int(mb) else f"{mb:.1f} MB"


def _format_accept(accept: str) -> str:
    """Format an HTML ``accept`` attribute value for human-readable display."""
    parts = [p.strip() for p in accept.split(",") if p.strip()]
    labels: list[str] = []
    for part in parts:
        if part.endswith("/*"):
            labels.append(part.split("/")[0].capitalize() + "s")
        elif part.startswith("."):
            labels.append(part[1:].upper())
        elif "/" in part:
            labels.append(part.split("/")[1].upper())
        else:
            labels.append(part.upper())
    return ", ".join(labels)


class _DropZoneMixin:
    """Shared get_context logic for FileDropZone and ImageDropZone."""

    max_size: int | None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)  # type: ignore[misc]
        accept = context["widget"]["attrs"].get("accept", "")
        if accept:
            context["widget"]["accept_display"] = _format_accept(accept)
        if self.max_size is not None:
            context["widget"]["max_size"] = self.max_size
            context["widget"]["max_size_display"] = _format_size(self.max_size)
        return context
