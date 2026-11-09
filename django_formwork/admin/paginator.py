"""A paginator that reads PostgreSQL's row estimate for a large unfiltered list."""

from __future__ import annotations

import logging
from typing import Any

from django.core.paginator import Paginator
from django.db import DatabaseError, connections
from django.db.models import QuerySet
from django.utils.functional import cached_property

__all__ = ["EstimatedCountPaginator", "table_estimate"]

logger = logging.getLogger(__name__)


def table_estimate(queryset: QuerySet[Any]) -> int | None:
    """``pg_class.reltuples`` for the table behind ``queryset``, None when unknown."""
    connection = connections[queryset.db]
    if connection.vendor != "postgresql":
        return None
    table = connection.ops.quote_name(queryset.model._meta.db_table)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", [table])
            row = cursor.fetchone()
    except DatabaseError:
        logger.warning("Could not read the row estimate of %s", table, exc_info=True)
        return None
    # -1 until the table was first analyzed.
    return row[0] if row and row[0] >= 0 else None


class EstimatedCountPaginator(Paginator):
    """Counts an unfiltered PostgreSQL table from its row estimate past ``estimate_threshold``.

    Any filter, ``DISTINCT`` or slice falls back to ``COUNT(*)``.
    """

    estimate_threshold = 10_000
    is_estimate = False

    @cached_property
    def count(self) -> int:
        queryset = self.object_list
        if isinstance(queryset, QuerySet) and self._estimable(queryset):
            estimate = table_estimate(queryset)
            if estimate is not None and estimate >= self.estimate_threshold:
                self.is_estimate = True
                return estimate
        return super().count

    @staticmethod
    def _estimable(queryset: QuerySet[Any]) -> bool:
        query = queryset.query
        return not (query.where or query.distinct or query.combinator or query.is_sliced)
