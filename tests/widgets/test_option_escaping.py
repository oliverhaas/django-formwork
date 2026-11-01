"""Escaping contract for the select family: option values live only in HTML attributes.

They round-trip through `dataset` and the POSTed `value`, and no Alpine expression carries one.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from django_formwork import ChoiceLabel
from django_formwork.widgets import Select

HOSTILE_VALUES = [
    "uuid-1234",  # hyphen: escapejs encodes it, HTML escaping does not
    "H&M",  # ampersand
    "O'Brien & Sons",  # apostrophe + ampersand
    "a\"b'c<d>e&f=g;h`i\\j",  # one of every char escapejs encodes
    "'); alert(1); ('",  # JS-string break-out attempt
    "</button><script>alert(1)</script>",  # HTML break-out attempt
]

WIDGETS = ["select", "combo_box", "select_multiple"]

PILL = mark_safe('<b class="pill">Jeans</b>')


def _render_options(*, widget: str, value: str, label: str) -> BeautifulSoup:
    """Render a widget's server-search option fragment the way FormworkSearchView does."""
    html = render_to_string(
        f"formwork/widgets/{widget}.html#option_list",
        {"options": [{"value": value, "label": label, "icon": "", "description": ""}]},
    )
    return BeautifulSoup(html, "html.parser")


@pytest.mark.unit
@pytest.mark.parametrize("value", HOSTILE_VALUES)
@pytest.mark.parametrize("widget", WIDGETS)
def test_data_attributes_round_trip(widget: str, value: str) -> None:
    """data-value/data-label survive a `dataset` read byte-for-byte (bs4 decodes as the browser does).

    select_multiple carries data-value on both its label and checkbox, so every one must round-trip.
    """
    label = f"label {value}"
    soup = _render_options(widget=widget, value=value, label=label)

    value_els = soup.select("[data-value]")
    assert value_els
    for el in value_els:
        assert el.get("data-value") == value

    label_el = soup.select_one("[data-label]")
    assert label_el is not None
    assert label_el.get("data-label") == label


@pytest.mark.unit
@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_select_multiple_submitted_value_round_trips(value: str) -> None:
    """The checkbox `value` is what the form POSTs; escapejs here corrupts saved data."""
    soup = _render_options(widget="select_multiple", value=value, label="label")
    checkbox = soup.select_one("input[type=checkbox]")
    assert checkbox is not None
    assert checkbox.get("value") == value


@pytest.mark.unit
@pytest.mark.parametrize("value", HOSTILE_VALUES)
@pytest.mark.parametrize("widget", WIDGETS)
def test_no_option_data_reaches_a_js_expression(widget: str, value: str) -> None:
    """Alpine expressions read the option off the DOM and never carry it inline.

    An inline value needs escapejs on top of HTML escaping, and the two disagree on `-`.
    """
    label = f"label {value}"
    soup = _render_options(widget=widget, value=value, label=label)

    for el in soup.find_all(name=True):
        for name, attr in el.attrs.items():
            if not name.startswith((":", "@", "x-")):
                continue
            expr = " ".join(attr) if isinstance(attr, list) else attr
            assert value not in expr, f"{name}={expr}"
            assert label not in expr, f"{name}={expr}"


@pytest.mark.unit
@pytest.mark.parametrize("widget", WIDGETS)
def test_hostile_option_injects_no_markup(widget: str) -> None:
    """A hostile value or label cannot inject markup through the visible text."""
    hostile = "</button></label></span><script>alert(1)</script>"
    soup = _render_options(widget=widget, value=hostile, label=hostile)
    assert soup.select_one("script") is None


@pytest.mark.unit
@pytest.mark.parametrize("widget", WIDGETS)
def test_label_html_renders_raw_while_data_label_stays_text(widget: str) -> None:
    """The rich-option slot is emitted unescaped; the filter and toggle read data-label."""
    html = render_to_string(
        f"formwork/widgets/{widget}.html#option_list",
        {
            "options": [
                {
                    "value": "1",
                    "label": "Fashion > Jeans",
                    "icon": "",
                    "description": "",
                    "label_html": PILL,
                },
            ],
        },
    )
    soup = BeautifulSoup(html, "html.parser")

    assert soup.select_one("b.pill") is not None
    label_el = soup.select_one("[data-label]")
    assert label_el is not None
    assert label_el.get("data-label") == "Fashion > Jeans"


@pytest.mark.unit
def test_selected_label_html_reaches_the_closed_toggle() -> None:
    """The trigger swaps to the rich markup, so the toggle matches the option row."""
    widget = Select()
    widget.choices = [("1", ChoiceLabel("Fashion > Jeans", label_html=PILL))]

    html = widget.render("category", "1", attrs={"id": "id_category"})
    soup = BeautifulSoup(html, "html.parser")

    root = soup.select_one("details")
    assert root is not None
    assert root.get("data-label-html") == PILL
    assert soup.select_one('[x-html="labelHtml"]') is not None
