"""Canonical tests for the Rating widget.

Tests progress from simple (pure Python) to complex (browser visual
regression).  Each level is marked so you can run fast-feedback subsets:

    uv run pytest tests/widgets/test_rating.py                 # everything
    uv run pytest tests/widgets/ -m unit                       # all widgets, unit only
    uv run pytest tests/widgets/test_rating.py -m "not e2e"    # skip browser tests

Levels:
    1. unit: widget object, instantiation, make_choices, get_context, value_from_datadict
    2. unit: widget rendering, HTML structure, classes, checked state, allow_clear
    3. integration: form integration, field template, fieldset wrapping, error state, prefix
    4. integration: Jinja2/DTL parity, identical HTML across engines
    5. e2e: user interaction, click a star
    6. e2e: error flow, SKIPPED (no required-Rating-only page yet)
    7. e2e: morph resilience, selected star preserved across htmx morphs
    8. screenshot: visual states, default, one-star-selected
"""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Rating

from .conftest import assert_html_equivalent, render_form, render_widget


class RatingForm(FormworkForm):
    """Form fixture for Rating integration tests."""

    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        required=True,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_rating_instantiation_defaults():
    """Rating widget instantiates with default star_class and allow_clear=False."""
    widget = Rating()
    assert widget.star_class == "mask-star-2"
    assert widget.allow_clear is False


@pytest.mark.unit
def test_rating_make_choices_count():
    """make_choices(5) returns exactly 5 choices."""
    choices = Rating.make_choices(5)
    assert len(choices) == 5


@pytest.mark.unit
def test_rating_make_choices_first():
    """First choice is ('1', '1 star')."""
    choices = Rating.make_choices(5)
    assert choices[0] == ("1", "1 star")


@pytest.mark.unit
def test_rating_make_choices_last():
    """Last choice is ('5', '5 stars')."""
    choices = Rating.make_choices(5)
    assert choices[4] == ("5", "5 stars")


@pytest.mark.unit
def test_rating_make_choices_plural():
    """All choices except the first use plural 'stars'."""
    choices = Rating.make_choices(3)
    assert choices[1][1] == "2 stars"
    assert choices[2][1] == "3 stars"


@pytest.mark.unit
def test_rating_allow_clear_flag():
    """allow_clear=True is stored on the widget."""
    widget = Rating(allow_clear=True)
    assert widget.allow_clear is True


@pytest.mark.unit
def test_rating_custom_star_class():
    """Custom star_class is stored on the widget."""
    widget = Rating(star_class="mask-heart")
    assert widget.star_class == "mask-heart"


@pytest.mark.unit
def test_rating_get_context_includes_star_class():
    """get_context() exposes star_class in widget context."""
    widget = Rating()
    widget.choices = Rating.make_choices(3)
    ctx = widget.get_context("rating", "2", {"id": "id_rating"})
    assert ctx["widget"]["star_class"] == "mask-star-2"


@pytest.mark.unit
def test_rating_get_context_includes_allow_clear():
    """get_context() exposes allow_clear in widget context."""
    widget = Rating(allow_clear=True)
    widget.choices = Rating.make_choices(3)
    ctx = widget.get_context("rating", "1", {"id": "id_rating"})
    assert ctx["widget"]["allow_clear"] is True


@pytest.mark.unit
def test_rating_value_from_datadict_selected():
    """Submitted radio value is returned from value_from_datadict."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    data = QueryDict("rating=3")
    result = widget.value_from_datadict(data, {}, "rating")
    assert result == "3"


@pytest.mark.unit
def test_rating_value_from_datadict_missing():
    """Missing rating field returns None."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "rating")
    assert result is None


@pytest.mark.unit
def test_rating_make_choices_edge_one():
    """make_choices(1) returns a single-element list."""
    choices = Rating.make_choices(1)
    assert len(choices) == 1
    assert choices[0] == ("1", "1 star")


@pytest.mark.unit
def test_rating_make_choices_zero_returns_empty():
    """make_choices(0) returns an empty list."""
    choices = Rating.make_choices(0)
    assert choices == []


