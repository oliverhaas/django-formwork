"""Translation coverage: every string formwork shows goes through gettext, and makemessages extracts it."""

from __future__ import annotations

import json
import re
import shutil
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import pytest
from django import forms
from django.utils import translation
from django.utils.dates import WEEKDAYS_ABBR

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

from .conftest import PACKAGE, extract_messages

if TYPE_CHECKING:
    from pathlib import Path

TEMPLATES = sorted((PACKAGE / "templates").rglob("*.html"))

_LOAD_I18N = re.compile(r"\{% load [^%]*\bi18n\b[^%]*%\}")
_TRANSLATED_BLOCK = re.compile(r"\{%\s*(blocktranslate|blocktrans|comment)\b.*?%\}.*?\{%\s*end\1\s*%\}", re.DOTALL)
_TEMPLATE_TAG = re.compile(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", re.DOTALL)
_PSEUDO = re.compile(r"⟦[^⟧]*⟧")
_WORD = re.compile(r"[A-Za-z]{2,}")
_JS_STRING = re.compile(r"'([^']*)'|\"([^\"]*)\"|`([^`]*)`")
_TEXT_ATTRS = {
    "alt",
    "aria-label",
    "aria-placeholder",
    "aria-roledescription",
    "aria-valuetext",
    "hx-confirm",
    "hx-prompt",
    "label",
    "placeholder",
    "title",
}
_TEXT_EXPRESSIONS = {"x-text", "x-html", ":alt", ":aria-label", ":placeholder", ":title"}


def _json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [text for item in value for text in _json_strings(item)]
    return []


def _data_texts(value: str) -> list[str]:
    """The strings a data attribute holds; JSON keys are names, not text."""
    try:
        return _json_strings(json.loads(value))
    except ValueError:
        return [value]


class _VisibleText(HTMLParser):
    """Collects what a page shows: text, text attributes, and string literals in text bindings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.texts: list[str] = []
        self._raw_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._raw_depth += 1
        for name, value in attrs:
            if not value:
                continue
            if name in _TEXT_ATTRS:
                self.texts.append(value)
            elif name.startswith("data-"):
                self.texts.extend(_data_texts(value))
            elif name in _TEXT_EXPRESSIONS:
                self.texts.extend(next(g for g in m.groups() if g is not None) for m in _JS_STRING.finditer(value))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._raw_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._raw_depth:
            self.texts.append(data)


def _english(html: str, allowed: frozenset[str] = frozenset()) -> list[str]:
    """The words ``html`` shows that are not ``allowed`` and neither a template tag nor a pseudo-translation."""
    parser = _VisibleText()
    parser.feed(_PSEUDO.sub("", _TEMPLATE_TAG.sub("", _TRANSLATED_BLOCK.sub("", html))))
    parser.close()
    texts = (text.strip() for text in parser.texts)
    return [text for text in texts if _WORD.search(text) and text not in allowed]


def _template_id(path: Path) -> str:
    return str(path.relative_to(PACKAGE / "templates"))


@pytest.mark.unit
@pytest.mark.parametrize("path", TEMPLATES, ids=_template_id)
def test_template_loads_i18n_first(path):
    assert _LOAD_I18N.match(path.read_text())


@pytest.mark.unit
@pytest.mark.parametrize("path", TEMPLATES, ids=_template_id)
def test_template_has_no_untranslated_text(path):
    assert _english(path.read_text()) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        '<button aria-label="Close">x</button>',
        "<p>Nothing here</p>",
        "<span x-text=\"open ? 'Hide' : 'Show'\"></span>",
        '<div data-error="File too large"></div>',
        '<div data-forms="{&quot;other&quot;: &quot;files&quot;}"></div>',
    ],
)
def test_untranslated_text_is_found(source):
    assert _english(source)


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        "<p>{% translate 'Nothing here' %}</p>",
        "<p>{% blocktranslate with n=count %}{{ n }} items{% endblocktranslate %}</p>",
        '<div data-error="{% translate \'File too large\' %}" data-open="true"></div>',
        '<span x-text="displayText || placeholder" :class="open && \'is-open\'">{{ label }} · 5</span>',
        "<script>const label = 'Close';</script>",
        '<div data-forms="{&quot;other&quot;: &quot;⟦files⟧&quot;}" data-selected="[]"></div>',
    ],
)
def test_translated_text_and_values_pass(source):
    assert _english(source) == []


@pytest.mark.unit
@pytest.mark.skipif(not shutil.which("xgettext"), reason="gettext is not installed")
def test_makemessages_extracts_without_warnings(tmp_path):
    assert "warning" not in extract_messages(tmp_path / "django_formwork").lower()


_CHOICES = [("a", "1"), ("b", "2")]


class _EveryWidgetForm(FormworkForm):
    f01 = forms.CharField(widget=TextInput, required=False)
    f02 = forms.CharField(widget=TextInput(attrs={"placeholder": "1"}, floating=True), required=False)
    f03 = forms.CharField(widget=Textarea, required=False)
    f04 = forms.CharField(widget=PasswordInput, required=False)
    f05 = forms.CharField(widget=SearchInput, required=False)
    f06 = forms.CharField(widget=OTPInput, required=False)
    f07 = forms.CharField(widget=InputMask(mask="#####"), required=False)
    f08 = forms.CharField(widget=DataList(suggestions=["1"]), required=False)
    f09 = forms.CharField(widget=ValidatedTextarea(validate_url="/1/"), required=False)
    f10 = forms.CharField(widget=ComboBox(suggestions=["1"]), required=False)
    f11 = forms.CharField(widget=ComboBoxMultiple(suggestions=["1"]), required=False)
    f12 = forms.DateField(widget=DateInput, required=False)
    f13 = forms.DateField(widget=DatePicker, required=False)
    f14 = DateRangeField(required=False)
    f15 = forms.IntegerField(widget=StepperNumberInput, required=False)
    f16 = forms.IntegerField(widget=SuffixNumberInput(suffix="%"), required=False)
    f17 = forms.IntegerField(widget=Range, required=False)
    f18 = forms.TypedChoiceField(choices=Rating.make_choices(5), coerce=int, widget=Rating(allow_clear=True))
    f19 = forms.ChoiceField(choices=_CHOICES, widget=Select, required=False)
    f20 = forms.MultipleChoiceField(choices=_CHOICES, widget=SelectMultiple, required=False)
    f21 = forms.MultipleChoiceField(choices=_CHOICES, widget=CheckboxSelectMultiple, required=False)
    f22 = forms.ChoiceField(choices=_CHOICES, widget=CardRadioSelect, required=False)
    f23 = forms.MultipleChoiceField(choices=_CHOICES, widget=CardCheckboxSelectMultiple, required=False)
    f24 = forms.BooleanField(widget=CheckboxInput(text="1"), required=False)
    f25 = forms.BooleanField(widget=ToggleInput, required=False)
    f26 = forms.FileField(widget=FileDropzoneInput(attrs={"accept": "image/*", "multiple": True}), required=False)
    f27 = forms.ImageField(widget=ImageDropzoneInput(max_size=1536), required=False)
    f28 = forms.CharField(widget=Display, disabled=True, required=False, initial="1")


@pytest.mark.unit
@pytest.mark.usefixtures("pseudo_catalog")
@pytest.mark.parametrize("field", list(_EveryWidgetForm.base_fields))
def test_every_widget_shows_only_translated_text(field):
    form = _EveryWidgetForm(label_suffix="")
    for bound in form:
        bound.label = "1"
    with translation.override("de"):
        html = str(form[field].as_field_group())
        translated_by_django = frozenset(str(day) for day in WEEKDAYS_ABBR.values())
    assert _english(html, translated_by_django) == []
