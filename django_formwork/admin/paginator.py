"""A paginator that reads PostgreSQL's row estimate for a large unfiltered list, and the links of a pager."""

from __future__ import annotations

import logging
from itertools import pairwise
from typing import Any, NamedTuple

from django.core.paginator import Paginator
from django.db import DatabaseError, connections
from django.db.models import QuerySet
from django.utils.functional import cached_property

__all__ = ["EstimatedCountPaginator", "PageLink", "page_links", "table_estimate"]

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


class PageLink(NamedTuple):
    """A page number of a pager, or None for an ellipsis where the run skips pages.

    ``wide`` and ``narrow`` tell whether the link shows on a wide and on a narrow screen.
    """

    page: int | None
    wide: bool
    narrow: bool


def page_links(paginator: Paginator[Any], number: int) -> list[PageLink]:
    """The links of a pager at page ``number``.

    A wide screen shows two pages on each side of the current one. A narrow screen shows the first,
    the current and the last page, so that the pager fits on a phone.
    """
    wide = list(paginator.get_elided_page_range(number, on_each_side=2, on_ends=1))
    narrow = list(paginator.get_elided_page_range(number, on_each_side=0, on_ends=1))
    wide_gaps = {page for before, page in pairwise(wide) if not isinstance(before, int)}
    narrow_gaps = {page for before, page in pairwise(narrow) if not isinstance(before, int)}
    links = []
    for page in wide:
        if not isinstance(page, int):
            continue
        if page in wide_gaps or page in narrow_gaps:
            links.append(PageLink(None, wide=page in wide_gaps, narrow=page in narrow_gaps))
        links.append(PageLink(page, wide=True, narrow=page in narrow))
    return links