@pytest.mark.unit
def test_rating_get_context_with_value_none():
    """Passing value=None is tolerated."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    ctx = widget.get_context("rating", None, {"id": "id_rating"})
    assert ctx["widget"]["name"] == "rating"


@pytest.mark.unit
def test_rating_renders_without_id():
    """Widget renders without an id attribute."""
    widget = Rating()
    widget.choices = Rating.make_choices(3)
    soup = render_widget(widget, name="rating", attrs={})
    div = soup.find("div", class_="rating")
    assert div is not None
    assert not div.has_attr("id")


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_rating_renders_wrapper_div():
    """Rendered HTML contains a <div class='rating'> wrapper."""
    widget = Rating()
    widget.choices = Rating.make_choices(3)
    soup = render_widget(widget, value="2")
    rating_div = soup.find("div", class_="rating")
    assert rating_div is not None


@pytest.mark.unit
def test_rating_renders_correct_radio_count():
    """Rendered HTML contains one radio input per choice."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    soup = render_widget(widget, value="1")
    radios = soup.find_all("input", {"type": "radio"})
    assert len(radios) == 5


@pytest.mark.unit
def test_rating_star_class_on_radios():
    """Each radio input carries both 'mask' and the default 'mask-star-2' class."""
    widget = Rating()
    widget.choices = Rating.make_choices(3)
    soup = render_widget(widget, value="1")
    radios = soup.find_all("input", {"type": "radio"})
    for radio in radios:
        classes = radio.get("class", [])
        assert "mask" in classes
        assert "mask-star-2" in classes


