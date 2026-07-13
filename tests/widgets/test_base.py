"""Tests for shared widget base helpers."""

from __future__ import annotations

import logging

import pytest

from django_formwork.widgets._base import _resolve_initial_results


@pytest.mark.unit
def test_resolve_initial_results_logs_swallowed_errors(caplog):
    """A crashing registration resolves to (None, []) and emits a warning with traceback."""
    from django_formwork._registry import SearchRegistration, register

    def _boom(query, request=None):
        raise RuntimeError("search backend down")

    register("tests.base.boom", SearchRegistration(search_func=_boom))
    with caplog.at_level(logging.WARNING, logger="django_formwork.widgets._base"):
        result = _resolve_initial_results("tests.base.boom")
    assert result == (None, [])
    record = next(r for r in caplog.records if "tests.base.boom" in r.getMessage())
    assert record.levelno == logging.WARNING
    assert record.exc_info is not None
