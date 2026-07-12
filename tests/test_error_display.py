"""Tests for ``_ErrorDisplayFormMixin`` (``Meta.error_display`` / kwarg resolution)."""

from __future__ import annotations

import pytest
from django import forms
from e2e.models import BasicFormData

from django_formwork.forms import FormworkForm, FormworkModelForm

pytestmark = pytest.mark.django_db


class PlainForm(FormworkForm):
    name = forms.CharField()


class MetaInlineForm(FormworkForm):
    name = forms.CharField()

    class Meta:
        error_display = "inline"


class PlainModelForm(FormworkModelForm):
    class Meta:
        model = BasicFormData
        fields = ["name", "email"]


class MetaInlineModelForm(FormworkModelForm):
    class Meta:
        model = BasicFormData
        fields = ["name", "email"]
        error_display = "inline"


class TestFormOnly:
    def test_default_is_tooltip(self):
        form = PlainForm()
        assert form.error_display == "tooltip"

    def test_kwarg_sets_inline(self):
        form = PlainForm(error_display="inline")
        assert form.error_display == "inline"

    def test_meta_default_sets_inline(self):
        form = MetaInlineForm()
        assert form.error_display == "inline"

    def test_kwarg_overrides_meta(self):
        form = MetaInlineForm(error_display="tooltip")
        assert form.error_display == "tooltip"


class TestModelForm:
    def test_default_is_tooltip(self):
        form = PlainModelForm()
        assert form.error_display == "tooltip"

    def test_kwarg_sets_inline(self):
        form = PlainModelForm(error_display="inline")
        assert form.error_display == "inline"

    def test_meta_default_sets_inline(self):
        form = MetaInlineModelForm()
        assert form.error_display == "inline"

    def test_kwarg_overrides_meta(self):
        form = MetaInlineModelForm(error_display="tooltip")
        assert form.error_display == "tooltip"
