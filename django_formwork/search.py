"""Process-wide registry mapping a stable key to one form field's server-side search.

Forms register at class creation; ``FormworkSearchView`` serves every key.
``ranked_search`` orders a search by match quality on PostgreSQL.
"""

from __future__ import annotations

import annotationlib
import hashlib
import inspect
from functools import cache, partial
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models import Case, Func, Q, TextField, Value, When
from django.db.models.functions import Cast, Upper
from django.urls import reverse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from django import forms
    from django.db.models import QuerySet

__all__ = [
    "RESERVED_PARAMS",
    "SEARCH_PAGE_SIZE",
    "check_search_params",
    "declared_params",
    "get_field",
    "ranked_search",
    "register_form_searches",
    "search_url",
]

_registry: dict[str, forms.Field] = {}

# The dispatch view reads these itself, so no search param can take their names.
RESERVED_PARAMS = frozenset({"allow_clear", "exclude", "offset", "q", "widget"})
_PARAM_TYPES: dict[str, type] = {"int": int, "str": str}
# Rows per search page; a searchable select renders the first page itself.
SEARCH_PAGE_SIZE = 20
# Shorter queries give pg_trgm too few trigrams to rank by, so they rank by prefix.
_TRIGRAM_MIN_QUERY_LENGTH = 3


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
        msg = f"{getattr(queryset, '__qualname__', queryset)} takes {sorted(expected)}, got {sorted(params)}"
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


def _any_field(fields: Sequence[str], lookup: str, query: str) -> Q:
    return Q.create([(f"{name}__{lookup}", query) for name in fields], connector=Q.OR)


def ranked_search(queryset: QuerySet[Any], fields: Sequence[str], query: str) -> QuerySet[Any]:
    """The rows with ``query`` in one of ``fields``, best match first; typos match too.

    Needs PostgreSQL with the pg_trgm extension. A trigram index on
    ``UPPER(field::text)`` per field serves every lookup used here.
    """
    # Deferred: django.contrib.postgres imports the PostgreSQL driver.
    from django.contrib.postgres.lookups import TrigramWordSimilar
    from django.contrib.postgres.search import TrigramSimilarity, TrigramStrictWordSimilarity

    contains = _any_field(fields, "icontains", query)
    order = queryset.query.order_by or queryset.model._meta.ordering  # noqa: SLF001
    if len(query) < _TRIGRAM_MIN_QUERY_LENGTH:
        rank = Case(
            When(_any_field(fields, "iexact", query), then=Value(0)),
            When(_any_field(fields, "istartswith", query), then=Value(1)),
            default=Value(2),
        )
        return queryset.filter(contains).order_by(rank, *order)
    # The shape __icontains compiles to, so the trigram index serves both.
    uppers = [Upper(Cast(name, output_field=TextField())) for name in fields]
    similar = Q.create([Q(TrigramWordSimilar(upper, query)) for upper in uppers], connector=Q.OR)
    # Values that contain the query before typo matches, then whole-word matches,
    # then the closest value. Unlike Greatest(), GREATEST takes a single field.
    typo = Case(When(contains, then=Value(0)), default=Value(1))
    word_score = Func(*(TrigramStrictWordSimilarity(query, upper) for upper in uppers), function="GREATEST")
    score = Func(*(TrigramSimilarity(upper, query) for upper in uppers), function="GREATEST")
    return queryset.filter(contains | similar).order_by(typo, word_score.desc(), score.desc(), *order)


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
    from django_formwork.widgets.select import SearchableSelectMixin

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

        _check_search(f"{form_cls.__name__}.{name}", widget)
        widget.search_key = _search_key(f"{form_label}.{name}", widget)
        _registry[widget.search_key] = field


def _check_search(label: str, widget: Any) -> None:  # noqa: ANN401
    """Fail at import, not on the first search."""
    from django_formwork.widgets.select import _UnsetDecorator

    if isinstance(widget.search_decorator, _UnsetDecorator):
        msg = (
            f"{label}: search_queryset needs an explicit "
            f"search_decorator (e.g. login_required) or None for a public endpoint."
        )
        raise ImproperlyConfigured(msg)

    if widget.search_ranked and not widget.search_fields:
        msg = f"{label}: search_ranked ranks the search_fields, and none are set."
        raise ImproperlyConfigured(msg)

    if widget.search_ranked and connection.vendor != "postgresql":
        msg = (
            f"{label}: search_ranked needs PostgreSQL with the pg_trgm "
            f"extension, but the default database is {connection.vendor}."
        )
        raise ImproperlyConfigured(msg)

    if not callable(widget.search_queryset):
        msg = (
            f"{label}: search_queryset must be a callable that takes the request, "
            f"got {type(widget.search_queryset).__name__}. Wrap a queryset: "
            f"lambda request: Model.objects.filter(...)."
        )
        raise ImproperlyConfigured(msg)

    declared_params(widget.search_queryset)


def _search_key(field_label: str, widget: Any) -> str:  # noqa: ANN401
    """A stable, opaque key: the same in every worker.

    Factory-built forms share a class name, so the search's definition joins the key.
    """
    source = ":".join(
        [
            field_label,
            _definition(widget.search_queryset),
            _definition(widget.search_decorator),
            ",".join(widget.search_fields or ()),
        ],
    )
    key = hashlib.md5(source.encode(), usedforsecurity=False).hexdigest()[:16]
    registered = _registry.get(key)
    if registered is not None and not (
        _same_definition(registered.widget.search_queryset, widget.search_queryset)
        and _same_definition(registered.widget.search_decorator, widget.search_decorator)
    ):
        msg = (
            f"{field_label}: a form of the same name already registered this search with "
            f"other closure values. The endpoint serves one search per key, so scope the "
            f"search_queryset through its request argument, not through variables it closes over."
        )
        raise ImproperlyConfigured(msg)
    return key


def _definition(obj: object) -> str:
    """Where ``obj`` is defined: the same in every worker, unlike ``id()``."""
    func: Any = getattr(obj, "__func__", obj)
    while isinstance(func, partial):
        func = func.func
    code = getattr(func, "__code__", None)
    if code is None:
        return f"{type(obj).__module__}.{type(obj).__qualname__}"
    return f"{func.__module__}.{func.__qualname__}:{code.co_firstlineno}"


def _same_definition(a: object, b: object, seen: set[tuple[int, int]] | None = None) -> bool:
    """True for the same callable, or two built from one definition with equal bound values."""
    seen = set() if seen is None else seen
    if a is b or (id(a), id(b)) in seen:  # a function that closes over itself
        return True
    seen.add((id(a), id(b)))
    parts_a, parts_b = _parts(a), _parts(b)
    if parts_a is None or parts_b is None:
        try:
            return bool(a == b)
        except Exception:  # noqa: BLE001 (an __eq__ that raises is not a match)
            return False
    return len(parts_a) == len(parts_b) and all(
        _same_definition(x, y, seen) for x, y in zip(parts_a, parts_b, strict=True)
    )


def _parts(obj: object) -> list[Any] | None:
    """What a callable built from one definition can differ by between calls; None for a non-callable."""
    if isinstance(obj, partial):
        return [obj.func, *obj.args, *sorted(obj.keywords.items())]
    func: Any = getattr(obj, "__func__", obj)
    code = getattr(func, "__code__", None)
    if code is None:
        return None
    try:
        cells = [cell.cell_contents for cell in func.__closure__ or ()]
    except ValueError:  # an unfilled cell
        cells = [object()]
    defaults = [*(func.__defaults__ or ()), *sorted((func.__kwdefaults__ or {}).items())]
    return [code, getattr(obj, "__self__", None), *cells, *defaults]
