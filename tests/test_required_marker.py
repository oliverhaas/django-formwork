"""field.html marks the fields a user must fill with a red asterisk, unless they are disabled."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.core.exceptions import ImproperlyConfigured

from django_formwork.forms import FormworkForm

CHOICES = [("a", "Apples"), ("b", "Bananas")]


class _Form(FormworkForm):
    name = forms.CharField()
    nickname = forms.CharField(required=False)
    agreed = forms.BooleanField(widget=forms.CheckboxInput)
    newsletter = forms.BooleanField(required=False, widget=forms.CheckboxInput)
    fruit = forms.MultipleChoiceField(choices=CHOICES, widget=forms.CheckboxSelectMultiple)
    extras = forms.MultipleChoiceField(choices=CHOICES, required=False, widget=forms.CheckboxSelectMultiple)
    locked = forms.CharField(disabled=True)
    street = forms.CharField(required=False)

    class Meta:
        mandatory = ("street",)


def _render(field: str) -> BeautifulSoup:
    return BeautifulSoup(str(_Form()[field].as_field_group()), "html.parser")


@pytest.mark.parametrize(
    ("field", "marked"),
    [
        ("name", True),
        ("nickname", False),
        ("agreed", True),
        ("newsletter", False),
        ("fruit", True),
        ("extras", False),
        ("locked", False),
        ("street", True),
    ],
)
def test_only_a_field_the_user_must_fill_carries_the_asterisk(field: str, marked: bool) -> None:  # noqa: FBT001
    marker = _render(field).select_one(".fieldset-legend .text-error")

    assert (marker is not None) == marked
    if marker is not None:
        assert marker.get_text() == "*"
        assert marker["aria-hidden"] == "true"


def test_a_mandatory_field_is_announced_as_required() -> None:
    assert _render("street").select_one("input[aria-required=true]") is not None


@pytest.mark.parametrize("names", ["street", ["stret"]])
def test_meta_mandatory_must_list_declared_fields(names: object) -> None:
    with pytest.raises(ImproperlyConfigured, match=r"Meta\.mandatory"):

        class _BadForm(FormworkForm):
            street = forms.CharField(required=False)

            class Meta:
                mandatory = names
