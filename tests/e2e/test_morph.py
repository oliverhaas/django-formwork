"""A morph keeps what the user did in a field, and shows what the server sent after the user left it."""

import pytest
from django import forms
from e2e.models import SearchOption
from playwright.sync_api import FilePayload, expect

from django_formwork import DateRangeField
from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    CardCheckboxSelectMultiple,
    CardRadioSelect,
    CheckboxSelectMultiple,
    ClearableFileInput,
    ComboBox,
    DataList,
    DateInput,
    DatePicker,
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

CHOICES = [("red", "Red"), ("green", "Green"), ("blue", "Blue"), ("black", "Black")]
STARS = [(str(n), f"{n} stars") for n in range(1, 6)]
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


def colours(request):
    return SearchOption.objects.filter(kind="colour")


def text(widget=None):
    return forms.CharField(required=False, widget=widget or TextInput())


def choice(widget, choices=CHOICES):
    return forms.ChoiceField(required=False, choices=choices, widget=widget)


def choices(widget, choices=CHOICES):
    return forms.MultipleChoiceField(required=False, choices=choices, widget=widget)


def searched(field, widget):
    return field(
        queryset=SearchOption.objects.filter(kind="colour"),
        to_field_name="code",
        required=False,
        widget=widget(search_fields=["name"], search_queryset=colours, search_decorator=None),
    )


def combo_box():
    return text(ComboBox(search_fields=["name"], search_queryset=colours, search_decorator=None))


def fill(value, selector="#id_value"):
    return lambda form: form.locator(selector).fill(value)


def pick(*labels):
    """Opens the dropdown and picks; a single select closes on the pick, a multiple one stays open."""

    def act(form):
        form.locator("summary").click()
        for label in labels:
            form.get_by_role("option", name=label).click()

    return act


def pick_and_close(*labels):
    def act(form):
        pick(*labels)(form)
        form.locator("summary").click()

    return act


def search(query):
    def act(form):
        form.locator("summary").click()
        form.get_by_role("searchbox", name="Search").fill(query)

    return act


def check(*labels):
    def act(form):
        for label in labels:
            form.get_by_text(label, exact=True).click()

    return act


def select_option(*values, selector="#id_value"):
    return lambda form: form.locator(selector).select_option(list(values))


def reopen_after_pick(form):
    pick("Green")(form)
    form.locator("summary").click()


def highlight(form):
    form.locator("summary").click()
    form.locator("summary").press("ArrowDown")


def reveal(form):
    form.locator("#id_value").fill("secret")
    form.get_by_role("button", name="Show password").click()


def step_up_twice(form):
    form.get_by_role("button", name="Increase").click()
    form.get_by_role("button", name="Increase").click()


def fill_range(form):
    form.locator("#id_value").fill("11/2/2026")
    form.locator("#id_value_end").fill("11/27/2026")
    form.locator("#id_value_end").press("Enter")


def fill_date(form):
    form.locator("#id_value").fill("11/24/2026")
    form.locator("#id_value").press("Escape")


def open_calendar(form):
    form.get_by_role("button", name="Open calendar").click()
    expect(form.get_by_role("dialog", name="Calendar")).to_be_visible()


def search_server(form):
    search("Colour 2")(form)
    expect(form.get_by_role("option", name="Colour 29")).to_be_visible()


def search_and_pick(form):
    search_server(form)
    form.get_by_role("option", name="Colour 22").click()


def search_pick_and_close(form):
    search_and_pick(form)
    form.locator("summary").click()


def suggest(form):
    form.locator("#id_value").fill("Colour 2")
    expect(form.get_by_role("option", name="Colour 22")).to_be_in_viewport()


def type_and_dismiss(form):
    suggest(form)
    form.locator("#id_value").press("Escape")


def choose_file(name, mime_type, buffer):
    def act(form):
        form.locator("input[type=file]").set_input_files(
            files=FilePayload(name=name, mimeType=mime_type, buffer=buffer)
        )

    return act


def rate(form):
    form.get_by_role("radio", name="4 stars").check()


def expand_help_text(form):
    form.locator("#id_value_disclosure > summary").click()


