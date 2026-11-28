from __future__ import annotations

from collections import defaultdict

import pytest

from django_formwork import widgets as w
from django_formwork.widgets._base import size_classes

from .conftest import render_widget


@pytest.mark.unit
@pytest.mark.parametrize(
    ("classes", "expected"),
    [
        ("input-sm", "input-sm"),
        ("w-48 input-lg max-w-xl text-sm", "input-lg"),
        ("input-sm md:input-lg", "input-sm md:input-lg"),
        ("select-xs textarea-md file-input-xl otp-sm", "select-xs textarea-md file-input-xl otp-sm"),
        ("btn-sm checkbox-lg input-small", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_size_classes_keeps_the_size_classes_of_text_controls(classes, expected):
    """Only DaisyUI's size classes of a text control are repeated, with their variant prefixes."""
    assert size_classes(classes) == expected


@pytest.mark.unit
def test_size_classes_names_another_component():
    """With a component, each size class names that component at the same size and variants."""
    assert size_classes("input-sm md:hover:input-lg w-full", "btn") == "btn-sm md:hover:btn-lg"


@pytest.mark.unit
def test_trailing_stepper_buttons_take_the_button_size_of_the_input_size():
    """``input-sm`` on a StepperNumberInput gives its trailing buttons ``btn-sm``."""
    widget = w.StepperNumberInput(attrs={"class": "input-sm"}, trailing_buttons=True)
    buttons = render_widget(widget, name="qty", value=3).select("button")
    assert len(buttons) == 2
    assert all("btn-sm" in button["class"] for button in buttons)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("css_class", "expected"),
    [
        (None, ["otp", "otp-md", "sm:otp-lg"]),
        ("otp-sm", ["otp", "otp-sm"]),
        ("w-full", ["otp", "otp-md", "sm:otp-lg", "w-full"]),
    ],
)
def test_otp_input_sizes_its_boxes_from_the_label(css_class, expected):
    """DaisyUI sizes the boxes from ``.otp``, so the caller's class goes on the label; an otp size replaces the default."""
    attrs = {"class": css_class} if css_class else None
    soup = render_widget(w.OTPInput(attrs=attrs, length=4), name="code")
    assert soup.select_one("label.otp")["class"] == expected
    assert not soup.select_one("input").get("class")


_MEASURE = """() => [...document.querySelectorAll('[data-widget]')].map(cell => {
  const reference = cell.querySelector('.size-reference > *');
  const widget = cell.querySelector('.size-widget');
  const box = widget.querySelector(cell.dataset.box);
  const font = el => parseFloat(getComputedStyle(el).fontSize);
  const height = el => el.getBoundingClientRect().height;
  const shown = el => el.getClientRects().length > 0;
  return {
    widget: cell.dataset.widget,
    size: cell.dataset.size,
    reference: [height(reference), font(reference)],
    box: [height(box), font(box)],
    parts: [...widget.querySelectorAll('.formwork-field-font')].map(font),
    icons: [...widget.querySelectorAll('.icon, .loading')].filter(shown).map(el => el.getBoundingClientRect().width / font(box)),
    buttons: [...widget.querySelectorAll('.btn')].filter(shown).map(el => height(el) / height(box)),
  };
})"""


@pytest.mark.e2e
@pytest.mark.parametrize(("size_field", "input_height"), [(None, 40), ("0.1875rem", 30)], ids=["default", "dense"])
def test_widgets_take_the_size_of_the_daisyui_element(sizes_page, size_field, input_height):
    """At each size class and density, a widget's box has the height and font of DaisyUI's own element."""
    if size_field:
        sizes_page.evaluate(
            "value => document.querySelector('form').style.setProperty('--size-field', value)", size_field
        )
    cells = sizes_page.evaluate(_MEASURE)
    assert len(cells) == 75
    assert next(cell for cell in cells if cell["size"] == "md")["reference"][0] == input_height
    wrong = [
        (cell["widget"], cell["size"], cell["box"], cell["reference"])
        for cell in cells
        if cell["box"] != pytest.approx(cell["reference"], abs=0.5)
    ]
    assert wrong == []


@pytest.mark.e2e
def test_the_parts_around_a_widget_box_follow_its_size(sizes_page):
    """Panels and suffixes take the box's font, and icons and buttons keep their size relative to it at every size."""
    cells = sizes_page.evaluate(_MEASURE)
    off_font = [
        (cell["widget"], cell["size"], cell["parts"])
        for cell in cells
        if any(part != pytest.approx(cell["box"][1], abs=0.1) for part in cell["parts"])
    ]
    scales_by_widget = defaultdict(list)
    for cell in cells:
        scales_by_widget[cell["widget"]].append(cell["icons"] + cell["buttons"])
    off_scale = {
        widget: scales
        for widget, scales in scales_by_widget.items()
        if any(len(sized) != len(scales[0]) or sized != pytest.approx(scales[0], abs=0.02) for sized in scales)
    }
    assert off_font == []
    assert off_scale == {}
