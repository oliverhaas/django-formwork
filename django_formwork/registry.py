"""Auto-registration registry for server-side search endpoints.

Widgets with ``search_fields`` are automatically registered here when their
form is instantiated.  A single dispatch view (``FormworkAutoSearchView``)
serves all registered endpoints via a stable key derived from the model
and search configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.db.models import QuerySet

_registry: dict[str, SearchRegistration] = {}


@dataclass(frozen=True)
class SearchRegistration:
    """Everything needed to serve a search endpoint."""

    queryset_factory: Callable[[], QuerySet]
    search_fields: tuple[str, ...]
    to_field_name: str = "pk"
    label_from_instance: Callable[..., str] | None = None
    icon_from_instance: Callable[..., str] | None = None
    description_from_instance: Callable[..., str] | None = None
    permission: Callable[..., bool] | None = None
    max_results: int = 50
    widget_type: str = "search_select"
    extra: dict[str, Any] = field(default_factory=dict)


def make_key(
    model_label: str,
    search_fields: Sequence[str],
    to_field_name: str = "pk",
) -> str:
    """Build a stable, URL-safe registry key."""
    fields_part = ",".join(sorted(search_fields))
    key = f"{model_label}.{fields_part}"
    if to_field_name != "pk":
        key += f".{to_field_name}"
    return key


def register(key: str, registration: SearchRegistration) -> None:
    """Register a search endpoint (idempotent)."""
    _registry[key] = registration


def get_registration(key: str) -> SearchRegistration | None:
    """Look up a registration by key."""
    return _registry.get(key)


def get_registry() -> dict[str, SearchRegistration]:
    """Return the full registry (for debugging / introspection)."""
    return _registry
