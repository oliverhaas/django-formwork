"""Auto-registration registry for server-side search endpoints.

Search-capable widgets (``SearchSelect``, ``MultiSelect``, ``ComboBox``) are
registered here at *class-definition time*: the form metaclass walks the
declared fields and registers one endpoint per searchable widget.  Registering
in the metaclass (rather than on form instantiation) means every endpoint is
present in every process as soon as the form module is imported, so the single
dispatch view (:class:`~django_formwork.views.FormworkAutoSearchView`) can serve
it regardless of which worker rendered the form.

Each endpoint is keyed by an opaque, stable digest of ``form_label`` +
``field_name`` — unique per form field (no cross-form collisions) and free of
internal module paths in the URL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import QuerySet
    from django.http import HttpRequest

__all__ = [
    "SearchRegistration",
    "form_label",
    "get_registration",
    "get_registry",
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

    ``queryset_factory`` is request-scoped. It receives the current
    ``HttpRequest`` (or ``None`` during the initial widget render, before a
    request is available) so per-request querysets (e.g. filtered by
    ``request.user``) resolve against the *searching* user, not whoever last
    rendered the form.
    """

    queryset_factory: Callable[[HttpRequest | None], QuerySet] | None = None
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


def form_label(form_cls: type) -> str:
    """Return the fully-qualified label identifying a form class."""
    return f"{form_cls.__module__}.{form_cls.__qualname__}"


def make_key(form_cls: type, field_name: str) -> str:
    """Build a stable, opaque registry key for one form field's search endpoint.

    The key is a digest of the form's label and the field name. It is unique
    per form field (so two forms searching the same model never collide) and
    opaque (internal module paths are not exposed in the URL).
    """
    digest = hashlib.md5(
        f"{form_label(form_cls)}.{field_name}".encode(),
        usedforsecurity=False,
    )
    return digest.hexdigest()[:16]


def register(key: str, registration: SearchRegistration) -> None:
    """Register a search endpoint (idempotent)."""
    _registry[key] = registration


def get_registration(key: str) -> SearchRegistration | None:
    """Look up a registration by key."""
    return _registry.get(key)


def get_registry() -> dict[str, SearchRegistration]:
    """Return the full registry (for debugging / introspection)."""
    return _registry
