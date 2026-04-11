"""Canonical test patterns for a formwork widget (Toggle as exemplar).

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_toggle.py                 # everything
    uv run pytest tests/widgets/ -m unit                       # all widgets, unit only
    uv run pytest tests/widgets/test_toggle.py -m "not e2e"    # skip browser tests

Levels:
    1. unit        — widget object: instantiation, get_context, value_from_datadict
    2. unit        — widget rendering: HTML structure, classes, attributes
    3. integration — form integration: field template, error state, morph IDs
    4. integration — Jinja2/DTL parity: identical HTML across engines
    5. e2e         — user interaction: fill, click, submit
    6. e2e         — error flow: validation errors appear and clear
    7. e2e         — morph resilience: state preserved across htmx morphs
    8. screenshot  — visual states: default, checked, error
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Toggle


class ToggleForm(FormworkForm):
    """Form fixture for Toggle integration tests."""

    enabled = forms.BooleanField(widget=Toggle, required=True)


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_toggle_instantiation_has_default_class():
    """Toggle widget adds 'toggle' to its default attrs."""
    widget = Toggle()
    assert "toggle" in widget.attrs.get("class", "")


@pytest.mark.unit
def test_toggle_preserves_user_attrs():
    """User-supplied attrs (including class) are merged with defaults."""
    widget = Toggle(attrs={"class": "my-toggle"})
    cls = widget.attrs.get("class", "")
    assert "toggle" in cls
    assert "my-toggle" in cls


@pytest.mark.unit
def test_toggle_get_context_returns_checkbox_type():
    """get_context() produces a context dict where the widget renders as a checkbox."""
    widget = Toggle()
    ctx = widget.get_context("enabled", True, {"id": "id_enabled"})  # noqa: FBT003
    assert ctx["widget"]["type"] == "checkbox"
    assert ctx["widget"]["name"] == "enabled"
    assert ctx["widget"]["attrs"]["id"] == "id_enabled"


@pytest.mark.unit
def test_toggle_value_from_datadict_checked():
    """Submitted checked checkbox returns True."""
    widget = Toggle()
    data = QueryDict("enabled=on")
    assert widget.value_from_datadict(data, {}, "enabled") is True


@pytest.mark.unit
def test_toggle_value_from_datadict_unchecked():
    """Unchecked checkbox returns False (name missing from QueryDict)."""
    widget = Toggle()
    data = QueryDict("")
    assert widget.value_from_datadict(data, {}, "enabled") is False


@pytest.mark.unit
def test_toggle_get_context_with_value_none():
    """Passing value=None is tolerated — widget renders unchecked."""
    widget = Toggle()
    ctx = widget.get_context("enabled", None, {"id": "id_enabled"})
    assert ctx["widget"]["value"] is None
