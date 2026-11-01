from __future__ import annotations

import pytest
from django import forms
from django.utils.html import format_html

from django_formwork.forms import FormworkForm
from django_formwork.widgets import ChoiceLabel, Display

from .conftest import render_form, render_widget


class DisplayForm(FormworkForm):
    owner = forms.CharField(required=False, disabled=True, widget=Display, help_text="Set by the admin.")


@pytest.mark.unit
@pytest.mark.parametrize(("value", "items"), [("Ada", ["Ada"]), (["Ada", "Bob"], ["Ada", "Bob"]), (42, ["42"])])
def test_display_renders_each_value_as_an_item(value, items):
    """A string, a number or a list each render one item per value."""
    soup = render_widget(Display(), name="owner", value=value)
    assert [span.get_text() for span in soup.select("div[role=group] > span")] == items


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "", []])
def test_display_renders_a_dash_when_empty(value):
    """An empty value shows a dash, so the box does not look unfilled."""
    soup = render_widget(Display(), name="owner", value=value)
    assert soup.select_one("div[role=group]").get_text(strip=True) == "—"


@pytest.mark.unit
def test_display_posts_nothing():
    """A read-only value renders no form control."""
    soup = render_widget(Display(), name="owner", value="Ada", attrs={"id": "id_owner"})
    assert soup.select("input, select, textarea, button") == []
    assert soup.select_one("#id_owner")["role"] == "group"


@pytest.mark.unit
def test_display_badges_take_the_label_color():
    """With ``badges`` each item is a soft badge in its ChoiceLabel colour."""
    items = [ChoiceLabel("Open", color="success"), ChoiceLabel("Late", color="error")]
    soup = render_widget(Display(badges=True), name="state", value=items)
    badges = soup.select("span.badge")
    assert [b["class"][-1] for b in badges] == ["badge-success", "badge-error"]
    assert all("badge-soft" in b["class"] for b in badges)


@pytest.mark.unit
def test_display_escapes_text_and_keeps_label_html():
    """Plain labels are escaped; ``label_html`` is trusted markup."""
    hostile = "<script>alert(1)</script>"
    html_label = ChoiceLabel("Ada", label_html=format_html("<b>{}</b>", "Ada"))
    soup = render_widget(Display(), name="owner", value=[hostile, html_label])
    assert soup.select_one("script") is None
    assert hostile in soup.get_text()
    assert soup.select_one("b").get_text() == "Ada"


@pytest.mark.integration
def test_display_is_named_by_the_field_label(renderer):
    """The label has no control to point at, so the group names itself by the label id."""
    soup = render_form(DisplayForm(initial={"owner": "Ada"}), renderer=renderer)
    label = soup.find("label", id="id_owner_label")
    assert not label.has_attr("for")
    group = soup.select_one("#id_owner")
    assert group["aria-labelledby"].split()[0] == "id_owner_label"
    assert all(soup.find(id=i) is not None for i in group["aria-describedby"].split())
