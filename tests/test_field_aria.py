"""aria wiring in field.html: every id Django puts in ``aria-describedby`` is rendered.

A ``<summary>`` trigger cannot be the target of ``<label for>``, so it names itself via ``aria-labelledby``.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import Select

CHOICES = [("a", "Apples"), ("b", "Bananas")]
HELP_TEXT = "Pick one."


class _Form(FormworkForm):
    name = forms.CharField(help_text=HELP_TEXT)
    fruit = forms.ChoiceField(choices=CHOICES, help_text=HELP_TEXT, widget=Select)

    class Meta:
        error_display = "inline"


def _render(field: str, *, bind_invalid: bool) -> BeautifulSoup:
    form = _Form({"name": "", "fruit": ""} if bind_invalid else None)
    if bind_invalid:
        assert not form.is_valid()
    return BeautifulSoup(str(form[field].as_field_group()), "html.parser")


def _ids(soup: BeautifulSoup) -> set[str]:
    return {str(el["id"]) for el in soup.select("[id]")}


@pytest.mark.parametrize("field", ["name", "fruit"])
@pytest.mark.parametrize("bind_invalid", [False, True])
def test_described_by_targets_exist(field: str, bind_invalid: bool) -> None:  # noqa: FBT001
    soup = _render(field, bind_invalid=bind_invalid)

    described = soup.select("[aria-describedby]")
    assert described
    for el in described:
        for target in str(el["aria-describedby"]).split():
            assert target in _ids(soup), target


def test_summary_names_itself_by_label_then_value() -> None:
    soup = _render("fruit", bind_invalid=False)

    summary = soup.select_one("summary")
    assert summary is not None
    label_id, self_id = str(summary["aria-labelledby"]).split()
    assert self_id == summary["id"]

    label = soup.select_one(f"label#{label_id}")
    assert label is not None
    assert not label.get("for")  # <summary> is not labelable


def test_labelable_control_gets_no_labelledby() -> None:
    soup = _render("name", bind_invalid=False)

    assert soup.select_one("input[aria-labelledby]") is None
    assert soup.select_one("label")["for"] == "id_name"
