"""CascadeSelect widget tests: unit → integration → e2e → screenshot.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_cascade_select.py                 # everything
    uv run pytest tests/widgets/test_cascade_select.py -m unit         # fast only
    uv run pytest tests/widgets/test_cascade_select.py -m "not e2e"    # skip browser

Levels:
    1. unit        — widget object: instantiation, get_context, defaults, choices
    2. unit        — widget rendering: HTML structure, options, selected, htmx attrs
    3. integration — form integration: fieldset, error state, prefix
    4. integration — Jinja2/DTL parity
    5. e2e         — (no dedicated page yet — tracked for future work)
    6. e2e         — (no dedicated page yet)
    7. e2e         — (no dedicated page yet)
    8. screenshot  — (no dedicated page yet)
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import CascadeSelect

from .conftest import assert_html_equivalent, render_form, render_widget

CITY_CHOICES = [("nyc", "New York"), ("ldn", "London"), ("tyo", "Tokyo")]


class CascadeSelectForm(FormworkForm):
    """Form fixture for CascadeSelect integration tests."""

    city = forms.ChoiceField(
        choices=CITY_CHOICES,
        widget=CascadeSelect(parent_field="country", search_url="/api/cities/"),
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_cascade_select_instantiation():
    """CascadeSelect stores parent_field and search_url on the instance."""
    widget = CascadeSelect(parent_field="country", search_url="/api/cities/")
    assert widget.parent_field == "country"
    assert widget.search_url == "/api/cities/"


@pytest.mark.unit
def test_cascade_select_get_context():
    """get_context() includes parent_field and search_url in widget context."""
    widget = CascadeSelect(parent_field="country", search_url="/api/cities/")
    ctx = widget.get_context("city", None, {"id": "id_city"})
    assert ctx["widget"]["parent_field"] == "country"
    assert ctx["widget"]["search_url"] == "/api/cities/"


@pytest.mark.unit
def test_cascade_select_default_empty():
    """parent_field and search_url default to empty strings."""
    widget = CascadeSelect()
    assert widget.parent_field == ""
    assert widget.search_url == ""


@pytest.mark.unit
def test_cascade_select_value_from_datadict():
    """value_from_datadict delegates to standard Select behaviour."""
    widget = CascadeSelect(parent_field="country", search_url="/api/cities/")
    data = QueryDict("city=ldn")
    result = widget.value_from_datadict(data, {}, "city")
    assert result == "ldn"


@pytest.mark.unit
def test_cascade_select_choices():
    """Choices passed at construction are accessible on the widget."""
    widget = CascadeSelect(choices=CITY_CHOICES)
    values = [v for v, _label in widget.choices]
    assert "nyc" in values
    assert "ldn" in values
    assert "tyo" in values


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_cascade_select_renders_select():
    """render() produces a <select> element."""
    widget = CascadeSelect(choices=CITY_CHOICES)
    soup = render_widget(widget, name="city")
    assert soup.find("select") is not None


@pytest.mark.unit
def test_cascade_select_renders_options():
    """Rendered <select> contains an <option> for each choice."""
    widget = CascadeSelect(choices=CITY_CHOICES)
    soup = render_widget(widget, name="city")
    options = soup.find_all("option")
    option_values = [opt.get("value") for opt in options]
    assert "nyc" in option_values
    assert "ldn" in option_values
    assert "tyo" in option_values


@pytest.mark.unit
def test_cascade_select_renders_selected():
    """The option matching the current value has the selected attribute."""
    widget = CascadeSelect(choices=CITY_CHOICES)
    soup = render_widget(widget, name="city", value="ldn")
    selected = soup.find("option", selected=True)
    assert selected is not None
    assert selected["value"] == "ldn"


@pytest.mark.unit
def test_cascade_select_renders_htmx_attrs():
    """hx-get and hx-trigger are present on the <select> when search_url is set."""
    widget = CascadeSelect(
        choices=CITY_CHOICES,
        parent_field="country",
        search_url="/api/cities/",
    )
    soup = render_widget(widget, name="city")
    select = soup.find("select")
    assert select is not None
    assert select.get("hx-get") == "/api/cities/"
    assert select.get("hx-trigger") is not None


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_cascade_select_renders_via_form(renderer):
    """CascadeSelect renders correctly when used inside a FormworkForm."""
    form = CascadeSelectForm()
    soup = render_form(form, renderer=renderer)
    select = soup.find("select", attrs={"name": "city"})
    assert select is not None


@pytest.mark.integration
def test_cascade_select_form_wraps_in_fieldset(renderer):
    """Field template wraps the CascadeSelect in a fieldset with a stable id."""
    form = CascadeSelectForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_city_field")
    assert fieldset is not None


@pytest.mark.integration
def test_cascade_select_error_state(renderer):
    """Bound form with errors adds aria-invalid='true' to the <select>."""
    form = CascadeSelectForm(data={})
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    select = soup.find("select", attrs={"name": "city"})
    assert select is not None
    assert select.get("aria-invalid") == "true"


@pytest.mark.integration
def test_cascade_select_form_prefix(renderer):
    """Form prefix propagates to widget name and id."""
    form = CascadeSelectForm(prefix="loc")
    soup = render_form(form, renderer=renderer)
    select = soup.find("select", attrs={"name": "loc-city"})
    assert select is not None
    assert select["id"] == "id_loc-city"


# ─── Level 4: Renderer parity (DTL vs Jinja2) ────────────────────────────


@pytest.mark.integration
def test_cascade_select_dtl_jinja2_parity(dtl_renderer, jinja2_renderer):
    """DTL and Jinja2 renderers produce equivalent HTML for CascadeSelect."""
    form_dtl = CascadeSelectForm()
    form_jinja2 = CascadeSelectForm()

    soup_dtl = render_form(form_dtl, renderer=dtl_renderer)
    soup_jinja2 = render_form(form_jinja2, renderer=jinja2_renderer)

    select_dtl = soup_dtl.find("select", attrs={"name": "city"})
    select_jinja2 = soup_jinja2.find("select", attrs={"name": "city"})

    assert select_dtl is not None
    assert select_jinja2 is not None
    assert_html_equivalent(select_dtl, select_jinja2)


# ─── Level 5-7: E2e interaction / error flow / morph resilience ──────────
#
# CascadeSelect depends on a parent field and a live htmx endpoint; no
# dedicated test page exists yet.  E2e coverage is deferred until a
# suitable page is added.  Tracked as future work.


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# No dedicated page exists yet; screenshot tests are deferred alongside
# the e2e work above.
