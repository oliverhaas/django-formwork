"""``error_display`` resolution on FormworkForm and FormworkModelForm."""

from __future__ import annotations

import pytest
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured

from django_formwork.forms import FormworkForm, FormworkModelForm


class _PlainForm(FormworkForm):
    name = forms.CharField()


class _MetaForm(FormworkForm):
    name = forms.CharField()

    class Meta:
        error_display = "tooltip"


class _PlainModelForm(FormworkModelForm[User]):
    class Meta:
        model = User
        fields = ["username"]


class _MetaModelForm(FormworkModelForm[User]):
    class Meta:
        model = User
        fields = ["username"]
        error_display = "tooltip"


def test_default_is_auto() -> None:
    assert _PlainForm().error_display == "auto"
    assert _PlainModelForm().error_display == "auto"


def test_meta_sets_error_display() -> None:
    assert _MetaForm().error_display == "tooltip"
    assert _MetaModelForm().error_display == "tooltip"


def test_kwarg_overrides_meta() -> None:
    assert _MetaForm(error_display="inline").error_display == "inline"
    assert _PlainForm(error_display="tooltip").error_display == "tooltip"


@pytest.mark.parametrize("bad", ["popover", "", "Inline", "none"])
def test_invalid_value_raises(bad: str) -> None:
    with pytest.raises(ImproperlyConfigured):
        _PlainForm(error_display=bad)


def test_invalid_meta_value_fails_at_class_creation() -> None:
    with pytest.raises(ImproperlyConfigured, match=r"Meta\.error_display"):

        class _BadMetaForm(FormworkForm):
            class Meta:
                error_display = "popover"
