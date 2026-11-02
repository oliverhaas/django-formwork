"""field.html error placement: auto / inline / tooltip, via rendered structure."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.utils.html import format_html

from django_formwork.forms import FormworkForm

ERROR_TEXT = "This field is required."
HELP_TEXT = "Your legal name."


def _make_form_cls(*, help_text: str, error_display: str) -> type[FormworkForm]:
    class _F(FormworkForm):
        name = forms.CharField(help_text=help_text)

        class Meta:
            pass

    _F.Meta.error_display = error_display
    return _F


def _render(*, help_text: str, error_display: str, bind_invalid: bool) -> BeautifulSoup:
    form_cls = _make_form_cls(help_text=help_text, error_display=error_display)
    data = {"name": ""} if bind_invalid else None
    form = form_cls(data)
    if bind_invalid:
        assert not form.is_valid()
    html = str(form["name"].as_field_group())
    return BeautifulSoup(html, "html.parser")


def _disclosure(soup: BeautifulSoup):
    return soup.select_one("details.formwork-disclosure")


def _line(soup: BeautifulSoup):
    el = soup.select_one(".formwork-disclosure-text")
    return el.get_text(strip=True) if el is not None else None


def test_auto_with_help_and_error_is_inline_disclosure() -> None:
    soup = _render(help_text=HELP_TEXT, error_display="auto", bind_invalid=True)
    assert soup.select_one(".tooltip-error") is None
    disc = _disclosure(soup)
    assert disc is not None
    line = soup.select_one(".formwork-disclosure-text")
    assert line is not None
    assert line.get("role") == "alert"
    assert ERROR_TEXT in line.get_text()
    assert HELP_TEXT in disc.get_text()


def test_auto_without_help_and_error_is_tooltip() -> None:
    soup = _render(help_text="", error_display="auto", bind_invalid=True)
    tooltip = soup.select_one(".tooltip.tooltip-error")
    assert tooltip is not None
    tooltip_content = tooltip.select_one(".tooltip-content")
    assert tooltip_content is not None
    assert ERROR_TEXT in tooltip_content.get_text()
    assert _disclosure(soup) is None


def test_tooltip_mode_with_help_shows_tooltip_and_help_row() -> None:
    soup = _render(help_text=HELP_TEXT, error_display="tooltip", bind_invalid=True)
    assert soup.select_one(".tooltip.tooltip-error") is not None
    assert _line(soup) == HELP_TEXT
    line = soup.select_one(".formwork-disclosure-text")
    assert line is not None
    assert line.get("role") != "alert"


def test_inline_mode_without_help_and_error_is_inline_disclosure() -> None:
    soup = _render(help_text="", error_display="inline", bind_invalid=True)
    assert soup.select_one(".tooltip-error") is None
    line = soup.select_one(".formwork-disclosure-text")
    assert line is not None
    assert line.get("role") == "alert"
    assert ERROR_TEXT in line.get_text()


def test_help_text_marked_safe_keeps_its_markup() -> None:
    help_text = format_html('<a href="{}">Register</a>', "https://example.test")

    soup = _render(help_text=help_text, error_display="auto", bind_invalid=False)

    anchor = soup.select_one(".formwork-disclosure-text a")
    assert anchor is not None
    assert anchor["href"] == "https://example.test"


def test_plain_help_text_with_angle_brackets_is_escaped() -> None:
    soup = _render(
        help_text="defaults to '<country_code>: <carrier_name>'",
        error_display="auto",
        bind_invalid=False,
    )

    line = soup.select_one(".formwork-disclosure-text")
    assert line is not None
    assert line.select_one("country_code") is None
    assert "<country_code>" in line.get_text()


@pytest.mark.parametrize("mode", ["auto", "inline", "tooltip"])
def test_no_error_with_help_is_plain_help_row(mode: str) -> None:
    soup = _render(help_text=HELP_TEXT, error_display=mode, bind_invalid=False)
    assert soup.select_one(".tooltip-error") is None
    assert _line(soup) == HELP_TEXT
    assert soup.select_one('[role="alert"]') is None
