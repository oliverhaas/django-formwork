"""Shared fixtures and helpers for widget-level tests.

Unit and integration tests need no browser.  E2e and screenshot tests
re-export fixtures from ``tests/e2e/conftest.py`` since pytest does not
share conftest fixtures across sibling directories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.contrib.auth.models import User

from django_formwork.forms import FormworkForm
from django_formwork.renderers import FormworkRenderer
from django_formwork.search import SEARCH_PAGE_SIZE
from django_formwork.widgets import ComboBox, ComboBoxMultiple, Select
from django_formwork.widgets.select import ChoiceLabel

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


def _items(request):
    return User.objects.none()


class _ServerSearchForm(FormworkForm):
    """Registers the search that ``server_widget`` points at."""

    item = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=Select(search_fields=["username"], search_queryset=_items, search_decorator=None),
    )


SERVER_KEY = _ServerSearchForm.base_fields["item"].widget.search_key


def server_widget(
    widget_cls,
    *,
    count: int = SEARCH_PAGE_SIZE + 5,
    icons: bool = False,
    descriptions: bool = False,
    selected_toggle_classes: bool = False,
    **kwargs,
):
    """A widget with a registered search; past one page of choices it renders server mode."""
    if widget_cls in (ComboBox, ComboBoxMultiple):
        return widget_cls(search_key=SERVER_KEY, **kwargs)
    choices = [
        (
            str(i),
            ChoiceLabel(
                f"Item {i}",
                icon=f"\U0001f4cd{i}" if icons else "",
                description=f"desc {i}" if descriptions else "",
                selected_toggle_class="select-error" if selected_toggle_classes else "",
            ),
        )
        for i in range(count)
    ]
    return widget_cls(search_key=SERVER_KEY, choices=choices, **kwargs)


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


@pytest.fixture
def renderer() -> FormworkRenderer:
    return FormworkRenderer()
