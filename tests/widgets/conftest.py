"""Shared fixtures and helpers for widget-level tests.

Unit and integration tests need no browser.  E2e and screenshot tests
re-export fixtures from ``tests/e2e/conftest.py`` since pytest does not
share conftest fixtures across sibling directories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup

from django_formwork.renderers import FormworkRenderer

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
    """Register a widget's search as FormworkForm would, without a form.

    ``count`` sizes a fake queryset of objects with label, icon, description and toggle class.
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
    """Build a Select/SelectMultiple/ComboBox already wired into the registry."""
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


@pytest.fixture(autouse=True)
def _clean_widget_registry():
    """Drop any registry entries created by ``attach_server_search`` so tests
    don't leak state across the module."""
    from django_formwork._registry import clear_registry

    yield
    clear_registry()


@pytest.fixture
def renderer() -> FormworkRenderer:
    return FormworkRenderer()