KEEPS = {
    "text_input": (text(), fill("Lamp")),
    "text_input_floating": (text(TextInput(floating=True, attrs={"placeholder": "Name"})), fill("Lamp")),
    "textarea": (text(Textarea()), fill("First line\nSecond line")),
    "validated_textarea": (text(ValidatedTextarea()), fill("First line")),
    "password_revealed": (forms.CharField(required=False, widget=PasswordInput(render_value=True)), reveal),
    "otp_input": (text(OTPInput(length=4)), fill("1234")),
    "search_input": (text(SearchInput()), fill("lamps")),
    "input_mask": (text(InputMask(mask="#####")), fill("12345")),
    "datalist": (text(DataList(suggestions=["Red", "Green"])), fill("Gre")),
    "suffix_number": (forms.DecimalField(required=False, widget=SuffixNumberInput(suffix="%")), fill("12.5")),
    "stepper_number": (
        forms.IntegerField(required=False, widget=StepperNumberInput(integer=True, min=0)),
        step_up_twice,
    ),
    "range": (
        forms.IntegerField(required=False, widget=Range(attrs={"min": "0", "max": "100", "step": "10"})),
        fill("70"),
    ),
    "rating": (choice(Rating(), STARS), rate),
    "date_input": (forms.DateField(required=False, widget=DateInput()), fill("2026-11-10")),
    "date_picker": (forms.DateField(required=False, widget=DatePicker()), fill_date),
    "date_picker_open": (forms.DateField(required=False, widget=DatePicker()), open_calendar),
    "date_range": (DateRangeField(required=False), fill_range),
    "split_date_time": (
        forms.SplitDateTimeField(required=False),
        lambda form: (form.locator("#id_value_0").fill("2026-11-10"), form.locator("#id_value_1").fill("09:30")),
    ),
    "select_date": (
        forms.DateField(required=False, widget=forms.SelectDateWidget(years=range(2025, 2028))),
        lambda form: (
            form.locator("#id_value_year").select_option("2026"),
            form.locator("#id_value_month").select_option("11"),
            form.locator("#id_value_day").select_option("10"),
        ),
    ),
    "checkbox": (forms.BooleanField(required=False), check("Value")),
    "toggle": (forms.BooleanField(required=False, widget=ToggleInput()), check("Value")),
    "radio_select": (choice(forms.RadioSelect()), check("Green")),
    "checkbox_select_multiple": (choices(CheckboxSelectMultiple(columns=2)), check("Green", "Blue")),
    "card_radio": (choice(CardRadioSelect(), CHOICES[:3]), check("Green")),
    "card_checkbox": (choices(CardCheckboxSelectMultiple(), CHOICES[:3]), check("Green", "Blue")),
    "native_select": (choice(forms.Select()), select_option("green")),
    "native_select_multiple": (choices(forms.SelectMultiple()), select_option("green", "blue")),
    "select_picked": (choice(Select()), pick("Green")),
    "select_open": (choice(Select()), reopen_after_pick),
    "select_searching": (choice(Select(show_search=True)), search("bl")),
    "select_highlighted": (choice(Select()), highlight),
    "select_floating": (choice(Select(floating=True, attrs={"placeholder": "Colour"})), pick("Green")),
    "select_multiple_open": (choices(SelectMultiple()), pick("Green", "Blue")),
    "select_multiple_picked": (choices(SelectMultiple()), pick_and_close("Green", "Blue")),
    "select_multiple_summary": (choices(SelectMultiple()), pick_and_close("Red", "Green", "Blue", "Black")),
    "select_server_search": (searched(forms.ModelChoiceField, Select), search_server),
    "select_multiple_server_search": (searched(forms.ModelMultipleChoiceField, SelectMultiple), search_and_pick),
    "combo_box_suggesting": (combo_box(), suggest),
    "file_dropzone": (
        forms.FileField(required=False, widget=FileDropzoneInput()),
        choose_file("notes.txt", "text/plain", b"notes"),
    ),
    "image_dropzone": (
        forms.ImageField(required=False, widget=ImageDropzoneInput()),
        choose_file("logo.png", "image/png", PNG),
    ),
    "clearable_file_input": (
        forms.FileField(required=False, widget=ClearableFileInput()),
        choose_file("notes.txt", "text/plain", b"notes"),
    ),
    "help_text_expanded": (
        forms.CharField(
            required=False, help_text="A help text long enough to need more than one line. " * 3, widget=TextInput()
        ),
        expand_help_text,
    ),
}

