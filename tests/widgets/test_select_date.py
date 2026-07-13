"""Django's built-in SelectDateWidget under formwork styling."""

from __future__ import annotations

import pytest
from django import forms
from django.http import QueryDict

from django_formwork.forms import FormworkForm

from .conftest import assert_html_equivalent, render_form, render_widget, submit


class SelectDateForm(FormworkForm):
    """Form fixture for SelectDateWidget integration tests."""

    birthday = forms.DateField(
        widget=forms.SelectDateWidget(years=range(2020, 2031)),
        required=False,
    )


# ─── Level 1: Widget object (pure Python) ────────────────────────────────


@pytest.mark.unit
def test_select_date_instantiation():
    """SelectDateWidget stores the years range."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    assert list(widget.years) == list(range(2020, 2031))


@pytest.mark.unit
def test_select_date_get_context():
    """get_context() returns three subwidgets for month, day, and year."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    ctx = widget.get_context("birthday", None, {"id": "id_birthday"})
    subwidgets = ctx["widget"]["subwidgets"]
    assert len(subwidgets) == 3
    names = [sw["name"] for sw in subwidgets]
    assert "birthday_month" in names
    assert "birthday_day" in names
    assert "birthday_year" in names


@pytest.mark.unit
def test_select_date_value_from_datadict():
    """Submitted month/day/year values are combined into a date string."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    data = QueryDict("birthday_month=3&birthday_day=14&birthday_year=2025")
    result = widget.value_from_datadict(data, {}, "birthday")
    assert result == "2025-03-14"


@pytest.mark.unit
def test_select_date_value_from_datadict_empty():
    """Empty QueryDict returns None when all selects are unset."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    data = QueryDict("")
    result = widget.value_from_datadict(data, {}, "birthday")
    assert result is None


# ─── Level 2: Widget rendering (HTML output) ─────────────────────────────


@pytest.mark.unit
def test_select_date_renders_three_selects():
    """render() produces exactly three <select> elements."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    soup = render_widget(widget, name="birthday")
    selects = soup.find_all("select")
    assert len(selects) == 3


@pytest.mark.unit
def test_select_date_renders_month_options():
    """Month select has 13 options: one empty placeholder plus 12 months."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    soup = render_widget(widget, name="birthday")
    month_select = soup.find("select", attrs={"name": "birthday_month"})
    assert month_select is not None
    assert len(month_select.find_all("option")) == 13


@pytest.mark.unit
def test_select_date_renders_day_options():
    """Day select has 32 options: one empty placeholder plus days 1 to 31."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    soup = render_widget(widget, name="birthday")
    day_select = soup.find("select", attrs={"name": "birthday_day"})
    assert day_select is not None
    assert len(day_select.find_all("option")) == 32


@pytest.mark.unit
def test_select_date_renders_year_options():
    """Year select has 12 options: one empty placeholder plus years 2020 to 2030."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    soup = render_widget(widget, name="birthday")
    year_select = soup.find("select", attrs={"name": "birthday_year"})
    assert year_select is not None
    assert len(year_select.find_all("option")) == 12


@pytest.mark.unit
def test_select_date_renders_name_suffixes():
    """The three selects carry _month, _day, and _year name suffixes."""
    widget = forms.SelectDateWidget(years=range(2020, 2031))
    soup = render_widget(widget, name="birthday")
    assert soup.find("select", attrs={"name": "birthday_month"}) is not None
    assert soup.find("select", attrs={"name": "birthday_day"}) is not None
    assert soup.find("select", attrs={"name": "birthday_year"}) is not None


# ─── Level 3: Form integration ───────────────────────────────────────────


@pytest.mark.integration
def test_select_date_renders_via_form(renderer):
    """Field renders three selects with _month/_day/_year name suffixes."""
    form = SelectDateForm()
    soup = render_form(form, renderer=renderer)
    assert soup.find("select", attrs={"name": "birthday_month"}) is not None
    assert soup.find("select", attrs={"name": "birthday_day"}) is not None
    assert soup.find("select", attrs={"name": "birthday_year"}) is not None


@pytest.mark.integration
def test_select_date_form_wraps_in_fieldset(renderer):
    """Field template wraps the SelectDateWidget in a fieldset with a stable id."""
    form = SelectDateForm()
    soup = render_form(form, renderer=renderer)
    fieldset = soup.find("fieldset", id="id_birthday_field")
    assert fieldset is not None


