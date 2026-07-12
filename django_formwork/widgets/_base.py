"""Internal utilities and base classes for formwork widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django_formwork._registry import SearchRegistration

# Sentinel: distinguishes "developer didn't pass search_decorator" from
# "developer explicitly passed None" (= no decorator, public endpoint).
# Typed ``Any`` so it can default a ``Callable | None`` parameter; it never
# leaks past _AutoSearchMixin, which validates it on form instantiation.
_NOT_SET: Any = object()

_KB = 1024
_MB = 1024 * 1024


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


def _resolve_initial_results(registry_key: str | None) -> tuple[int | None, list[dict[str, Any]]]:
    """Resolve ``(total_count, initial_options)`` from the registry for first-page render.

    Called on every render, with no caching.  The initial options are
    pre-rendered into the listbox so the dropdown opens with real data;
    htmx replaces them on first focus.  Total count drives the
    ``show_search`` decision (compared against ``search_threshold``).

    - **Model-backed**: ``queryset_factory().count()`` for the total,
      ``queryset_factory()[:reg.max_results]`` for the items.
    - **Choices-backed**: ``search_func("")`` once for both the total
      (``len``) and the items (sliced to ``reg.max_results``).

    Returns ``(None, [])`` when no registration is attached.
    """
    if registry_key is None:
        return None, []
    from django_formwork._registry import get_registration

    reg = get_registration(registry_key)
    if reg is None:
        return None, []
    try:
        if reg.queryset_factory is not None:
            return _initial_from_queryset(reg)
        if reg.search_func is not None:
            return _initial_from_search_func(reg)
    except Exception:  # noqa: BLE001 (initial render must never crash)
        return None, []
    return None, []


def _initial_from_queryset(reg: SearchRegistration) -> tuple[int, list[dict[str, Any]]]:
    assert reg.queryset_factory is not None  # caller checked  # noqa: S101
    qs = reg.queryset_factory()
    # NOTE: full ``COUNT(*)`` is wasteful when we only care whether it
    # crosses the search threshold.  Worth a PostgreSQL approximate-count
    # path later (pg_class.reltuples), left exact for now.
    total = qs.count()
    items = [
        {
            "value": str(getattr(obj, reg.to_field_name)),
            "label": str(reg.label_from_instance(obj)) if reg.label_from_instance else str(obj),
            "icon": reg.icon_from_instance(obj) if reg.icon_from_instance else "",
            "description": reg.description_from_instance(obj) if reg.description_from_instance else "",
        }
        for obj in qs[: reg.max_results]
    ]
    return total, items


def _initial_from_search_func(reg: SearchRegistration) -> tuple[int, list[dict[str, Any]]]:
    assert reg.search_func is not None  # caller checked  # noqa: S101
    raw = reg.search_func("", None) or []
    total = len(raw)
    items: list[dict[str, Any]] = []
    for item in raw[: reg.max_results]:
        if isinstance(item, dict):
            items.append(
                {
                    "value": str(item.get("value", "")),
                    "label": str(item.get("label", "")),
                    "icon": item.get("icon", "") or "",
                    "description": item.get("description", "") or "",
                },
            )
        else:
            items.append(
                {"value": str(item[0]), "label": str(item[1]), "icon": "", "description": ""},
            )
    return total, items


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
