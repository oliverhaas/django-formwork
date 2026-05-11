"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django_formwork.registry import SearchRegistration

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


# Cache the first call to ``_resolve_skeleton_options`` per registry key.
# The skeleton is shape-only and doesn't change between requests, so a
# process-lifetime cache avoids paying for ``search_func("")`` on every
# render (matters for any non-trivial choices-backed search).  Cleared via
# ``_clear_skeleton_cache()`` in tests.
_skeleton_cache: dict[str, list[dict[str, Any]]] = {}


def _clear_skeleton_cache() -> None:
    """Drop the skeleton cache (intended for test isolation)."""
    _skeleton_cache.clear()


def _resolve_skeleton_options(
    registry_key: str | None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Fetch up to ``max_results`` unfiltered options from the registry.

    Used to render a pixel-perfect loading skeleton that exactly matches
    the eventual response: same row layout, same icon column, same label
    widths.  Works for both backings:

    - **Model-backed**: pulls ``max_results`` instances from
      ``queryset_factory()``.
    - **Choices-backed**: calls ``search_func("")`` and slices the result.

    Returns an empty list when no registration is attached.  The result
    is cached per registry key (see ``_skeleton_cache``).
    """
    if registry_key is None:
        return []
    if registry_key in _skeleton_cache:
        return _skeleton_cache[registry_key]
    from django_formwork.registry import get_registration

    reg = get_registration(registry_key)
    if reg is None:
        return []
    try:
        if reg.queryset_factory is not None:
            results = _skeleton_from_queryset(reg, max_results)
        elif reg.search_func is not None:
            results = _skeleton_from_search_func(reg, max_results)
        else:
            results = []
    except Exception:  # noqa: BLE001 — skeleton is a hint, never block render
        results = []
    # Cache even an empty result so a slow / failing ``search_func`` isn't
    # called on every render.
    _skeleton_cache[registry_key] = results
    return results


def _skeleton_from_queryset(reg: SearchRegistration, max_results: int) -> list[dict[str, Any]]:
    return [
        {
            "value": str(getattr(obj, reg.to_field_name)),
            "label": str(reg.label_from_instance(obj)) if reg.label_from_instance else str(obj),
            "icon": reg.icon_from_instance(obj) if reg.icon_from_instance else "",
            "description": reg.description_from_instance(obj) if reg.description_from_instance else "",
        }
        for obj in reg.queryset_factory()[:max_results]  # type: ignore[misc]
    ]


def _skeleton_from_search_func(reg: SearchRegistration, max_results: int) -> list[dict[str, Any]]:
    # ``search_func`` may be slow (e.g. external API).  Caching at the
    # caller avoids paying that cost on every render — but the first
    # render of each form still pays it once.
    raw = reg.search_func("", None) or []
    results: list[dict[str, Any]] = []
    for item in raw[:max_results]:
        if isinstance(item, dict):
            results.append(
                {
                    "value": str(item.get("value", "")),
                    "label": str(item.get("label", "")),
                    "icon": item.get("icon", "") or "",
                    "description": item.get("description", "") or "",
                },
            )
        else:
            results.append(
                {
                    "value": str(item[0]),
                    "label": str(item[1]),
                    "icon": "",
                    "description": "",
                },
            )
    return results


def _resolve_search_expectations(registry_key: str | None) -> tuple[int | None, bool, bool]:
    """Resolve ``(expected_count, expected_icons, expected_descriptions)`` from the registry.

    The count comes from ``queryset_factory().count()``; the icon and
    description flags from whether ``icon_from_instance`` /
    ``description_from_instance`` were registered.  Returns
    ``(None, False, False)`` when no registration is attached, so the
    template falls back to a generic skeleton shape.
    """
    if registry_key is None:
        return None, False, False
    from django_formwork.registry import get_registration

    reg = get_registration(registry_key)
    if reg is None:
        return None, False, False
    expected_count: int | None = None
    if reg.queryset_factory is not None:
        try:
            expected_count = reg.queryset_factory().count()
        except Exception:  # noqa: BLE001 — count is a hint, never block render
            expected_count = None
    return expected_count, reg.icon_from_instance is not None, reg.description_from_instance is not None


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