@pytest.mark.integration
def test_select_date_form_prefix(renderer):
    """Form prefix propagates to the select name suffixes."""
    form = SelectDateForm(prefix="reg")
    soup = render_form(form, renderer=renderer)
    assert soup.find("select", attrs={"name": "reg-birthday_month"}) is not None
    assert soup.find("select", attrs={"name": "reg-birthday_day"}) is not None
    assert soup.find("select", attrs={"name": "reg-birthday_year"}) is not None


# ─── Level 4: Jinja2 / DTL parity ────────────────────────────────────────


@pytest.mark.integration
def test_select_date_jinja2_dtl_parity(dtl_renderer, jinja2_renderer):
    """SelectDateWidget produces equivalent HTML when rendered via DTL and Jinja2."""
    soup_dtl = render_form(SelectDateForm(), renderer=dtl_renderer)
    soup_jinja2 = render_form(SelectDateForm(), renderer=jinja2_renderer)
    assert_html_equivalent(soup_dtl, soup_jinja2)


# ─── Level 5: E2e basic interaction ──────────────────────────────────────


@pytest.mark.e2e
def test_select_date_renders_on_page(builtin_page):
    """All three date selects are visible on the /builtin/ page."""
    from playwright.sync_api import expect

    expect(builtin_page.locator('select[name="birthday_month"]')).to_be_visible()
    expect(builtin_page.locator('select[name="birthday_day"]')).to_be_visible()
    expect(builtin_page.locator('select[name="birthday_year"]')).to_be_visible()


@pytest.mark.e2e
def test_select_date_month_has_options(builtin_page):
    """Month select has 13 options (empty placeholder + 12 months)."""
    options = builtin_page.locator('select[name="birthday_month"] option').all()
    assert len(options) == 13


@pytest.mark.e2e
def test_select_date_select_date(builtin_page):
    """User can select a month, day, and year."""
    builtin_page.select_option('select[name="birthday_month"]', value="3")
    builtin_page.select_option('select[name="birthday_day"]', value="14")
    builtin_page.select_option('select[name="birthday_year"]', value="2025")
    assert builtin_page.locator('select[name="birthday_month"]').input_value() == "3"
    assert builtin_page.locator('select[name="birthday_day"]').input_value() == "14"
    assert builtin_page.locator('select[name="birthday_year"]').input_value() == "2025"


@pytest.mark.e2e
def test_select_date_three_column_layout(builtin_page):
    """The three date selects are arranged side-by-side (same vertical row)."""
    month_box = builtin_page.locator('select[name="birthday_month"]').bounding_box()
    day_box = builtin_page.locator('select[name="birthday_day"]').bounding_box()
    year_box = builtin_page.locator('select[name="birthday_year"]').bounding_box()
    # All selects should have approximately the same top position (same row).
    assert abs(month_box["y"] - day_box["y"]) < 10
    assert abs(month_box["y"] - year_box["y"]) < 10
    # Each select should be to the right of the previous one.
    assert day_box["x"] > month_box["x"]
    assert year_box["x"] > day_box["x"]


# ─── Level 6: E2e error flow ─────────────────────────────────────────────
#
# Needs a page with a required DateField; birthday on /builtin/ is optional.


# ─── Level 7: E2e morph resilience ───────────────────────────────────────


@pytest.mark.e2e
def test_select_date_morph_preserves_date(builtin_page):
    """Selected month/day/year survive an htmx form morph."""
    builtin_page.select_option('select[name="birthday_month"]', value="3")
    builtin_page.select_option('select[name="birthday_day"]', value="14")
    builtin_page.select_option('select[name="birthday_year"]', value="2025")
    submit(builtin_page)
    assert builtin_page.locator('select[name="birthday_month"]').input_value() == "3"
    assert builtin_page.locator('select[name="birthday_day"]').input_value() == "14"
    assert builtin_page.locator('select[name="birthday_year"]').input_value() == "2025"


# ─── Level 8: Screenshot (visual regression) ─────────────────────────────


@pytest.mark.screenshot
def test_select_date_screenshot_default(builtin_page, assert_screenshot):
    """Visual snapshot: SelectDateWidget in default (empty) state."""
    wrapper = builtin_page.locator("#id_birthday_field")
    assert_screenshot(wrapper, "select-date-default.png")


@pytest.mark.screenshot
def test_select_date_screenshot_filled(builtin_page, assert_screenshot):
    """Visual snapshot: SelectDateWidget with a date selected."""
    builtin_page.select_option('select[name="birthday_month"]', value="3")
    builtin_page.select_option('select[name="birthday_day"]', value="14")
    builtin_page.select_option('select[name="birthday_year"]', value="2025")
    wrapper = builtin_page.locator("#id_birthday_field")
    assert_screenshot(wrapper, "select-date-filled.png")
