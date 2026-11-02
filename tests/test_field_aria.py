"""aria wiring in field.html: every id Django puts in ``aria-describedby`` is rendered.

A ``<summary>`` trigger cannot be the target of ``<label for>``, so it names itself via ``aria-labelledby``.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from django import forms

from django_formwork.fields import DateRangeField
from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    CardCheckboxSelectMultiple,
    CardRadioSelect,
    CheckboxInput,
    CheckboxSelectMultiple,
    ComboBox,
    ComboBoxMultiple,
    DataList,
    DateInput,
    DatePicker,
    Display,
    FileDropzoneInput,
    ImageDropzoneInput,
    InputMask,
    OTPInput,
    PasswordInput,
    Range,
    Rating,
    SearchInput,
    Select,
    SelectMultiple,
    StepperNumberInput,
    SuffixNumberInput,
    Textarea,
    TextInput,
    ToggleInput,
    ValidatedTextarea,
)

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


class _EveryWidgetForm(FormworkForm):
    text = forms.CharField(widget=TextInput, help_text=HELP_TEXT)
    floating = forms.CharField(widget=TextInput(attrs={"placeholder": "Name"}, floating=True), help_text=HELP_TEXT)
    note = forms.CharField(widget=Textarea, help_text=HELP_TEXT)
    password = forms.CharField(widget=PasswordInput, help_text=HELP_TEXT)
    search = forms.CharField(widget=SearchInput, help_text=HELP_TEXT)
    otp = forms.CharField(widget=OTPInput, help_text=HELP_TEXT)
    zip_code = forms.CharField(widget=InputMask(mask="#####"), help_text=HELP_TEXT)
    browser = forms.CharField(widget=DataList(suggestions=["Firefox"]), help_text=HELP_TEXT)
    bio = forms.CharField(widget=ValidatedTextarea(validate_url="/validate/"), help_text=HELP_TEXT)
    food = forms.CharField(widget=ComboBox(suggestions=["Pizza"]), help_text=HELP_TEXT)
    foods = forms.CharField(widget=ComboBoxMultiple(suggestions=["Pizza"]), help_text=HELP_TEXT)
    day = forms.DateField(widget=DateInput, help_text=HELP_TEXT)
    due = forms.DateField(widget=DatePicker, help_text=HELP_TEXT)
    period = DateRangeField(help_text=HELP_TEXT)
    quantity = forms.IntegerField(widget=StepperNumberInput, help_text=HELP_TEXT)
    weight = forms.IntegerField(widget=SuffixNumberInput(suffix="kg"), help_text=HELP_TEXT)
    volume = forms.IntegerField(widget=Range, help_text=HELP_TEXT)
    stars = forms.TypedChoiceField(choices=Rating.make_choices(5), coerce=int, widget=Rating, help_text=HELP_TEXT)
    fruit = forms.ChoiceField(choices=CHOICES, widget=Select, help_text=HELP_TEXT)
    fruits = forms.MultipleChoiceField(choices=CHOICES, widget=SelectMultiple, help_text=HELP_TEXT)
    boxes = forms.MultipleChoiceField(choices=CHOICES, widget=CheckboxSelectMultiple(columns=2), help_text=HELP_TEXT)
    plan = forms.ChoiceField(choices=CHOICES, widget=CardRadioSelect, help_text=HELP_TEXT)
    extras = forms.MultipleChoiceField(choices=CHOICES, widget=CardCheckboxSelectMultiple, help_text=HELP_TEXT)
    agree = forms.BooleanField(widget=CheckboxInput(text="I agree"), help_text=HELP_TEXT)
    terms = forms.BooleanField(widget=CheckboxInput, help_text=HELP_TEXT)
    enabled = forms.BooleanField(widget=ToggleInput, help_text=HELP_TEXT)
    upload = forms.FileField(widget=FileDropzoneInput, help_text=HELP_TEXT)
    avatar = forms.ImageField(widget=ImageDropzoneInput, help_text=HELP_TEXT)
    logo = forms.ImageField(widget=ImageDropzoneInput(preview_url="/media/logo.png"), help_text=HELP_TEXT)
    owner = forms.CharField(widget=Display, disabled=True, required=False, initial="Ada", help_text=HELP_TEXT)


@pytest.mark.unit
@pytest.mark.parametrize("field", list(_EveryWidgetForm.base_fields))
@pytest.mark.parametrize("error_display", ["auto", "inline", "tooltip"])
@pytest.mark.parametrize("bind_invalid", [False, True])
def test_every_widget_wires_labels_and_descriptions_to_rendered_ids(
    field: str,
    error_display: str,
    bind_invalid: bool,  # noqa: FBT001
) -> None:
    form = _EveryWidgetForm({} if bind_invalid else None, error_display=error_display)
    if bind_invalid:
        assert field == "owner" or field in form.errors
    soup = BeautifulSoup(str(form[field].as_field_group()), "html.parser")
    ids = [str(el["id"]) for el in soup.select("[id]")]

    assert len(ids) == len(set(ids))
    assert soup.select_one("script") is None
    for el in soup.select("[aria-describedby], [aria-labelledby]"):
        for target in f"{el.get('aria-describedby', '')} {el.get('aria-labelledby', '')}".split():
            assert target in ids, target
    for label in soup.select("label[for]"):
        target = soup.find(id=label["for"])
        assert target is not None, label["for"]
        assert target.get("type") != "hidden"
