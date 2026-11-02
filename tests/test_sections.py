"""Tests for ``section_forms``: the server side of ``data-section-form`` pages."""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import BadRequest

from django_formwork import section_forms
from django_formwork.forms import FormworkForm
from django_formwork.sections import SECTION_INPUT_NAME


class GeneralForm(FormworkForm):
    name = forms.CharField()


class StockForm(FormworkForm):
    count = forms.IntegerField()


SECTIONS = {"general": GeneralForm, "stock": StockForm}


def test_get_builds_every_section_unbound(rf):
    built = section_forms(rf.get("/"), SECTIONS, initial={"name": "Lamp"})
    assert not any(form.is_bound for form in built.values())
    assert built["general"]["name"].value() == "Lamp"


def test_post_binds_only_the_named_section(rf):
    request = rf.post("/", {SECTION_INPUT_NAME: "stock", "count": "3"})
    built = section_forms(request, SECTIONS)
    assert built["general"].is_bound is False
    assert built["stock"].is_valid() is True
    assert built["stock"].cleaned_data == {"count": 3}


@pytest.mark.parametrize("data", [{}, {SECTION_INPUT_NAME: "missing"}])
def test_post_without_a_known_section_is_a_bad_request(rf, data):
    with pytest.raises(BadRequest):
        section_forms(rf.post("/", data), SECTIONS)
