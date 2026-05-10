"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

from typing import Any

# Sentinel: distinguishes "developer didn't pass search_decorator" from
# "developer explicitly passed None" (= no decorator, public endpoint).
_NOT_SET = object()

_KB = 1024
_MB = 1024 * 1024


def _skeleton_row_count(expected_count: int | None) -> int:
    """Pick a row count that approximates how full the dropdown will look.

    Capped between 1 and 5 so the dropdown always reads as "loading a list"
    rather than "loading nothing" or "loading a wall."  Falls back to 4 when
    no hint is provided.
    """
    if expected_count is None:
        return 4
    return max(1, min(expected_count, 5))


def _skeleton_rows(expected_count: int | None) -> list[int]:
    """Return a list usable in template ``{% for _ in widget.skeleton_rows %}``."""
    return list(range(_skeleton_row_count(expected_count)))


def _resolve_search_expectations(
    registry_key: str | None,
    expected_count: int | None,
    expected_icons: bool,  # noqa: FBT001 — internal helper, kwargs would only obscure the call site
    expected_descriptions: bool,  # noqa: FBT001
) -> tuple[int | None, bool, bool]:
    """Resolve ``(expected_count, expected_icons, expected_descriptions)``.

    Looks up auto-registered metadata when the widget didn't supply hints.
    The count comes from the queryset factory, the icon/description flags
    from whether ``icon_from_instance`` / ``description_from_instance`` were
    registered.
    """
    if registry_key is None:
        return expected_count, expected_icons, expected_descriptions
    from django_formwork.registry import get_registration

    reg = get_registration(registry_key)
    if reg is None:
        return expected_count, expected_icons, expected_descriptions
    if expected_count is None and reg.queryset_factory is not None:
        try:
            expected_count = reg.queryset_factory().count()
        except Exception:  # noqa: BLE001 — count is a hint, never block render
            expected_count = None
    if not expected_icons and reg.icon_from_instance is not None:
        expected_icons = True
    if not expected_descriptions and reg.description_from_instance is not None:
        expected_descriptions = True
    return expected_count, expected_icons, expected_descriptions


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