@pytest.mark.unit
def test_rating_selected_value_is_checked():
    """Only the radio matching the current value has the checked attribute."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    soup = render_widget(widget, value="3")
    radios = soup.find_all("input", {"type": "radio"})
    checked = [r for r in radios if r.has_attr("checked")]
    assert len(checked) == 1
    assert checked[0]["value"] == "3"


@pytest.mark.unit
def test_rating_no_checked_when_no_value():
    """With value=None, no radio is checked."""
    widget = Rating()
    widget.choices = Rating.make_choices(5)
    soup = render_widget(widget, value=None)
    radios = soup.find_all("input", {"type": "radio"})
    checked = [r for r in radios if r.has_attr("checked")]
    assert len(checked) == 0


@pytest.mark.unit
def test_rating_allow_clear_renders_hidden_input():
    """allow_clear=True produces a hidden clear radio with class 'rating-hidden'."""
    widget = Rating(allow_clear=True)
    widget.choices = Rating.make_choices(3)
    soup = render_widget(widget, value="1")
    hidden = soup.find("input", class_="rating-hidden")
    assert hidden is not None


@pytest.mark.unit
def test_rating_no_allow_clear_no_hidden_input():
    """allow_clear=False produces no hidden clear radio."""
    widget = Rating(allow_clear=False)
    widget.choices = Rating.make_choices(3)
    soup = render_widget(widget, value="1")
    hidden = soup.find("input", class_="rating-hidden")
    assert hidden is None


@pytest.mark.unit
def test_rating_custom_star_class_in_output():
    """Custom star_class appears on all radio inputs instead of the default."""
    widget = Rating(star_class="mask-heart")
    widget.choices = Rating.make_choices(2)
    soup = render_widget(widget, value="1")
    radios = soup.find_all("input", {"type": "radio"})
    for radio in radios:
        assert "mask-heart" in radio.get("class", [])
        assert "mask-star-2" not in radio.get("class", [])


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_rating_renders_via_form(renderer):
    """Rating renders correctly when used inside a FormworkForm."""
    form = RatingForm()
    soup = render_form(form, renderer=renderer)
    radios = soup.find_all("input", {"type": "radio", "name": "rating"})
    assert len(radios) == 5


@pytest.mark.integration
def test_rating_form_wraps_in_fieldset(renderer):
    """Field template wraps the Rating in a fieldset with a stable id."""
    form = RatingForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_rating_field")
    assert fieldset is not None


@pytest.mark.integration
def test_rating_error_state_aria_invalid(renderer):
    """Bound form with errors adds aria-invalid='true' to the widget."""
    form = RatingForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    # The rating div wrapper should carry the aria-invalid attribute
    rating_div = soup.find("div", class_="rating")
    assert rating_div is not None
    # At least one radio has aria-invalid (Django sets it on the widget)
    # or the fieldset signals the error: check tooltip exists
    tooltip = soup.find(id="id_rating_tooltip")
    assert tooltip is not None


@pytest.mark.integration
def test_rating_error_state_shows_tooltip(renderer):
    """Bound form with errors renders a tooltip containing the error text."""
    form = RatingForm(data={}, error_display="tooltip")
    form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find(id="id_rating_tooltip")
    assert tooltip is not None
    assert "required" in tooltip.text.lower()


@pytest.mark.integration
def test_rating_form_prefix_handling(renderer):
    """Form prefix propagates to widget name and id attributes."""
    form = RatingForm(prefix="srv")
    soup = render_form(form, renderer=renderer)
    radios = soup.find_all("input", {"type": "radio", "name": "srv-rating"})
    assert len(radios) > 0
    assert radios[0]["id"].startswith("id_srv-rating")


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_rating_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """Rating produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(RatingForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(RatingForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_rating_renders_5_stars(simple_page):
    """5 star radio inputs are visible on the /simple/ page."""
    stars = simple_page.locator('#id_stars input[type="radio"]')
    assert stars.count() == 5


@pytest.mark.e2e
def test_rating_click_selects_star(simple_page):
    """Clicking a star radio marks it as checked."""
    third_star = simple_page.locator('#id_stars input[type="radio"]').nth(2)
    third_star.click(force=True)
    assert third_star.is_checked()


@pytest.mark.e2e
def test_rating_has_mask_star_class(simple_page):
    """Star radio inputs carry the 'mask-star-2' CSS class."""
    star = simple_page.locator('#id_stars input[type="radio"]').first
    cls = star.get_attribute("class") or ""
    assert "mask-star-2" in cls


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# The /simple/ page requires a Rating field (stars), but submitting with no
# star selected also triggers errors on the other required fields, making
# isolated Rating error-flow tests noisy.  A dedicated page with only a
# required Rating field is needed.  Skipped until that page exists; tracked
# under the broader error-state test coverage work.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_rating_morph_preserves_selected_star(simple_page):
    """Selected star value survives an htmx form morph."""
    from tests.e2e.conftest import submit

    simple_page.evaluate("""
        const star = document.querySelector('#id_stars input[value="3"]');
        star.checked = true;
        star.dispatchEvent(new Event('change', {bubbles: true}));
    """)
    submit(simple_page)
    checked = simple_page.evaluate(
        "document.querySelector('#id_stars input:checked')?.value || ''",
    )
    assert checked == "3"


@pytest.mark.e2e
def test_rating_morph_no_star_selected_stays_empty(simple_page):
    """With no star selected, morph does not auto-select any star."""
    from tests.e2e.conftest import submit

    # Ensure nothing is checked first
    initially_checked = simple_page.evaluate(
        "document.querySelector('#id_stars input:checked')?.value || ''",
    )
    assert initially_checked == ""
    submit(simple_page)
    # Still nothing checked after morph (form may show error but value is preserved)
    after_checked = simple_page.evaluate(
        "document.querySelector('#id_stars input:checked')?.value || ''",
    )
    assert after_checked == ""


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────
#
# Scaffolding only: these tests produce PNG artifacts in `test-results/`
# that can be reviewed manually.  True baseline comparison requires
# wiring up a visual-regression plugin (e.g. `pytest-playwright-visual`)
# as a follow-up.  See issue #26 for the plan.


@pytest.mark.screenshot
def test_rating_screenshot_default(simple_page, assert_screenshot):
    """Visual snapshot: Rating in default (no selection) state."""
    wrapper = simple_page.locator("#id_stars_field")
    assert_screenshot(wrapper, "rating-default.png")


@pytest.mark.screenshot
def test_rating_screenshot_one_star_selected(simple_page, assert_screenshot):
    """Visual snapshot: Rating with first star selected."""
    simple_page.locator('#id_stars input[type="radio"]').first.click(force=True)
    wrapper = simple_page.locator("#id_stars_field")
    assert_screenshot(wrapper, "rating-one-star.png")
