"""Process-wide registry mapping a stable key to one form field's server-side search.

Forms register at class creation; ``FormworkSearchView`` serves every key.
"""

from __future__ import annotations

import annotationlib
import hashlib
import inspect
from functools import cache
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.urls import reverse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from django import forms

__all__ = [
    "RESERVED_PARAMS",
    "SEARCH_PAGE_SIZE",
    "check_search_params",
    "declared_params",
    "get_field",
    "register_form_searches",
    "search_url",
]

_registry: dict[str, forms.Field] = {}

# The dispatch view reads these itself, so no search param can take their names.
RESERVED_PARAMS = frozenset({"allow_clear", "exclude", "offset", "q", "widget"})
_PARAM_TYPES: dict[str, type] = {"int": int, "str": str}
# Rows per search page; a searchable select renders the first page itself.
SEARCH_PAGE_SIZE = 20


@cache
def declared_params(queryset: Callable[..., Any]) -> dict[str, type]:
    """The keyword-only ``int`` or ``str`` params ``queryset`` takes after the request."""
    # FORWARDREF: a request annotation imported under TYPE_CHECKING must not fail.
    signature = inspect.signature(queryset, annotation_format=annotationlib.Format.FORWARDREF)
    params: dict[str, type] = {}
    for name, param in list(signature.parameters.items())[1:]:
        annotation = param.annotation
        # Under `from __future__ import annotations` the annotation is the string "int".
        if isinstance(annotation, str):
            annotation = _PARAM_TYPES.get(annotation, annotation)
        if (
            param.kind is not inspect.Parameter.KEYWORD_ONLY
            or annotation not in _PARAM_TYPES.values()
            or name in RESERVED_PARAMS
        ):
            msg = (
                f"{getattr(queryset, '__qualname__', queryset)}: {name!r} must be a keyword-only int or str "
                f"param not named {sorted(RESERVED_PARAMS)}."
            )
            raise ImproperlyConfigured(msg)
        params[name] = annotation
    return params


def check_search_params(key: str, params: Mapping[str, int | str]) -> None:
    """Raise unless ``key`` is registered and ``params`` names its queryset's params."""
    field = _registry.get(key)
    if field is None:
        msg = f"No search is registered under the key {key!r}."
        raise ImproperlyConfigured(msg)
    queryset = field.widget.search_queryset
    if params.keys() != (expected := declared_params(queryset)).keys():
        msg = f"{queryset.__qualname__} takes {sorted(expected)}, got {sorted(params)}"
        raise ImproperlyConfigured(msg)


def search_url(
    key: str,
    params: Mapping[str, int | str],
    *,
    widget: str,
    allow_clear: bool = False,
) -> str:
    """The endpoint URL for one widget variant of the search registered under ``key``."""
    check_search_params(key, params)
    query = {**params, "widget": widget}
    if allow_clear:
        query["allow_clear"] = "1"
    path = reverse("formwork:search", kwargs={"key": key})
    return f"{path}?{urlencode(query)}"


def get_field(key: str) -> forms.Field | None:
    return _registry.get(key)


def register_form_searches(form_cls: type) -> None:
    """Register the search of each widget that declares a ``search_queryset``.

    A field whose ``search_queryset`` takes params is a template: fields built in
    ``__init__`` reuse its ``search_key`` with their own ``search_params``.
    """
    form_label = f"{form_cls.__module__}.{form_cls.__qualname__}"
    base_fields = getattr(form_cls, "base_fields", None)
    if not base_fields:
        return

    # Deferred: importing widgets at call time keeps this module a leaf.
    from django_formwork.widgets.combo_box import ComboBox
    from django_formwork.widgets.select import SearchableSelectMixin, _UnsetDecorator

    for name, field in base_fields.items():
        widget = field.widget
        if not isinstance(widget, (SearchableSelectMixin, ComboBox)):
            continue

        # Django copies a widget per field, so a key means an inherited field.
        # Re-keying it leaves the parent rendering the child's URL.
        if widget.search_key is not None:
            continue

        # The class-level `field.queryset` misses a queryset narrowed in `__init__`.
        if widget.search_queryset is None:
            if widget.search_fields:
                msg = (
                    f"{form_cls.__name__}.{name}: search_fields needs an explicit "
                    f"search_queryset callable (e.g. lambda request: Model.objects.filter(...)), "
                    f"because the endpoint cannot see a queryset narrowed in __init__."
                )
                raise ImproperlyConfigured(msg)
            continue

        if isinstance(widget.search_decorator, _UnsetDecorator):
            msg = (
                f"{form_cls.__name__}.{name}: search_queryset needs an explicit "
                f"search_decorator (e.g. login_required) or None for a public endpoint."
            )
            raise ImproperlyConfigured(msg)

        if widget.search_ranked and connection.vendor != "postgresql":
            msg = f"{form_cls.__name__}.{name}: search_ranked needs PostgreSQL, got {connection.vendor}."
            raise ImproperlyConfigured(msg)

        # Fails at import, not on the first search.
        declared_params(widget.search_queryset)
        # A stable, opaque key: the same form and field map to it in every worker.
        digest = hashlib.md5(f"{form_label}.{name}".encode(), usedforsecurity=False)
        widget.search_key = digest.hexdigest()[:16]
        _registry[widget.search_key] = field
