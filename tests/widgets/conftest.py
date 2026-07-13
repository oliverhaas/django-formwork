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

# Re-export e2e fixtures, the submit helper, and the autouse settings
# override so e2e widget tests in this directory can use them.
from tests.e2e.conftest import (  # noqa: F401
    _e2e_settings,
    basic_page,
    builtin_page,
    combobox_page,
    multi_select_page,
    new_widgets_page,
    search_select_page,
    simple_page,
    submit,
    textarea_page,
    toggle_page,
    uploads_page,
)

if TYPE_CHECKING:
    from django.forms.renderers import BaseRenderer


def render_widget(widget, name: str = "test", value=None, attrs: dict | None = None) -> BeautifulSoup:
    """Render a widget in isolation and return a BeautifulSoup tree."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


def attach_server_search(  # noqa: PLR0913
    widget,
    *,
    count: int | None = None,
    icons: bool = False,
    descriptions: bool = False,
    selected_toggle_classes: bool = False,
    key: str | None = None,
) -> None:
    """Wire a SearchSelect/MultiSelect/ComboBox into the registry as if it were
    auto-registered, so unit tests can exercise the server-side rendering paths
    without going through a full FormworkForm.

    ``count`` populates a fake queryset whose ``.count()`` and slicing yield
    that many objects with ``label`` / ``icon`` / ``description`` /
    ``selected_toggle_class`` attributes.
    """
    from django_formwork._registry import SearchRegistration, register

    key = key or f"tests.widget.{type(widget).__name__}.{id(widget)}"

    class _Obj:
        def __init__(self, i: int) -> None:
            self.pk = str(i)
            self.label = f"Item {i}"
            self.icon = f"\U0001f4cd{i}" if icons else ""
            self.description = f"desc {i}" if descriptions else ""
            self.selected_toggle_class = "select-error" if selected_toggle_classes else ""

        def __str__(self) -> str:
            return self.label

    class _QS:
        def __init__(self, n: int) -> None:
            self._items = [_Obj(i) for i in range(n)]

        def count(self) -> int:
            return len(self._items)

        def all(self) -> _QS:
            return self

        def __getitem__(self, key):
            return self._items[key]

        def __iter__(self):
            return iter(self._items)

    n = count if count is not None else 0
    factory = (lambda: _QS(n)) if count is not None else None
    register(
        key,
        SearchRegistration(
            queryset_factory=factory,
            search_fields=("label",) if factory else (),
            label_from_instance=(lambda obj: obj.label) if factory else None,
            icon_from_instance=(lambda obj: obj.icon) if (factory and icons) else None,
            description_from_instance=(lambda obj: obj.description) if (factory and descriptions) else None,
            selected_toggle_class_from_instance=(
                (lambda obj: obj.selected_toggle_class) if (factory and selected_toggle_classes) else None
            ),
        ),
    )
    widget._registry_key = key


def make_server_widget(
    widget_cls,
    *,
    count: int | None = 10,
    icons: bool = False,
    descriptions: bool = False,
    selected_toggle_classes: bool = False,
    **kwargs,
):
    """Build a SearchSelect/MultiSelect/ComboBox already wired into the registry.

    Drop-in for tests that previously created a widget with ``search_url=``
    and expected server-side mode to be active.
    """
    widget = widget_cls(**kwargs)
    attach_server_search(
        widget,
        count=count,
        icons=icons,
        descriptions=descriptions,
        selected_toggle_classes=selected_toggle_classes,
    )
    return widget


def render_form(form, renderer: BaseRenderer | None = None) -> BeautifulSoup:
    """Render a form via a formwork renderer and return a BeautifulSoup tree."""
    if renderer is not None:
        form.renderer = renderer
    return BeautifulSoup(str(form), "html.parser")


def open_dropdown(page, css_class: str, index: int, settle_ms: int = 150):
    """Open the nth <details> dropdown widget by clicking its summary; returns its locator."""
    widget = page.locator(f"details.dropdown.{css_class}").nth(index)
    widget.locator("summary").click()
    page.wait_for_timeout(settle_ms)
    return widget


def open_combo_box(page, name: str):
    """Open a ComboBox by clicking its input; returns the input locator."""
    inp = page.locator(f'input[name="{name}"]')
    inp.click()
    page.wait_for_timeout(150)
    return inp


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


@pytest.fixture(autouse=True)
def _clean_widget_registry():
    """Drop any registry entries created by ``attach_server_search`` so tests
    don't leak state across the module."""
    from django_formwork._registry import get_registry

    yield
    get_registry().clear()


@pytest.fixture(params=["dtl", "jinja2"], ids=["dtl", "jinja2"])
def renderer(request) -> FormworkRenderer | FormworkJinja2Renderer:
    """Parametrized renderer: each integration test runs against both engines."""
    if request.param == "dtl":
        return FormworkRenderer()
    return FormworkJinja2Renderer()


@pytest.fixture
def dtl_renderer() -> FormworkRenderer:
    return FormworkRenderer()


@pytest.fixture
def jinja2_renderer() -> FormworkJinja2Renderer:
    return FormworkJinja2Renderer()
