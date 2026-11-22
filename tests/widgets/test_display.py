from __future__ import annotations

import pytest
from admin_app.models import Category, Item, Tag
from bs4 import BeautifulSoup
from django import forms
from django.db.models import Count
from django.utils.html import format_html

from django_formwork import DisplayField
from django_formwork.forms import FormworkForm, FormworkModelForm
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


def item_form(name, field, fields=("name",)):
    meta = type("Meta", (), {"model": Item, "fields": list(fields)})
    return type("ItemForm", (FormworkModelForm,), {name: field, "Meta": meta})


def shown_items(form, name):
    soup = BeautifulSoup(form[name].as_field_group(), "html.parser")
    return [span.get_text() for span in soup.select("div[role=group] > span")]


@pytest.fixture
def item():
    kitchen = Category.objects.create(name="Kitchen", slug="kitchen")
    kettle = Item.objects.create(name="Kettle", category=kitchen, status=Item.Status.ACTIVE, quantity=3)
    kettle.tags.add(Tag.objects.create(name="new"), Tag.objects.create(name="sale"))
    return Item.objects.annotate(tag_count=Count("tags")).get(pk=kettle.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "field", "items"),
    [
        ("status", DisplayField(), ["Active"]),
        ("tags", DisplayField(), ["new", "sale"]),
        ("tag_count", DisplayField(), ["2"]),
        ("title", DisplayField(source="__str__"), ["Kettle"]),
        ("double", DisplayField(source=lambda item: item.quantity * 2), ["6"]),
    ],
    ids=["choice-label", "relation", "annotation", "method", "function"],
)
def test_display_field_shows_a_value_of_the_instance(item, name, field, items):
    assert shown_items(item_form(name, field)(instance=item), name) == items


@pytest.mark.django_db
def test_display_field_shows_no_related_rows_on_an_unsaved_instance():
    assert shown_items(item_form("tags", DisplayField())(), "tags") == []


@pytest.mark.unit
def test_display_field_of_a_form_without_an_instance_shows_its_initial_value():
    form_class = type("NoteForm", (FormworkForm,), {"author": DisplayField()})
    assert shown_items(form_class(initial={"author": "Ada"}), "author") == ["Ada"]


@pytest.mark.unit
@pytest.mark.parametrize("validate_dirty_only", [False, True])
def test_display_field_stays_out_of_cleaning_and_never_reads_its_value(validate_dirty_only):
    """A post reads no display value: an annotation the page adds later is not there yet."""
    reads = []
    form_class = type(
        "NoteForm",
        (FormworkForm,),
        {"text": forms.CharField(), "author": DisplayField(initial=lambda: reads.append(1) or "Ada")},
    )
    form = form_class(data={"text": "Hi", "author": "Bob"}, validate_dirty_only=validate_dirty_only)

    assert form.is_valid()
    assert form.changed_data == ["text"]
    assert form.cleaned_data == {"text": "Hi"}
    assert reads == []


@pytest.mark.django_db
def test_display_field_named_after_a_model_field_leaves_that_field_alone_on_save(item):
    data = {"name": "Pot", "status": Item.Status.ARCHIVED}
    form = item_form("status", DisplayField(), fields=("name", "status"))(data=data, instance=item)

    form.save()

    item.refresh_from_db()
    assert (item.name, item.status) == ("Pot", Item.Status.ACTIVE)


@pytest.mark.unit
def test_display_with_max_lines_runs_its_items_in_a_body_cut_to_that_many_lines():
    soup = render_widget(Display(max_lines=2), name="owner", value=["Ada", "Bob"])
    body = soup.select_one("div[role=group] > .formwork-clamp > .formwork-clamp-body")
    assert "line-clamp-2" in body["class"]
    assert [span.get_text() for span in body.select(":scope > span")] == ["Ada", "Bob"]
    assert soup.select_one(".formwork-clamp > details > summary") is not None


@pytest.mark.unit
def test_display_field_with_max_lines_cuts_its_value_in_the_box_and_in_a_table():
    form = type("NoteForm", (FormworkForm,), {"author": DisplayField(max_lines=3)})(initial={"author": "Ada"})
    box = BeautifulSoup(form["author"].as_field_group(), "html.parser")
    cell = BeautifulSoup(form["author"].display_value, "html.parser")
    assert "line-clamp-3" in box.select_one(".formwork-clamp-body")["class"]
    assert "line-clamp-3" in cell.select_one(".formwork-clamp-body")["class"]
    assert cell.get_text() == "Ada"


@pytest.mark.unit
@pytest.mark.parametrize("max_lines", [0, 11])
@pytest.mark.parametrize("make", [Display, DisplayField], ids=["widget", "field"])
def test_max_lines_outside_the_clamped_counts_raises(make, max_lines):
    with pytest.raises(ValueError, match="max_lines"):
        make(max_lines=max_lines)
