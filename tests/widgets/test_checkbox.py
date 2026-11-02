"""Tests for the formwork CheckboxInput (own text beside the box)."""

from __future__ import annotations

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import CheckboxInput

from .conftest import render_form


class NewsletterForm(FormworkForm):
    """Form fixture with a texted checkbox and a plain one."""

    newsletter = forms.BooleanField(
        label="Newsletter",
        required=False,
        widget=CheckboxInput(text="Send me the monthly digest"),
    )
    terms = forms.BooleanField(label="I accept the terms", required=False, widget=CheckboxInput)


class RequiredTermsForm(FormworkForm):
    terms = forms.BooleanField(label="Terms", widget=CheckboxInput(text="I accept the terms"))


@pytest.mark.integration
def test_checkbox_text_sits_beside_box_under_field_label(renderer):
    """With text, the box and text share a label and the field label sits above."""
    soup = render_form(NewsletterForm(), renderer=renderer)
    fieldset = soup.find("fieldset", id="id_newsletter_field")
    wrapper = fieldset.find("label", class_="checkbox-single")
    assert wrapper.find("input", attrs={"type": "checkbox", "name": "newsletter"}) is not None
    assert wrapper.get_text(strip=True) == "Send me the monthly digest"
    legend = fieldset.find("label", class_="fieldset-legend")
    assert legend.get_text(strip=True) == "Newsletter"
    assert legend["for"] == "id_newsletter"


@pytest.mark.integration
def test_checkbox_without_text_puts_field_label_beside_box(renderer):
    """Without text, the input stays a direct child of the fieldset for the grid layout."""
    soup = render_form(NewsletterForm(), renderer=renderer)
    fieldset = soup.find("fieldset", id="id_terms_field")
    assert fieldset.find("label", class_="checkbox-single") is None
    assert fieldset.find("input", attrs={"name": "terms"}, recursive=False) is not None


@pytest.mark.integration
def test_checkbox_with_text_error_wraps_box_and_text_in_tooltip(renderer):
    """A tooltip error wraps the texted box, so the error points at the control."""
    form = RequiredTermsForm(data={}, error_display="tooltip")
    assert not form.is_valid()
    soup = render_form(form, renderer=renderer)
    tooltip = soup.find("div", class_="tooltip")
    assert tooltip.find("label", class_="checkbox-single") is not None
    assert "required" in tooltip.find(id="id_terms_error").get_text().lower()


@pytest.mark.integration
def test_checkbox_text_is_not_a_placeholder(renderer):
    """HTML allows no placeholder on a checkbox, so the text renders only as the visible span."""
    soup = render_form(NewsletterForm(), renderer=renderer)
    assert not soup.find("input", attrs={"name": "newsletter"}).has_attr("placeholder")
