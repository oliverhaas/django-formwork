"""Shared fixtures and helpers for widget-level tests.

Unit and integration tests need no browser.  E2e and screenshot tests
re-export fixtures from ``tests/e2e/conftest.py`` since pytest does not
share conftest fixtures across sibling directories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup, NavigableString, Tag

from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

# Re-export e2e fixtures and the autouse settings override so e2e widget
# tests in this directory can use them.  Listed in __all__ to satisfy
# ruff's unused-import check.
from tests.e2e.conftest import (  # noqa: F401
    _e2e_settings,
    simple_page,
    toggle_page,
)

if TYPE_CHECKING:
    from django.forms.renderers import BaseRenderer


def render_widget(widget, name: str = "test", value=None, attrs: dict | None = None) -> BeautifulSoup:
    """Render a widget in isolation and return a BeautifulSoup tree."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


def render_form(form, renderer: BaseRenderer | None = None) -> BeautifulSoup:
    """Render a form via a formwork renderer and return a BeautifulSoup tree."""
    if renderer is not None:
        form.renderer = renderer
    return BeautifulSoup(str(form), "html.parser")


def _normalize(node: Tag | NavigableString) -> tuple:
    """Reduce an element to a comparable tuple, ignoring insignificant whitespace."""
    if isinstance(node, NavigableString):
        return ("text", " ".join(str(node).split()))
    children = [_normalize(c) for c in node.children if not (isinstance(c, NavigableString) and not str(c).strip())]
    return (node.name, dict(sorted(node.attrs.items())), children)


def assert_html_equivalent(a: Tag, b: Tag) -> None:
    """Assert two BeautifulSoup elements are equivalent, ignoring insignificant whitespace.

    Compares tag names, attribute dicts (order-insensitive), and children
    recursively.  Whitespace-only text nodes between elements are skipped.
    Text node whitespace is collapsed to single spaces.
    """
    norm_a = _normalize(a)
    norm_b = _normalize(b)
    assert norm_a == norm_b, f"HTML trees differ.\nA:\n{a}\n\nB:\n{b}"


@pytest.fixture
def dtl_renderer() -> FormworkRenderer:
    return FormworkRenderer()


@pytest.fixture
def jinja2_renderer() -> FormworkJinja2Renderer:
    return FormworkJinja2Renderer()
