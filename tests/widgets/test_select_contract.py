"""Rendering contract shared by the select family: toggle text, client rows, labels."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from django import forms
from django.contrib.auth.models import User
from django.test import Client
from django.utils.safestring import mark_safe

import django_formwork
from django_formwork import ChoiceLabel
from django_formwork.forms import FormworkForm
from django_formwork.widgets import ComboBox, ComboBoxMultiple, Select, SelectMultiple

FRUITS = [("a", "Apples"), ("b", "Bananas"), ("c", "Cherries"), ("d", "Dates")]
ICON_FRUITS = [("a", ChoiceLabel("Apples", icon=mark_safe('<i class="icon icon-apple"></i>'))), *FRUITS[1:]]
MANY = [(str(i), f"Option {i}") for i in range(200)]
SELECTED = "150"
FIRST_PAGE = [str(i) for i in range(20)]
WIDGET_TEMPLATES = Path(django_formwork.__file__).parent / "templates" / "formwork" / "widgets"


def _users(request):
    return User.objects.order_by("pk")


class _ToggleForm(FormworkForm):
    """One field the browser filters, one the search endpoint feeds."""

    client = forms.MultipleChoiceField(choices=ICON_FRUITS, widget=SelectMultiple)
    served = forms.MultipleChoiceField(
        choices=[*ICON_FRUITS, *MANY],
        widget=SelectMultiple(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _ClientForm(FormworkForm):
    """No endpoint: the browser filters the rows, so all of them must stay in the DOM."""

    one = forms.ChoiceField(choices=MANY, widget=Select)
    many = forms.MultipleChoiceField(choices=MANY, widget=SelectMultiple)


class _SearchForm(FormworkForm):
    """Both select widgets with a server-side endpoint, registered as a real form does."""

    one = forms.ChoiceField(
        choices=[("", "Not set"), *MANY],
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None, allow_clear=True),
    )
    many = forms.MultipleChoiceField(
        choices=MANY,
        widget=SelectMultiple(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _ModelSearchForm(FormworkForm):
    one = forms.ModelChoiceField(
        queryset=User.objects.order_by("pk"),
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )
    many = forms.ModelMultipleChoiceField(
        queryset=User.objects.order_by("pk"),
        widget=SelectMultiple(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _NoBlankModelForm(FormworkForm):
    listed = forms.ModelChoiceField(queryset=User.objects.order_by("pk"), empty_label=None, widget=Select)
    searched = forms.ModelChoiceField(
        queryset=User.objects.order_by("pk"),
        empty_label=None,
        widget=Select(search_fields=["email"], search_queryset=_users, search_decorator=None),
    )


class _FamilyForm(FormworkForm):
    select = forms.ChoiceField(choices=FRUITS, widget=Select)
    select_multiple = forms.MultipleChoiceField(choices=FRUITS, widget=SelectMultiple)
    combo_box = forms.CharField(widget=ComboBox(suggestions=["Apples", "Bananas"]))
    combo_box_multiple = forms.CharField(widget=ComboBoxMultiple(suggestions=["Apples", "Bananas"]))
    floating = forms.ChoiceField(choices=FRUITS, widget=Select(attrs={"placeholder": "Fruit"}, floating=True))


def _toggle_html(field: str, selected: list[str]) -> str:
    html = str(_ToggleForm(initial={field: selected})[field])
    span = BeautifulSoup(html, "html.parser").select_one("summary [x-html]")
    assert span is not None
    return span.decode_contents().strip()


@pytest.mark.unit
@pytest.mark.parametrize("field", ["client", "served"])
def test_toggle_names_the_selected_options_with_their_icons(field: str) -> None:
    assert _toggle_html(field, ["a", "b"]) == '<i class="icon icon-apple"></i> Apples, Bananas'


@pytest.mark.unit
@pytest.mark.parametrize("field", ["client", "served"])
def test_toggle_counts_selections_past_the_summary_threshold(field: str) -> None:
    assert _toggle_html(field, ["a", "b", "c", "d"]) == "4 selected"


def _values(form: forms.Form, field: str) -> list[str]:
    listbox = BeautifulSoup(str(form[field]), "html.parser").select_one("ul[role=listbox]")
    assert listbox is not None
    rows = (row.select_one("[data-value]") for row in listbox.select("li"))
    return [str(holder["data-value"]) for holder in rows if holder is not None]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "initial", "expected"),
    [
        ("one", None, ["", *FIRST_PAGE]),
        ("one", SELECTED, ["", *FIRST_PAGE, SELECTED]),
        ("many", None, FIRST_PAGE),
        ("many", [SELECTED], [*FIRST_PAGE, SELECTED]),
    ],
)
def test_server_search_renders_one_page_and_leaves_filtering_to_the_endpoint(
    field: str, initial: Any, expected: list[str]
) -> None:
    form = _SearchForm(initial={field: initial})

    assert _values(form, field) == expected
    search = BeautifulSoup(str(form[field]), "html.parser").select_one("input[type=search]")
    assert search is not None
    assert search["hx-trigger"] == "input changed delay:300ms"


@pytest.mark.django_db
def test_a_model_search_renders_one_page_and_a_selection_past_it() -> None:
    User.objects.bulk_create(User(username=f"user{i}", email=f"user{i}@example.com") for i in range(22))
    ids = [str(pk) for pk in User.objects.order_by("pk").values_list("pk", flat=True)]

    form = _ModelSearchForm(initial={"one": ids[-1]})

    assert _values(form, "one") == [*ids[:20], ids[-1]]
    more = BeautifulSoup(str(form["one"]), "html.parser").select_one('[role="status"] button[hx-get]')
    assert more is not None
    response = Client().get(str(more["hx-get"]))
    soup = BeautifulSoup(response.content.decode(), "html.parser")
    assert [str(el["data-value"]) for el in soup.select("[data-value]")] == ids[20:-1]


@pytest.mark.django_db
def test_a_bound_value_the_key_cannot_hold_renders_no_selection() -> None:
    User.objects.bulk_create(User(username=f"user{i}", email=f"user{i}@example.com") for i in range(22))

    form = _ModelSearchForm(data={"one": "not-a-pk"})

    assert len(_values(form, "one")) == 20


@pytest.mark.django_db
def test_a_malformed_value_keeps_the_valid_selections_past_the_page() -> None:
    User.objects.bulk_create(User(username=f"user{i}", email=f"user{i}@example.com") for i in range(22))
    last = str(User.objects.order_by("pk").values_list("pk", flat=True).last())

    form = _ModelSearchForm(data={"many": ["not-a-pk", last]})

    assert _values(form, "many")[-1] == last


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["listed", "searched"])
def test_a_model_select_without_a_blank_choice_queries_once(field: str, django_assert_num_queries) -> None:
    User.objects.bulk_create(User(username=f"user{i}", email=f"user{i}@example.com") for i in range(22))
    form = _NoBlankModelForm()

    with django_assert_num_queries(1):
        str(form[field])


@pytest.mark.unit
@pytest.mark.parametrize("field", ["one", "many"])
def test_client_side_filtering_keeps_every_option(field: str) -> None:
    soup = BeautifulSoup(str(_ClientForm()[field]), "html.parser")
    listbox = soup.select_one("ul[role=listbox]")
    assert listbox is not None
    assert len(listbox.select("li")) == len(MANY)


@pytest.mark.unit
def test_widget_templates_carry_no_script() -> None:
    """Alpine components live in static modules; a template script repeats on every swap."""
    templates = sorted(WIDGET_TEMPLATES.rglob("*.html"))
    assert templates
    for template in templates:
        assert "<script" not in template.read_text(), template.name


_BINDING = re.compile(r'\s((?:x-|:|@)[\w:.-]+|hx-on[\w:.-]*)="([^"]*)"')
_PATH = r"[A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*|\[\d+\])*"
_ARG = rf"(?:{_PATH}|-?\d+|'[^']*')"
_CALL_OR_PROPERTY = re.compile(rf"!?{_PATH}(?:\((?:{_ARG}(?:, {_ARG})*)?\))?")


@pytest.mark.unit
def test_widget_template_bindings_hold_one_call_or_property() -> None:
    """Logic lives in the Alpine components: a binding names a property or makes one call (D4)."""
    for template in sorted(WIDGET_TEMPLATES.rglob("*.html")):
        source = re.sub(r"{%.*?%}|{{.*?}}", "x", template.read_text())
        for name, value in _BINDING.findall(source):
            if name != "x-for" and value:
                assert _CALL_OR_PROPERTY.fullmatch(value), f"{template.name}: {name}={value}"


@pytest.mark.unit
@pytest.mark.parametrize("field", ["select", "select_multiple", "combo_box", "combo_box_multiple", "floating"])
def test_no_label_targets_a_hidden_input(field: str) -> None:
    soup = BeautifulSoup(str(_FamilyForm()[field].as_field_group()), "html.parser")
    for label in soup.select("label[for]"):
        target = soup.find(id=label["for"])
        assert target is not None, label["for"]
        assert target.get("type") != "hidden", label["for"]