SHOWS = {
    "text_input": (text(), fill("Lamp"), {"value": "Chair"}),
    "text_input_cleared": (text(), fill("Lamp"), {"value": ""}),
    "text_input_error": (forms.IntegerField(required=False, widget=TextInput()), fill("many"), {"value": "many"}),
    "textarea": (text(Textarea()), fill("First line"), {"value": "Other line"}),
    "validated_textarea": (text(ValidatedTextarea()), fill("First line"), {"value": "Other line"}),
    "search_input": (text(SearchInput()), fill("lamps"), {"value": "chairs"}),
    "input_mask": (text(InputMask(mask="#####")), fill("12345"), {"value": "54321"}),
    "suffix_number": (
        forms.DecimalField(required=False, widget=SuffixNumberInput(suffix="%")),
        fill("12.5"),
        {"value": "7"},
    ),
    "stepper_number": (
        forms.IntegerField(required=False, widget=StepperNumberInput(integer=True, min=0)),
        step_up_twice,
        {"value": "5"},
    ),
    "range": (
        forms.IntegerField(required=False, widget=Range(attrs={"min": "0", "max": "100", "step": "10"})),
        fill("70"),
        {"value": "20"},
    ),
    "rating": (choice(Rating(), STARS), rate, {"value": "2"}),
    "date_input": (forms.DateField(required=False, widget=DateInput()), fill("2026-11-10"), {"value": "2026-12-24"}),
    "date_picker": (forms.DateField(required=False, widget=DatePicker()), fill_date, {"value": "2026-12-24"}),
    "date_range": (DateRangeField(required=False), fill_range, {"value_0": "2026-12-01", "value_1": "2026-12-31"}),
    "split_date_time": (
        forms.SplitDateTimeField(required=False),
        lambda form: (form.locator("#id_value_0").fill("2026-11-10"), form.locator("#id_value_1").fill("09:30")),
        {"value_0": "2026-12-24", "value_1": "18:00"},
    ),
    "select_date": (
        forms.DateField(required=False, widget=forms.SelectDateWidget(years=range(2025, 2028))),
        lambda form: form.locator("#id_value_month").select_option("11"),
        {"value_year": "2027", "value_month": "3", "value_day": "5"},
    ),
    "checkbox": (forms.BooleanField(required=False), check("Value"), {}),
    "toggle": (forms.BooleanField(required=False, widget=ToggleInput()), check("Value"), {}),
    "radio_select": (choice(forms.RadioSelect()), check("Green"), {"value": "blue"}),
    "checkbox_select_multiple": (
        choices(CheckboxSelectMultiple(columns=2)),
        check("Green", "Blue"),
        {"value": ["red"]},
    ),
    "card_radio": (choice(CardRadioSelect(), CHOICES[:3]), check("Green"), {"value": "blue"}),
    "card_checkbox": (choices(CardCheckboxSelectMultiple(), CHOICES[:3]), check("Green", "Blue"), {"value": ["red"]}),
    "native_select": (choice(forms.Select()), select_option("green"), {"value": "blue"}),
    "native_select_multiple": (choices(forms.SelectMultiple()), select_option("green", "blue"), {"value": ["red"]}),
    "select": (choice(Select()), pick("Green"), {"value": "blue"}),
    "select_floating": (
        choice(Select(floating=True, attrs={"placeholder": "Colour"})),
        pick("Green"),
        {"value": "blue"},
    ),
    "select_multiple": (choices(SelectMultiple()), pick_and_close("Green", "Blue"), {"value": ["red"]}),
    "select_multiple_summary": (
        choices(SelectMultiple()),
        pick_and_close("Green"),
        {"value": ["red", "green", "blue", "black"]},
    ),
    "select_server_search": (searched(forms.ModelChoiceField, Select), search_and_pick, {"value": "c25"}),
    "select_multiple_server_search": (
        searched(forms.ModelMultipleChoiceField, SelectMultiple),
        search_pick_and_close,
        {"value": ["c25"]},
    ),
    "combo_box": (combo_box(), type_and_dismiss, {"value": "Colour 05"}),
}


def form_with(field):
    """A form with the one field; the search registry keys a field's search by its form's name."""
    return type(f"MorphForm{id(field)}", (FormworkForm,), {"value": field})


@pytest.fixture(autouse=True)
def colour_options(db):
    SearchOption.objects.bulk_create(
        SearchOption(kind="colour", code=f"c{n:02}", name=f"Colour {n:02}") for n in range(1, 31)
    )


@pytest.mark.parametrize(("field", "act"), KEEPS.values(), ids=KEEPS.keys())
def test_morph_keeps_what_the_user_did(morph_page, field, act):
    morph_page.open(form_with(field))
    act(morph_page.form)
    morph_page.assert_morph_keeps_state()


@pytest.mark.parametrize(("field", "act", "data"), SHOWS.values(), ids=SHOWS.keys())
def test_morph_shows_what_the_server_sent(morph_page, field, act, data):
    morph_page.open(form_with(field))
    act(morph_page.form)
    morph_page.assert_morph_shows(data)
