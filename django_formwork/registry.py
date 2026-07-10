"""Auto-registration registry for server-side search endpoints.

Widgets with ``search_fields`` are automatically registered here when their
form is instantiated.  Forms with ``search_choices_<fieldname>`` methods are
also registered for plain (non-model) choice fields.

A single dispatch view (``FormworkAutoSearchView``) serves all registered
endpoints via a stable key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.db.models import QuerySet

__all__ = [
    "SearchRegistration",
    "get_registration",
    "get_registry",
    "make_choices_key",
    "make_key",
    "register",
]

_registry: dict[str, SearchRegistration] = {}


@dataclass(frozen=True)
class SearchRegistration:
    """Everything needed to serve a search endpoint.

    Two modes:

    - **Model-backed**: ``queryset_factory`` + ``search_fields`` for automatic
      ``__icontains`` filtering.
    - **Choices-backed**: ``search_func(query, request)`` returns results directly.
    """

    queryset_factory: Callable[[], QuerySet] | None = None
    search_fields: tuple[str, ...] = ()
    to_field_name: str = "pk"
    label_from_instance: Callable[..., str] | None = None
    icon_from_instance: Callable[..., str] | None = None
    description_from_instance: Callable[..., str] | None = None
    search_decorator: Callable | None = None
    max_results: int = 50
    widget_type: str = "search_select"
    search_func: Callable[..., list] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def make_key(
    form_cls: type,
    field_name: str,
    model_label: str,
    search_fields: Sequence[str],
    to_field_name: str = "pk",
) -> str:
    """Build a stable, URL-safe registry key for model-backed search."""
    # SECURITY: the form class and field name are part of the key (mirroring
    # make_choices_key) so two forms searching the same model+fields never
    # share a registration.  Otherwise a public registration could overwrite
    # a decorated one (dropping its search_decorator), or an unfiltered
    # queryset could replace a scoped one.
    fields_part = ",".join(sorted(search_fields))
    key = f"{form_cls.__module__}.{form_cls.__qualname__}.{field_name}.{model_label}.{fields_part}"
    if to_field_name != "pk":
        key += f".{to_field_name}"
    return key.lower()


def make_choices_key(form_cls: type, field_name: str) -> str:
    """Build a stable, URL-safe registry key for choices-backed search."""
    module = form_cls.__module__
    qualname = form_cls.__qualname__
    return f"{module}.{qualname}.{field_name}".lower()


def register(key: str, registration: SearchRegistration) -> None:
    """Register a search endpoint (idempotent)."""
    _registry[key] = registration


def get_registration(key: str) -> SearchRegistration | None:
    """Look up a registration by key."""
    return _registry.get(key)


def get_registry() -> dict[str, SearchRegistration]:
    """Return the full registry (for debugging / introspection)."""
    return _registry
