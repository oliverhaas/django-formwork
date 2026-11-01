"""field.html badges the fields a user can leave empty, not demanded or disabled ones.

An unticked single checkbox is an answer, so it carries no badge.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms

from django_formwork.forms import FormworkForm

BADGE = "span.badge"
CHOICES = [("a", "Apples"), ("b", "Bananas")]


class _Form(FormworkForm):
    name = forms.CharField()
    nickname = forms.CharField(required=False)
    agreed = forms.BooleanField(widget=forms.CheckboxInput)
    newsletter = forms.BooleanField(required=False, widget=forms.CheckboxInput)
    fruit = forms.MultipleChoiceField(choices=CHOICES, widget=forms.CheckboxSelectMultiple)
    extras = forms.MultipleChoiceField(choices=CHOICES, required=False, widget=forms.CheckboxSelectMultiple)
    readonly = forms.CharField(required=False, disabled=True)
    street = forms.CharField(required=False)

    class Meta:
        mandatory = ("street",)


def _render(field: str) -> BeautifulSoup:
    return BeautifulSoup(str(_Form()[field].as_field_group()), "html.parser")


@pytest.mark.parametrize(
    ("field", "badged"),
    [
        ("name", False),
        ("nickname", True),
        ("agreed", False),
        ("newsletter", False),
        ("fruit", False),
        ("extras", True),
        ("readonly", False),
        ("street", False),
    ],
)
def test_only_the_optional_field_carries_the_badge(field: str, badged: bool) -> None:  # noqa: FBT001
    badge = _render(field).select_one(BADGE)

    assert (badge is not None) == badged
    if badge is not None:
        assert badge.get_text(strip=True) == "optional"


def test_a_mandatory_field_is_announced_as_required() -> None:
    assert _render("street").select_one("input[aria-required=true]") is not None
