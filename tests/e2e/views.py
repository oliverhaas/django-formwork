"""Views for e2e testing. widget showcase with one page per topic."""

from django import forms
from django.forms.models import construct_instance
from django.http import HttpRequest, HttpResponse
from django.template import engines
from e2e.models import AutoSaveFormData, BasicFormData, City, Region

from django_formwork.fields import ChoiceLabel
from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.views import FormworkValidateView
from django_formwork.widgets import (
    ComboBox,
    DataList,
    DatePicker,
    FileDropZone,
    ImageDropZone,
    InputMask,
    InputNumber,
    MultiSelect,
    OTPInput,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
    Select,
    TextInput,
    Textarea,
    Toggle,
    ValidatedTextarea,
)

# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
NOTIFY_CHOICES = [("email", "Email"), ("sms", "SMS"), ("none", "None")]


class BasicForm(FormworkModelForm):
    """Contact form backed by BasicFormData model."""

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        help_text=(
            "Required ChoiceField, rendered as a DaisyUI select dropdown. "
            "Defaults to \u201cLow\u201d, validated against the choice list server-side."
        ),
    )
    notify = forms.ChoiceField(
        choices=NOTIFY_CHOICES,
        widget=forms.RadioSelect,
        initial="email",
        help_text=(
            "Required ChoiceField with RadioSelect, each option is a "
            "DaisyUI radio. Pre-selects \u201cEmail\u201d via initial."
        ),
    )
    agree = forms.BooleanField(
        label="I agree to the terms",
        help_text=(
            "Required BooleanField, DaisyUI checkbox. Must be checked to submit; enforced client-side and server-side."
        ),
    )

    class Meta:
        model = BasicFormData
        fields = "__all__"
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "message": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Your message..."},
            ),
        }
        help_texts = {
            "name": (
                "Required CharField, TextInput styled as a DaisyUI input. "
                "Validates non-empty on both client and server side."
            ),
            "email": (
                "Required EmailField, EmailInput with type=email for native "
                "browser validation. Server-side format check via Django."
            ),
            "message": ("Optional CharField, Textarea styled as a DaisyUI textarea. No validation required."),
            "attachment": (
                "Optional FileField, standard file input with DaisyUI file-input styling. No type or size restrictions."
            ),
        }


class AutoSaveForm(FormworkModelForm):
    """Auto-save form: validates on every change, suppresses required errors."""

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial="low",
        help_text=(
            "Required ChoiceField, DaisyUI select. Auto-saves on change, validated server-side against the choice list."
        ),
    )
    notify = forms.ChoiceField(
        choices=NOTIFY_CHOICES,
        widget=forms.RadioSelect,
        initial="email",
        help_text=("Required ChoiceField with RadioSelect, DaisyUI radios. Auto-saves on change."),
    )
    agree = forms.BooleanField(
        label="I agree to the terms",
        help_text=("Required BooleanField, DaisyUI checkbox. Must be checked; validated server-side only."),
    )

    class Meta:
        model = AutoSaveFormData
        fields = "__all__"
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "message": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Your message..."},
            ),
        }
        help_texts = {
            "name": (
                "Required CharField, DaisyUI input. Auto-saves after "
                "you stop typing. Required error suppressed until all fields filled."
            ),
            "email": (
                "Required EmailField, DaisyUI input with type=email. Format validated server-side on every change."
            ),
            "message": ("Optional CharField, DaisyUI textarea. Auto-saves after you stop typing."),
            "attachment": ("Optional FileField, DaisyUI file-input. Auto-saves on file selection."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model has blank=True (allows partial saves) but visually these
        # fields are required. set required=True for the asterisk.
        self.fields["name"].required = True
        self.fields["email"].required = True
        # Strip the HTML required attribute so native validation doesn't
        # fire. keep field.required=True for the template asterisk.
        for field in self.fields.values():
            field.widget.use_required_attribute = lambda *_a: False

    def _clean_fields(self):
        """Suppress 'required' errors for empty fields (auto-save UX).

        On explicit submit (_submit in POST data), validate everything.
        """
        super()._clean_fields()
        if self.data.get("_submit"):
            return  # full validation on explicit submit
        for name in list(self._errors):
            field = self.fields[name]
            if not field.required:
                continue
            raw = self.data.get(self.add_prefix(name), "")
            if not raw:
                del self._errors[name]
                if name not in self.cleaned_data:
                    # BooleanField needs False (not "") or model validation
                    # rejects it with "must be either True or False".
                    if isinstance(field, forms.BooleanField):
                        self.cleaned_data[name] = False
                    elif field.initial is not None:
                        self.cleaned_data[name] = field.initial
                    else:
                        self.cleaned_data[name] = ""

    def save(self, commit=True, partial=False):  # noqa: FBT002
        """Save the form. With partial=True, save valid fields only."""
        if not partial:
            return super().save(commit=commit)
        instance = construct_instance(
            self,
            self.instance,
            self.fields,
            self._meta.exclude,
        )
        if commit:
            if instance.pk:
                instance.save(update_fields=list(self.cleaned_data))
            else:
                instance.save()
        return instance


class SimpleForm(FormworkForm):
    """Toggle, range slider, password reveal, datalist, rating."""

    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100", "step": "10"}),
    )
    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Enter password"}),
    )
    browser = forms.CharField(
        widget=DataList(
            datalist=["Chrome", "Firefox", "Safari", "Edge", "Opera"],
            attrs={"placeholder": "Type or pick"},
        ),
        required=False,
    )
    stars = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        label="Rating",
    )
    clearable_rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating(allow_clear=True),
        required=False,
        label="Clearable rating",
    )


class InlineErrorsForm(FormworkForm):
    """Meta.error_display = "inline": errors render like help text, in red, below the field."""

    name = forms.CharField(
        min_length=3,
        help_text=("Enter your full legal name exactly as it appears on your government-issued photo ID or passport."),
    )

    def clean_name(self):
        # Native-first (the default): the browser gates `required`/`min_length`
        # before the form POSTs, so an empty or too-short value shows a native
        # bubble, not an inline error. To see the inline error, enter a
        # native-valid value (>=3 chars) that still fails this server-only rule,
        # e.g. a single word like "Alice". After the first server error,
        # disableNativeValidation() turns native validation off (it keys off the
        # `formwork-errors` class the inline error now carries), so later
        # submits route every error through the server.
        name = self.cleaned_data["name"]
        if " " not in name.strip():
            raise forms.ValidationError("Enter your full name: first and last.")
        return name

    class Meta:
        error_display = "inline"


class TightForm(FormworkForm):
    """Compact form, no help text: Meta.error_display = "tooltip" overlays
    errors on the field instead of pushing the tightly-packed rows apart."""

    username = forms.CharField(
        min_length=3,
        widget=forms.TextInput(attrs={"placeholder": "Username"}),
    )
    pin = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "PIN", "inputmode": "numeric"}),
    )
    # Floating labels (DaisyUI): the placeholder doubles as a label that floats
    # above the control on focus/fill.  Optional so they add no validation
    # errors to the tooltip showcase above.
    nickname = forms.CharField(
        required=False,
        widget=TextInput(attrs={"placeholder": "Nickname"}, floating_label=True),
    )
    role = forms.ChoiceField(
        required=False,
        choices=[("", ""), ("admin", "Admin"), ("user", "User")],
        widget=Select(attrs={"placeholder": "Role"}, floating_label=True),
    )
    note = forms.CharField(
        required=False,
        widget=Textarea(attrs={"placeholder": "Note"}, floating_label=True),
    )

    def clean_username(self):
        # "admin" is native-valid (non-empty, 3+ chars), so it reaches the
        # server; this rule then rejects it. That is the case that surfaces a
        # tooltip rather than a native browser bubble.
        username = self.cleaned_data["username"]
        if username.strip().lower() == "admin":
            raise forms.ValidationError("That name is reserved.")
        return username

    class Meta:
        error_display = "tooltip"


class _FakeFile:
    """Minimal file-like object so ClearableFileInput shows the clear checkbox."""

    url = "#"

    def __str__(self):
        return "photo.jpg"


class GroupedModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that groups cities by their region."""

    def label_from_instance(self, obj):
        return obj.name

    iterator = type(
        "GroupedIterator",
        (forms.models.ModelChoiceIterator,),
        {
            "__iter__": lambda self: iter(
                [("", self.field.empty_label)]
                + [
                    (
                        region.name,
                        [(city.pk, self.field.label_from_instance(city)) for city in region.cities.all()],
                    )
                    for region in Region.objects.prefetch_related("cities")
                ],
            ),
        },
    )


def _ensure_cities():
    """Seed Region/City data if the tables are empty."""
    if Region.objects.exists():
        return
    data = {
        "Europe": ["London", "Paris", "Berlin"],
        "Asia": ["Tokyo", "Seoul", "Bangkok"],
        "Americas": ["New York", "S\u00e3o Paulo", "Mexico City"],
    }
    for region_name, cities in data.items():
        region = Region.objects.create(name=region_name)
        for city_name in cities:
            City.objects.create(name=city_name, region=region)


class BuiltinWidgetsForm(FormworkForm):
    """Showcases Django's built-in widgets that are auto-styled by formwork.css."""

    region = forms.ChoiceField(
        choices=[
            ("", "Select a city\u2026"),
            ("Europe", [("ldn", "London"), ("par", "Paris"), ("ber", "Berlin")]),
            ("Asia", [("tyo", "Tokyo"), ("sel", "Seoul"), ("bkk", "Bangkok")]),
            ("Americas", [("nyc", "New York"), ("sao", "S\u00e3o Paulo"), ("mex", "Mexico City")]),
        ],
        required=False,
        label="City by region",
        help_text="ChoiceField with optgroup, options grouped under region headers.",
    )
    city_model = GroupedModelChoiceField(
        queryset=City.objects.none(),
        required=False,
        empty_label="Select a city\u2026",
        label="City by region (model)",
        help_text="ModelChoiceField with optgroup, same grouping, backed by database models.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _ensure_cities()
        self.fields["city_model"].queryset = City.objects.select_related("region")

    event_at = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
        ),
        required=False,
        label="Event date & time",
        help_text="SplitDateTimeWidget, paired date + time inputs, side by side via CSS grid.",
    )
    avatar = forms.FileField(
        widget=forms.ClearableFileInput,
        required=False,
        initial=_FakeFile(),
        label="Avatar",
        help_text="ClearableFileInput, file input with a \u201cClear\u201d checkbox when a file is set.",
    )
    toppings = forms.MultipleChoiceField(
        choices=[("cheese", "Cheese"), ("pepperoni", "Pepperoni"), ("mushrooms", "Mushrooms"), ("olives", "Olives")],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Toppings",
        help_text="CheckboxSelectMultiple, checkbox group for multi-value selection.",
    )
    birthday = forms.DateField(
        widget=forms.SelectDateWidget(years=range(2020, 2031)),
        required=False,
        label="Birthday",
        help_text="SelectDateWidget, three dropdowns for month, day, and year.",
    )
    disabled_text = forms.CharField(
        widget=forms.TextInput(attrs={"disabled": True}),
        required=False,
        initial="Cannot edit this",
        label="Disabled field",
        help_text="TextInput with disabled attribute.",
    )
    readonly_text = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": True}),
        required=False,
        initial="Read-only value",
        label="Readonly field",
        help_text="TextInput with readonly attribute.",
    )
    color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        required=False,
        label="Favorite color",
        help_text="ColorInput, native color picker.",
    )
    search = forms.CharField(
        widget=forms.TextInput(attrs={"type": "search", "placeholder": "Search\u2026"}),
        required=False,
        label="Search",
        help_text="SearchInput, native search box with a built-in clear affordance.",
    )


_COUNTRIES = [
    ("ar", "\U0001f1e6\U0001f1f7", "Argentina"),
    ("au", "\U0001f1e6\U0001f1fa", "Australia"),
    ("br", "\U0001f1e7\U0001f1f7", "Brazil"),
    ("ca", "\U0001f1e8\U0001f1e6", "Canada"),
    ("cn", "\U0001f1e8\U0001f1f3", "China"),
    ("de", "\U0001f1e9\U0001f1ea", "Germany"),
    ("eg", "\U0001f1ea\U0001f1ec", "Egypt"),
    ("es", "\U0001f1ea\U0001f1f8", "Spain"),
    ("fr", "\U0001f1eb\U0001f1f7", "France"),
    ("gb", "\U0001f1ec\U0001f1e7", "United Kingdom"),
    ("gr", "\U0001f1ec\U0001f1f7", "Greece"),
    ("id", "\U0001f1ee\U0001f1e9", "Indonesia"),
    ("il", "\U0001f1ee\U0001f1f1", "Israel"),
    ("in", "\U0001f1ee\U0001f1f3", "India"),
    ("it", "\U0001f1ee\U0001f1f9", "Italy"),
    ("jp", "\U0001f1ef\U0001f1f5", "Japan"),
    ("kr", "\U0001f1f0\U0001f1f7", "South Korea"),
    ("mx", "\U0001f1f2\U0001f1fd", "Mexico"),
    ("ng", "\U0001f1f3\U0001f1ec", "Nigeria"),
    ("nl", "\U0001f1f3\U0001f1f1", "Netherlands"),
    ("no", "\U0001f1f3\U0001f1f4", "Norway"),
    ("nz", "\U0001f1f3\U0001f1ff", "New Zealand"),
    ("pe", "\U0001f1f5\U0001f1ea", "Peru"),
    ("ph", "\U0001f1f5\U0001f1ed", "Philippines"),
    ("pl", "\U0001f1f5\U0001f1f1", "Poland"),
    ("pt", "\U0001f1f5\U0001f1f9", "Portugal"),
    ("se", "\U0001f1f8\U0001f1ea", "Sweden"),
    ("sg", "\U0001f1f8\U0001f1ec", "Singapore"),
    ("th", "\U0001f1f9\U0001f1ed", "Thailand"),
    ("tr", "\U0001f1f9\U0001f1f7", "Turkey"),
    ("us", "\U0001f1fa\U0001f1f8", "United States"),
]

_COUNTRY_DESCRIPTIONS = {
    "ar": "South America",
    "au": "Oceania",
    "br": "South America",
    "ca": "North America",
    "cn": "East Asia",
    "de": "Central Europe",
    "eg": "North Africa",
    "es": "Southern Europe",
    "fr": "Western Europe",
    "gb": "Northern Europe",
    "gr": "Southern Europe",
    "id": "Southeast Asia",
    "il": "Middle East",
    "in": "South Asia",
    "it": "Southern Europe",
    "jp": "East Asia",
    "kr": "East Asia",
    "mx": "North America",
    "ng": "West Africa",
    "nl": "Western Europe",
    "no": "Northern Europe",
    "nz": "Oceania",
    "pe": "South America",
    "ph": "Southeast Asia",
    "pl": "Central Europe",
    "pt": "Southern Europe",
    "se": "Northern Europe",
    "sg": "Southeast Asia",
    "th": "Southeast Asia",
    "tr": "Eurasia",
    "us": "North America",
}

E2E_COUNTRIES_SEARCH = [
    {
        "value": code,
        "label": name,
        "icon": flag,
        "description": _COUNTRY_DESCRIPTIONS.get(code, ""),
    }
    for code, flag, name in _COUNTRIES
]


class SearchSelectForm(FormworkForm):
    """SearchSelect. few options (no search), many options (auto-search), icons, server-side."""

    city_plain = forms.ChoiceField(
        choices=[
            ("", ""),
            ("nyc", "New York"),
            ("ldn", "London"),
            ("tyo", "Tokyo"),
            ("par", "Paris"),
            ("syd", "Sydney"),
        ],
        widget=SearchSelect,
        required=False,
        label="City (plain, few options)",
    )
    country_many = forms.ChoiceField(
        choices=[("", "")] + [(c, ChoiceLabel(n, icon=flag)) for c, flag, n in _COUNTRIES],
        widget=SearchSelect(),
        required=False,
        label="Country (many options, auto-search)",
    )
    city_icons = forms.ChoiceField(
        choices=[
            ("", ""),
            ("nyc", ChoiceLabel("New York", icon="\U0001f5fd", description="The Big Apple")),
            ("ldn", ChoiceLabel("London", icon="\U0001f1ec\U0001f1e7", description="Capital of England")),
            ("tyo", ChoiceLabel("Tokyo", icon="\U0001f5fc", description="Capital of Japan")),
            ("par", ChoiceLabel("Paris", icon="\U0001f1eb\U0001f1f7", description="City of Light")),
        ],
        widget=SearchSelect(),
        required=False,
        label="City (icons + descriptions)",
    )
    city_htmx = forms.ChoiceField(
        widget=SearchSelect(search_decorator=None),
        required=False,
        label="City (server search, few, no search input)",
    )
    city_htmx_many = forms.ChoiceField(
        widget=SearchSelect(search_decorator=None),
        required=False,
        label="City (server search, many, auto search input)",
    )
    country_htmx_icons = forms.ChoiceField(
        widget=SearchSelect(search_decorator=None),
        required=False,
        label="Country (server search, icons + descriptions)",
    )
    city_grouped = forms.ChoiceField(
        choices=[
            ("", ""),
            (
                "Europe",
                [
                    ("ldn", ChoiceLabel("London", icon="\U0001f1ec\U0001f1e7")),
                    ("par", ChoiceLabel("Paris", icon="\U0001f1eb\U0001f1f7")),
                    ("ber", ChoiceLabel("Berlin", icon="\U0001f1e9\U0001f1ea")),
                ],
            ),
            (
                "Asia",
                [
                    ("tyo", ChoiceLabel("Tokyo", icon="\U0001f1ef\U0001f1f5")),
                    ("sel", ChoiceLabel("Seoul", icon="\U0001f1f0\U0001f1f7")),
                    ("bkk", ChoiceLabel("Bangkok", icon="\U0001f1f9\U0001f1ed")),
                ],
            ),
            (
                "Americas",
                [
                    (
                        "nyc",
                        ChoiceLabel(
                            "New York",
                            icon="\U0001f1fa\U0001f1f8",
                            description="The Big Apple",
                        ),
                    ),
                    ("sao", ChoiceLabel("São Paulo", icon="\U0001f1e7\U0001f1f7")),
                    ("mex", ChoiceLabel("Mexico City", icon="\U0001f1f2\U0001f1fd")),
                ],
            ),
        ],
        widget=SearchSelect(show_search=True),
        required=False,
        label="City by region (grouped)",
        help_text=(
            "Grouped SearchSelect, optgroup headers shown as section titles, "
            "auto-hide when search filters out their children."
        ),
    )
    city_failing = forms.ChoiceField(
        widget=SearchSelect(search_decorator=None),
        required=False,
        label="City (server search, always fails)",
        help_text="Endpoint always raises, exercises the error UX.",
    )
    # Appended last so it does not shift the nth() indices the other e2e
    # tests rely on.  Each option carries a free-form ``selected_toggle_class``
    # that the widget moves onto the closed trigger when selected, recoloring
    # the box.  These are DaisyUI select-* colors, which formwork.css already
    # safelists, so they compile with no extra config here.
    priority = forms.ChoiceField(
        choices=[
            ("", ""),
            ("low", ChoiceLabel("Low", selected_toggle_class="select-success")),
            ("mid", ChoiceLabel("Medium", selected_toggle_class="select-warning")),
            ("high", ChoiceLabel("High", selected_toggle_class="select-error")),
        ],
        widget=SearchSelect,
        required=False,
        label="Priority (trigger recolors by selection)",
        help_text="Selecting an option applies its class to the closed select box.",
    )

    @staticmethod
    def search_choices_city_htmx(query, request=None):
        return _filter_search(query, E2E_CITIES)

    @staticmethod
    def search_choices_city_htmx_many(query, request=None):
        return _filter_search(query, E2E_CITIES_MANY)

    @staticmethod
    def search_choices_country_htmx_icons(query, request=None):
        return _filter_search(query, E2E_COUNTRIES_SEARCH)

    @staticmethod
    def search_choices_city_failing(query, request=None):
        _raise_failure()


class MultiSelectForm(FormworkForm):
    """MultiSelect, plain, with icons (auto-search), and server-side search."""

    languages_plain = forms.MultipleChoiceField(
        choices=[
            ("py", "Python"),
            ("js", "JavaScript"),
            ("go", "Go"),
            ("rs", "Rust"),
        ],
        widget=MultiSelect,
        required=False,
        label="Languages (plain)",
    )
    countries_icons = forms.MultipleChoiceField(
        choices=[(code, ChoiceLabel(name, icon=flag)) for code, flag, name in _COUNTRIES],
        widget=MultiSelect(),
        required=False,
        label="Countries (icons, auto-search)",
    )
    languages_htmx = forms.MultipleChoiceField(
        widget=MultiSelect(search_decorator=None),
        required=False,
        label="Languages (server-side search)",
    )
    cities_grouped = forms.MultipleChoiceField(
        choices=[
            (
                "Europe",
                [
                    ("ldn", ChoiceLabel("London", icon="\U0001f1ec\U0001f1e7")),
                    ("par", ChoiceLabel("Paris", icon="\U0001f1eb\U0001f1f7")),
                    ("ber", ChoiceLabel("Berlin", icon="\U0001f1e9\U0001f1ea")),
                ],
            ),
            (
                "Asia",
                [
                    ("tyo", ChoiceLabel("Tokyo", icon="\U0001f1ef\U0001f1f5")),
                    ("sel", ChoiceLabel("Seoul", icon="\U0001f1f0\U0001f1f7")),
                    ("bkk", ChoiceLabel("Bangkok", icon="\U0001f1f9\U0001f1ed")),
                ],
            ),
            (
                "Americas",
                [
                    ("nyc", ChoiceLabel("New York", icon="\U0001f1fa\U0001f1f8")),
                    ("sao", ChoiceLabel("São Paulo", icon="\U0001f1e7\U0001f1f7")),
                    ("mex", ChoiceLabel("Mexico City", icon="\U0001f1f2\U0001f1fd")),
                ],
            ),
        ],
        widget=MultiSelect(show_search=True),
        required=False,
        label="Cities by region (grouped)",
        help_text="Grouped MultiSelect, optgroup headers, keyboard nav, Enter toggles without closing.",
    )
    languages_failing = forms.MultipleChoiceField(
        widget=MultiSelect(search_decorator=None),
        required=False,
        label="Languages (server search, always fails)",
        help_text="Endpoint always raises, exercises the error UX.",
    )

    @staticmethod
    def search_choices_languages_htmx(query, request=None):
        return _filter_search(query, E2E_LANGUAGES)

    @staticmethod
    def search_choices_languages_failing(query, request=None):
        _raise_failure()


class ComboBoxForm(FormworkForm):
    """ComboBox, single, multiple, with icons, and server-side search."""

    language_single = forms.CharField(
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust", "TypeScript", "Ruby"],
            attrs={"placeholder": "Type a language"},
        ),
        required=False,
        label="Language (single)",
    )
    toppings_multi = forms.CharField(
        widget=ComboBox(
            suggestions=["Pizza", "Pasta", "Sushi", "Tacos", "Curry"],
            multiple=True,
            attrs={"placeholder": "Comma-separated"},
        ),
        required=False,
        label="Toppings (multiple)",
    )
    language_icons = forms.CharField(
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust"],
            icons={
                "Python": "\U0001f40d",
                "JavaScript": "\U0001f7e8",
                "Go": "\U0001f439",
                "Rust": "\U0001f980",
            },
            attrs={"placeholder": "Language with icons"},
        ),
        required=False,
        label="Language (with icons)",
    )
    language_icons_multi = forms.CharField(
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust"],
            icons={
                "Python": "\U0001f40d",
                "JavaScript": "\U0001f7e8",
                "Go": "\U0001f439",
                "Rust": "\U0001f980",
            },
            multiple=True,
            attrs={"placeholder": "Languages with icons"},
        ),
        required=False,
        label="Language (icons + multiple)",
    )
    language_htmx = forms.CharField(
        widget=ComboBox(
            search_decorator=None,
            attrs={"placeholder": "Server-side search"},
        ),
        required=False,
        label="Language (server-side)",
    )
    language_htmx_icons = forms.CharField(
        widget=ComboBox(
            search_decorator=None,
            attrs={"placeholder": "Server search with icons"},
        ),
        required=False,
        label="Language (server search + icons)",
    )
    food_descriptions = forms.CharField(
        widget=ComboBox(
            suggestions=["Pizza", "Sushi", "Tacos", "Curry", "Ramen"],
            icons={
                "Pizza": "\U0001f355",
                "Sushi": "\U0001f363",
                "Tacos": "\U0001f32e",
                "Curry": "\U0001f35b",
                "Ramen": "\U0001f35c",
            },
            descriptions={
                "Pizza": "Italian classic",
                "Sushi": "Japanese delicacy",
                "Tacos": "Mexican street food",
                "Curry": "Indian comfort food",
                "Ramen": "Japanese noodle soup",
            },
            attrs={"placeholder": "Pick a food"},
        ),
        required=False,
        label="Food (icons + descriptions)",
    )
    food_grouped = forms.CharField(
        widget=ComboBox(
            suggestions=[
                ("Italian", ["Pizza", "Pasta", "Risotto"]),
                ("Japanese", ["Sushi", "Ramen", "Tempura"]),
                ("Mexican", ["Tacos", "Burrito", "Enchilada"]),
            ],
            icons={
                "Pizza": "\U0001f355",
                "Pasta": "\U0001f35d",
                "Sushi": "\U0001f363",
                "Ramen": "\U0001f35c",
                "Tacos": "\U0001f32e",
                "Burrito": "\U0001f32f",
            },
            attrs={"placeholder": "Pick a dish (grouped)"},
        ),
        required=False,
        label="Food by cuisine (grouped)",
        help_text="Grouped ComboBox, suggestions grouped by cuisine, optgroup headers hide on filter.",
    )
    language_failing = forms.CharField(
        widget=ComboBox(
            search_decorator=None,
            attrs={"placeholder": "Server search (always fails)"},
        ),
        required=False,
        label="Language (server search, always fails)",
        help_text="Endpoint always raises, exercises the error UX.",
    )

    @staticmethod
    def search_choices_language_htmx(query, request=None):
        return _filter_search(query, E2E_LANGUAGES)

    @staticmethod
    def search_choices_language_htmx_icons(query, request=None):
        return _filter_search(query, E2E_LANGUAGES_ICONS)

    @staticmethod
    def search_choices_language_failing(query, request=None):
        _raise_failure()


class UploadsForm(FormworkForm):
    """File upload widgets with variations."""

    dropzone = forms.FileField(
        widget=FileDropZone(attrs={"multiple": True}),
        required=False,
        label="Drop zone (multi)",
    )
    dropzone_restricted = forms.FileField(
        widget=FileDropZone(
            attrs={"accept": ".pdf"},
            max_size=5 * 1024 * 1024,
        ),
        required=False,
        label="Drop zone (PDF only, 5 MB max)",
    )
    avatar = forms.ImageField(
        widget=ImageDropZone,
        required=False,
    )
    avatar_restricted = forms.ImageField(
        widget=ImageDropZone(
            attrs={"accept": ".png,.jpg,.jpeg"},
            max_size=2 * 1024 * 1024,
        ),
        required=False,
        label="Avatar (PNG/JPEG, 2 MB max)",
    )


class TextareaForm(FormworkForm):
    """ValidatedTextarea with server-side validation."""

    bio = forms.CharField(
        widget=ValidatedTextarea(
            validate_url="/e2e/validate/bio/",
            attrs={"rows": "4", "placeholder": "Write something\u2026"},
        ),
        required=False,
        help_text=(
            "Server-side validated textarea, try typing "
            "\u201cbadword\u201d or \u201cspam\u201d to see "
            "inline error highlighting."
        ),
    )


class NewWidgetsForm(FormworkForm):
    """DatePicker, InputNumber, OTP, Country, InputMask."""

    due_date = forms.DateField(
        widget=DatePicker,
        required=False,
        help_text="Calendar date picker with month navigation.",
    )
    quantity = forms.IntegerField(
        widget=InputNumber(attrs={"min": "1", "max": "99", "step": "1"}),
        initial=1,
        help_text="Number input with +/- stepper buttons.",
    )
    price = forms.FloatField(
        widget=InputNumber(attrs={"min": "0", "max": "10", "step": "0.1"}),
        initial=0.2,
        required=False,
        help_text="Float stepper: 0.1 increments round to step precision.",
    )
    otp_code = forms.CharField(
        widget=OTPInput(length=6),
        required=False,
        help_text="One-time password with auto-advance between digits.",
    )
    country = forms.ChoiceField(
        choices=[("", "")] + [(c, ChoiceLabel(n, icon=flag)) for c, flag, n in _COUNTRIES],
        widget=SearchSelect(),
        required=False,
        help_text="Searchable country selector with flag emojis.",
    )
    zip_code = forms.CharField(
        widget=InputMask(mask="#####"),
        required=False,
        help_text="Masked input: 5 digits only.",
    )
    phone_masked = forms.CharField(
        widget=InputMask(mask="(###) ###-####"),
        required=False,
        label="Phone (masked)",
        help_text="Masked input with pattern formatting.",
    )


class ComplexForm(FormworkForm):
    """Cross-field validation with dropdowns, auto-validated on every change."""

    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Password"}),
    )
    confirm_password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Confirm password"}),
    )
    country = forms.CharField(
        widget=SearchSelect(search_decorator=None),
        required=False,
        label="Country",
    )
    languages = forms.MultipleChoiceField(
        choices=[
            ("py", "Python"),
            ("js", "JavaScript"),
            ("go", "Go"),
            ("rs", "Rust"),
            ("ts", "TypeScript"),
            ("rb", "Ruby"),
        ],
        widget=MultiSelect(search_decorator=None),
        required=False,
        label="Languages",
    )

    @staticmethod
    def search_choices_country(query, request=None):
        return _filter_search(query, E2E_COUNTRIES_SEARCH)

    @staticmethod
    def search_choices_languages(query, request=None):
        return _filter_search(query, E2E_LANGUAGES)

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    terms = forms.BooleanField(label="I accept the terms and conditions")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Strip HTML required so auto-validate POSTs don't trigger native
        # validation.  field.required stays True for the asterisk.
        for field in self.fields.values():
            field.widget.use_required_attribute = lambda *_a: False

    def _clean_fields(self):
        """Suppress 'required' errors for empty fields during auto-validation."""
        super()._clean_fields()
        if self.data.get("_submit"):
            return  # full validation on explicit submit
        for name in list(self._errors):
            field = self.fields[name]
            if not field.required:
                continue
            raw = self.data.get(self.add_prefix(name), "")
            if not raw:
                del self._errors[name]

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if pw and confirm and pw != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start >= end:
            self.add_error("end_date", "End date must be after start date.")
        country = cleaned.get("country")
        languages = cleaned.get("languages", [])
        if country and not languages:
            self.add_error("languages", "Select at least one language when a country is chosen.")
        return cleaned


# ---------------------------------------------------------------------------
# Server-side search and validation endpoints
# ---------------------------------------------------------------------------

E2E_CITIES = [
    {"value": "nyc", "label": "New York"},
    {"value": "ldn", "label": "London"},
    {"value": "tyo", "label": "Tokyo"},
    {"value": "par", "label": "Paris"},
]

E2E_CITIES_MANY = [
    {"value": "nyc", "label": "New York"},
    {"value": "ldn", "label": "London"},
    {"value": "tyo", "label": "Tokyo"},
    {"value": "par", "label": "Paris"},
    {"value": "syd", "label": "Sydney"},
    {"value": "ber", "label": "Berlin"},
    {"value": "rom", "label": "Rome"},
    {"value": "mad", "label": "Madrid"},
    {"value": "ams", "label": "Amsterdam"},
    {"value": "vie", "label": "Vienna"},
    {"value": "prg", "label": "Prague"},
    {"value": "lis", "label": "Lisbon"},
    {"value": "dub", "label": "Dublin"},
    {"value": "cop", "label": "Copenhagen"},
    {"value": "sto", "label": "Stockholm"},
    {"value": "hel", "label": "Helsinki"},
    {"value": "war", "label": "Warsaw"},
    {"value": "bud", "label": "Budapest"},
    {"value": "ath", "label": "Athens"},
    {"value": "ist", "label": "Istanbul"},
    {"value": "bkk", "label": "Bangkok"},
    {"value": "sin", "label": "Singapore"},
    {"value": "hkg", "label": "Hong Kong"},
    {"value": "sel", "label": "Seoul"},
]

E2E_LANGUAGES = [
    {"value": "py", "label": "Python"},
    {"value": "js", "label": "JavaScript"},
    {"value": "go", "label": "Go"},
    {"value": "rs", "label": "Rust"},
    {"value": "ts", "label": "TypeScript"},
    {"value": "rb", "label": "Ruby"},
]

E2E_LANGUAGES_ICONS = [
    {"label": "Python", "icon": "\U0001f40d"},
    {"label": "JavaScript", "icon": "\U0001f7e8"},
    {"label": "Go", "icon": "\U0001f439"},
    {"label": "Rust", "icon": "\U0001f980"},
    {"label": "TypeScript", "icon": "\U0001f535"},
    {"label": "Ruby", "icon": "\U0001f48e"},
]


def _filter_search(query, results):
    """Filter ``results`` by case-insensitive substring match on ``label``.

    Throttle in DevTools (Network panel → "Slow 3G" or custom) if you want
    to observe the loading skeleton in a manual demo.
    """
    if not query:
        return results
    return [r for r in results if query.lower() in r["label"].lower()]


def _raise_failure():
    """Raise to exercise the failure UX (htmx 500 → alert)."""
    raise RuntimeError("Simulated upstream failure")


class E2EBioValidateView(FormworkValidateView):
    def get_errors(self, text, **kwargs):
        errors = []
        lower = text.lower()
        for word in ["badword", "spam"]:
            start = 0
            while True:
                idx = lower.find(word, start)
                if idx == -1:
                    break
                errors.append(
                    {
                        "message": f'"{text[idx : idx + len(word)]}" is not allowed',
                        "start": idx,
                        "end": idx + len(word),
                    },
                )
                start = idx + len(word)
        return errors


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_HEAD = """\
<script>
  var t = localStorage.getItem('formwork-theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.addEventListener('DOMContentLoaded', function() {
    var r = document.querySelector('input.theme-controller[value="' + t + '"]');
    if (r) r.checked = true;
  });
</script>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/formwork/formwork-dist.css">
<script src="https://unpkg.com/htmx.org@4.0.0-beta3/dist/htmx.min.js"></script>
<script type="module" src="/static/formwork/formwork.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>"""

_THEMES = [
    "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
    "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden",
    "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black",
    "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade",
    "night", "coffee", "winter", "dim", "nord", "sunset",
]  # fmt: skip

_THEME_SWITCHER = (
    '<div class="fixed bottom-6 right-6 z-50 dropdown dropdown-top dropdown-end">\n'
    '  <div tabindex="0" role="button" class="btn btn-circle btn-sm shadow-lg">\n'
    '    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'class="size-4"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/>'
    '<path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
    '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/>'
    '<path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
    '<path d="m19.07 4.93-1.41 1.41"/></svg>\n'
    "  </div>\n"
    '  <ul tabindex="0" class="dropdown-content menu bg-base-200 rounded-box shadow-xl '
    'border border-base-300 max-h-80 overflow-y-auto w-44 p-2 flex-nowrap" '
    """@change="const v = $event.target.value; """
    """document.documentElement.setAttribute('data-theme', v); """
    """localStorage.setItem('formwork-theme', v)">\n"""
    + "".join(
        f'    <li><label class="flex gap-2 cursor-pointer">'
        f'<input type="radio" name="theme-dropdown" '
        f'class="theme-controller radio radio-xs" value="{theme}">'
        f" {theme.title()}</label></li>\n"
        for theme in _THEMES
    )
    + "  </ul>\n"
    "</div>"
)


def _form_html(url, form_id):
    return (
        f'<form id="{form_id}" method="post" enctype="multipart/form-data" '
        f'hx-post="{url}" hx-swap="outerMorph" hx-target="#{form_id}">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        '    <button type="submit" class="btn btn-primary">Submit</button>\n'
        "    {% if saved %}\n"
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="outerMorph" hx-target="#{form_id}">Delete</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</form>"
    )


def _complex_form_html(url, form_id):
    return (
        f'<form id="{form_id}" method="post" enctype="multipart/form-data" novalidate '
        f'hx-post="{url}" hx-swap="outerMorph" hx-target="#{form_id}" '
        f'hx-sync="this:replace" '
        f'hx-trigger="input delay:1500ms, change delay:300ms, submit" '
        # In htmx 4, each trigger spec has its own delay timer.  Pending
        # input/change timers from earlier typing would fire AFTER the
        # submit POST and clobber its result.  Clear them on submit.
        f'hx-on:submit="for (const s of this._htmx?.triggerSpecs || []) {{ if (s.timeout) {{ clearTimeout(s.timeout); s.timeout = null; }} }}">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        f'    <button type="submit" name="_submit" value="1" class="btn btn-primary">Submit</button>\n'
        "    {% if saved %}\n"
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="outerMorph" hx-target="#{form_id}">Delete</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</form>"
    )


def _autosave_form_html(url, form_id):
    # Cancel pending auto-save timers before any explicit (non-input)
    # action (submit, reset, delete) so they don't fire afterward and
    # clobber the result.  htmx 4 keeps timers per-spec, so we walk the
    # form's specs.
    cancel_timers = (
        "for (const s of this.closest('form')._htmx?.triggerSpecs || []) "
        "{ if (s.timeout) { clearTimeout(s.timeout); s.timeout = null; } }"
    )
    return (
        f'<form id="{form_id}" method="post" enctype="multipart/form-data" novalidate '
        f'hx-post="{url}" hx-swap="outerMorph" hx-target="#{form_id}" '
        f'hx-trigger="input delay:500ms, change delay:200ms">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        f'    <button type="submit" class="btn btn-primary" '
        f'hx-post="{url}" hx-swap="outerMorph" hx-target="#{form_id}" '
        f'hx-on:click="{cancel_timers}" '
        f"""hx-vals='{{"_submit": "1"}}'>Submit</button>\n"""
        "    {% if saved %}\n"
        f'    <button type="button" class="btn" '
        f'hx-delete="{url}" hx-swap="outerMorph" hx-target="#{form_id}" '
        f'hx-on:click="{cancel_timers}">Reset</button>\n'
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="outerMorph" hx-target="#{form_id}" '
        f'hx-on:click="{cancel_timers}">Delete</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</form>"
    )


def _card_body(title, inner_html, standalone_url=None, description=None):
    link = ""
    if standalone_url:
        link = (
            f' <a href="{standalone_url}" class="flex opacity-40 hover:opacity-70'
            f' transition-opacity" title="Open standalone">'
            '<svg xmlns="http://www.w3.org/2000/svg" class="size-4 mb-0.5" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
            '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
            "</svg></a>"
        )
    desc = ""
    if description:
        desc = f'\n  <p class="text-sm text-base-content/60">{description}</p>'
    return f'<div class="card-body">\n  <h2 class="card-title">{title}{link}</h2>{desc}\n  {inner_html}\n</div>'


def _page_html(title, card_body_html):
    return (
        '<!DOCTYPE html>\n<html lang="en" data-theme="light">\n<head>\n  '
        + _HEAD
        + f"\n  <title>{title}</title>\n</head>\n"
        '<body class="min-h-screen p-8 bg-base-200">\n' + _THEME_SWITCHER + "\n"
        '<div class="max-w-2xl mx-auto">\n'
        '  <div class="card bg-base-100 shadow-sm">\n'
        f"    {card_body_html}\n"
        "  </div>\n"
        "</div>\n"
        "</body>\n</html>"
    )


def _to_session(cleaned_data):
    """Serialize cleaned_data for session storage (skip files)."""
    result = {}
    for key, val in cleaned_data.items():
        if hasattr(val, "read"):
            result[key] = val.name if hasattr(val, "name") else "[file]"
        elif hasattr(val, "isoformat"):
            result[key] = val.isoformat()
        elif isinstance(val, (str, int, float, bool, list, type(None))):
            result[key] = val
        else:
            result[key] = str(val)
    return result


def _build_templates(key, url, title, description=None, form_html_fn=None):
    form_id = f"{key}-form"
    fn = form_html_fn or _form_html
    form_tmpl = fn(url, form_id)
    card_tmpl = _card_body(
        title,
        form_tmpl,
        standalone_url=url,
        description=description,
    )
    page_tmpl = _page_html(
        title,
        _card_body(title, form_tmpl, description=description),
    )
    return form_tmpl, card_tmpl, page_tmpl


# Page registry: (key, url, title, description)
_ICON_MODIFIERS_INNER = (
    '<p class="text-sm text-base-content/60 mb-4">'
    "Button and alert icon modifier patterns.</p>\n"
    # --- btn-icon ---
    '<p class="text-xs font-semibold uppercase tracking-wide text-base-content/40 mt-2">btn-icon / btn-icon-end</p>\n'
    '<div class="flex flex-wrap gap-2 mt-1">\n'
    '  <button id="btn-icon-upload" class="btn btn-primary btn-icon icon-upload">Upload</button>\n'
    '  <button id="btn-icon-end-next" class="btn btn-outline btn-icon-end icon-chevron-right">Next</button>\n'
    '  <button id="btn-icon-square" class="btn btn-square btn-icon icon-pencil" aria-label="Edit"></button>\n'
    "</div>\n"
    '<p class="text-xs font-semibold uppercase tracking-wide text-base-content/40 mt-4">size ladder</p>\n'
    '<div class="flex flex-wrap items-end gap-2 mt-1">\n'
    '  <button id="btn-icon-xs" class="btn btn-xs btn-icon icon-upload">XS</button>\n'
    '  <button id="btn-icon-sm" class="btn btn-sm btn-icon icon-upload">SM</button>\n'
    '  <button class="btn btn-icon icon-upload">MD</button>\n'
    '  <button id="btn-icon-lg" class="btn btn-lg btn-icon icon-upload">LG</button>\n'
    '  <button id="btn-icon-xl" class="btn btn-xl btn-icon icon-upload">XL</button>\n'
    "</div>\n"
    # --- btn-loading ---
    '<div class="divider"></div>\n'
    '<p class="text-xs font-semibold uppercase tracking-wide text-base-content/40">btn-loading</p>\n'
    '<div class="flex flex-wrap gap-2 mt-1">\n'
    '  <button id="btn-loading-standalone" class="btn btn-primary btn-loading"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Save</button>\n"
    '  <button id="btn-loading-icon" class="btn btn-primary btn-icon btn-loading icon-upload"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Upload</button>\n"
    '  <button id="btn-loading-dots" class="btn btn-primary btn-loading btn-loading-dots"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Dots</button>\n"
    '  <button class="btn btn-secondary btn-loading btn-loading-ring"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Ring</button>\n"
    '  <button class="btn btn-accent btn-loading btn-loading-ball"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Ball</button>\n"
    '  <button class="btn btn-neutral btn-loading btn-loading-bars"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Bars</button>\n"
    '  <button class="btn btn-info btn-loading btn-loading-infinity"'
    " @click=\"$el.classList.add('htmx-request'); setTimeout(() => $el.classList.remove('htmx-request'), 3000)\""
    ">Infinity</button>\n"
    "</div>\n"
    # --- alert-icon ---
    '<div class="divider"></div>\n'
    '<p class="text-xs font-semibold uppercase tracking-wide text-base-content/40">alert-icon / alert-col / alert-soft</p>\n'
    '<div class="grid gap-3 mt-1">\n'
    '  <div id="alert-icon-default" class="alert alert-success alert-icon">Saved successfully.</div>\n'
    '  <div id="alert-icon-custom" class="alert alert-warning alert-icon icon-triangle-alert">Check input.</div>\n'
    '  <div id="alert-soft" class="alert alert-info alert-soft alert-icon">Tip: drag to reorder.</div>\n'
    '  <div id="alert-col" class="alert alert-info alert-col alert-icon icon-search">\n'
    "    <strong>No matches</strong>\n"
    "    <p>Try broadening your search.</p>\n"
    "  </div>\n"
    "</div>"
)

_ICON_MODIFIERS_BODY = _card_body("Icon Modifiers", _ICON_MODIFIERS_INNER)
_ICON_MODIFIERS_CARD = _card_body(
    "Icon Modifiers",
    _ICON_MODIFIERS_INNER,
    standalone_url="/icon-modifiers/",
)
_ICON_MODIFIERS_HTML = _page_html("Icon Modifiers", _ICON_MODIFIERS_BODY)

_PAGES = [
    (
        "basic",
        "/basic/",
        "Basic Form",
        "Contact form using only Django\u2019s built-in widgets, auto-styled by formwork.css with DaisyUI components",
    ),
    (
        "elements",
        "/elements/",
        "Standalone Elements",
        "Raw HTML inputs without a Django form, auto-styled by formwork.css",
    ),
    ("simple", "/simple/", "Simple Custom Widgets", "Toggle, range slider, password reveal, datalist, and star rating"),
    (
        "inline-errors",
        "/inline-errors/",
        "Inline Errors",
        "Meta.error_display = \u201cinline\u201d, errors render like help text, in red, below the field",
    ),
    (
        "tight",
        "/tight/",
        "Tight Form",
        "Compact form, no help text, Meta.error_display = \u201ctooltip\u201d, errors overlay instead of pushing the packed rows apart",
    ),
    (
        "builtin",
        "/builtin/",
        "Built-in Widgets",
        "Django\u2019s built-in compound widgets, SplitDateTimeWidget, ClearableFileInput, CheckboxSelectMultiple, SelectDateWidget",
    ),
    (
        "search-select",
        "/search-select/",
        "SearchSelect",
        "Searchable dropdown, static, with icons, and server-side search via htmx",
    ),
    (
        "multi-select",
        "/multi-select/",
        "MultiSelect",
        "Multi-select dropdown, plain, with icons and auto-search, and server-side via htmx",
    ),
    (
        "combobox",
        "/combobox/",
        "ComboBox",
        "Filterable text input, single, multiple, with icons, and server-side via htmx",
    ),
    ("uploads", "/uploads/", "File Uploads", "Drag-and-drop file and image uploads with size and type restrictions"),
    ("textarea", "/textarea/", "ValidatedTextarea", "Server-side validation with inline word highlighting via htmx"),
    (
        "new-widgets",
        "/new-widgets/",
        "New Widgets",
        "DatePicker, InputNumber, OTP, Country, InputMask",
    ),
    (
        "complex",
        "/complex/",
        "Complex Form",
        "Auto-validated cross-field form, passwords, dates, SearchSelect, MultiSelect with morph resilience",
    ),
    (
        "autosave",
        "/autosave/",
        "Auto-Save Form",
        "Auto-saves on every field change, server-side validation with htmx morph swap",
    ),
    (
        "icon-modifiers",
        "/icon-modifiers/",
        "Icon Modifiers",
        "Button and alert icon modifier patterns, btn-icon, btn-loading, alert-icon",
    ),
]

# Lazy-loading cards for the combined overview page
_LAZY_CARDS = "\n".join(
    f'  <div id="card-{key}" class="card bg-base-100 shadow-sm"\n'
    f'       hx-get="{url}" hx-trigger="load" hx-swap="innerHTML">\n'
    f'    <div class="card-body">\n'
    f'      <h2 class="card-title text-sm">{title}</h2>\n'
    f'      <p class="text-xs text-base-content/60">{desc}</p>\n'
    f'      <span class="loading loading-spinner loading-sm"></span>\n'
    f"    </div>\n"
    f"  </div>"
    for key, url, title, desc in _PAGES
)

_INDEX_HTML = (
    '<!DOCTYPE html>\n<html lang="en" data-theme="light">\n<head>\n  '
    + _HEAD
    + "\n  <title>Formwork Showcase</title>\n</head>\n"
    '<body class="min-h-screen p-8 bg-base-200">\n' + _THEME_SWITCHER + "\n"
    '<div class="max-w-2xl mx-auto flex flex-col gap-8">\n'
    '  <h1 class="text-2xl font-bold">Formwork Showcase</h1>\n' + _LAZY_CARDS + "\n</div>\n"
    "</body>\n</html>"
)

_ELEMENTS_INNER = (
    '<p class="text-sm text-base-content/60 mb-4">'
    "These raw HTML inputs are auto-styled by formwork.css,"
    " no Django form needed.</p>\n"
    '<div class="grid gap-4">\n'
    '  <input type="text" placeholder="Text input">\n'
    '  <input type="email" placeholder="Email input">\n'
    '  <input type="password" placeholder="Password input">\n'
    "  <select>\n"
    '    <option value="">Select\u2026</option>\n'
    "    <option>Option A</option>\n"
    "    <option>Option B</option>\n"
    "    <option>Option C</option>\n"
    "  </select>\n"
    '  <textarea placeholder="Textarea" rows="3"></textarea>\n'
    '  <label class="flex items-center gap-2">'
    '<input type="checkbox"> Checkbox</label>\n'
    '  <label class="flex items-center gap-2">'
    '<input type="radio" name="radio-demo"> Radio A</label>\n'
    '  <label class="flex items-center gap-2">'
    '<input type="radio" name="radio-demo"> Radio B</label>\n'
    '  <input type="file">\n'
    '  <input type="range" min="0" max="100">\n'
    '  <p class="text-sm font-medium mt-2">'
    "Soft colour variants (select-soft / input-soft / textarea-soft)</p>\n"
    '  <select class="select-soft select-accent">\n'
    "    <option>Accent soft select</option>\n"
    "    <option>Option A</option>\n"
    "    <option>Option B</option>\n"
    "  </select>\n"
    '  <select class="select-soft select-error">\n'
    "    <option>Error soft select</option>\n"
    "    <option>Option A</option>\n"
    "    <option>Option B</option>\n"
    "  </select>\n"
    '  <input type="text" class="input-soft input-accent" value="Accent soft input">\n'
    '  <textarea class="textarea-soft textarea-accent" rows="2">Accent soft textarea</textarea>\n'
    "</div>"
)

_ELEMENTS_BODY = _card_body("Standalone Elements", _ELEMENTS_INNER)
_ELEMENTS_CARD = _card_body(
    "Standalone Elements",
    _ELEMENTS_INNER,
    standalone_url="/elements/",
)
_ELEMENTS_HTML = _page_html("Standalone Elements", _ELEMENTS_BODY)

_FORM_HTML_FNS = {"complex": _complex_form_html, "autosave": _autosave_form_html}

_TEMPLATES = {
    key: _build_templates(key, url, title, desc, _FORM_HTML_FNS.get(key))
    for key, url, title, desc in _PAGES
    if key != "elements"
}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _form_view(request: HttpRequest, form_class: type, key: str) -> HttpResponse:
    """Generic form view: render page on GET, handle htmx morph on POST."""
    engine = engines["django"]
    form_tmpl, card_tmpl, page_tmpl = _TEMPLATES[key]
    is_htmx = request.headers.get("HX-Request") == "true"
    session_key = f"formwork:{key}"

    if request.method == "DELETE":
        request.session.pop(session_key, None)
        form = form_class()
        ctx = {"form": form, "saved": False}
        template = engine.from_string(form_tmpl)
        return HttpResponse(template.render(ctx, request))

    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        valid = form.is_valid()
        if valid:
            request.session[session_key] = _to_session(form.cleaned_data)
        ctx = {"form": form, "saved": valid}
        if is_htmx:
            template = engine.from_string(form_tmpl)
            return HttpResponse(template.render(ctx, request))
        template = engine.from_string(page_tmpl)
        return HttpResponse(template.render(ctx, request))

    saved = request.session.get(session_key)
    form = form_class(initial=saved) if saved else form_class()
    ctx = {"form": form, "saved": bool(saved)}
    if is_htmx:
        template = engine.from_string(card_tmpl)
        return HttpResponse(template.render(ctx, request))

    template = engine.from_string(page_tmpl)
    return HttpResponse(template.render(ctx, request))


def index_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse(_INDEX_HTML)


def basic_view(request: HttpRequest) -> HttpResponse:
    """Model-backed basic form view. always reads/writes the first row."""
    engine = engines["django"]
    form_tmpl, card_tmpl, page_tmpl = _TEMPLATES["basic"]
    is_htmx = request.headers.get("HX-Request") == "true"

    obj = BasicFormData.objects.first()

    if request.method == "DELETE":
        if obj:
            obj.delete()
        form = BasicForm()
        template = engine.from_string(form_tmpl)
        return HttpResponse(template.render({"form": form, "saved": False}, request))

    if request.method == "POST":
        form = BasicForm(request.POST, request.FILES, instance=obj)
        valid = form.is_valid()
        if valid:
            form.save()
        ctx = {"form": form, "saved": valid}
        if is_htmx:
            template = engine.from_string(form_tmpl)
            return HttpResponse(template.render(ctx, request))
        template = engine.from_string(page_tmpl)
        return HttpResponse(template.render(ctx, request))

    # GET
    form = BasicForm(instance=obj) if obj else BasicForm()
    ctx = {"form": form, "saved": obj is not None}
    if is_htmx:
        template = engine.from_string(card_tmpl)
        return HttpResponse(template.render(ctx, request))
    template = engine.from_string(page_tmpl)
    return HttpResponse(template.render(ctx, request))


def autosave_view(request: HttpRequest) -> HttpResponse:
    """Auto-save form view. saves on every field change with submit button."""
    engine = engines["django"]
    form_tmpl, card_tmpl, page_tmpl = _TEMPLATES["autosave"]
    is_htmx = request.headers.get("HX-Request") == "true"

    obj = AutoSaveFormData.objects.first()

    if request.method == "DELETE":
        if obj:
            obj.delete()
        form = AutoSaveForm()
        template = engine.from_string(form_tmpl)
        return HttpResponse(template.render({"form": form, "saved": False}, request))

    if request.method == "POST":
        is_submit = request.POST.get("_submit") == "1"
        form = AutoSaveForm(request.POST, request.FILES, instance=obj)
        valid = form.is_valid()
        if is_submit:
            if valid:
                obj = form.save()
        else:
            # Auto-save: save all valid fields even when some have errors
            obj = form.save(partial=True)
        ctx = {
            "form": form,
            "saved": valid or obj is not None,
        }
        template = engine.from_string(form_tmpl if is_htmx else page_tmpl)
        return HttpResponse(template.render(ctx, request))

    # GET
    form = AutoSaveForm(instance=obj) if obj else AutoSaveForm()
    ctx = {"form": form, "saved": obj is not None}
    template = engine.from_string(card_tmpl if is_htmx else page_tmpl)
    return HttpResponse(template.render(ctx, request))


def elements_view(request: HttpRequest) -> HttpResponse:
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(_ELEMENTS_CARD)
    return HttpResponse(_ELEMENTS_HTML)


def simple_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, SimpleForm, "simple")


def inline_errors_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, InlineErrorsForm, "inline-errors")


def tight_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, TightForm, "tight")


def builtin_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, BuiltinWidgetsForm, "builtin")


def search_select_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, SearchSelectForm, "search-select")


def multi_select_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, MultiSelectForm, "multi-select")


def combobox_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, ComboBoxForm, "combobox")


def uploads_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, UploadsForm, "uploads")


def textarea_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, TextareaForm, "textarea")


def new_widgets_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, NewWidgetsForm, "new-widgets")


def icon_modifiers_view(request: HttpRequest) -> HttpResponse:
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(_ICON_MODIFIERS_CARD)
    return HttpResponse(_ICON_MODIFIERS_HTML)


def complex_view(request: HttpRequest) -> HttpResponse:
    """Complex form: auto-validates on change, saves only on explicit submit."""
    engine = engines["django"]
    form_tmpl, card_tmpl, page_tmpl = _TEMPLATES["complex"]
    is_htmx = request.headers.get("HX-Request") == "true"
    session_key = "formwork:complex"

    if request.method == "DELETE":
        request.session.pop(session_key, None)
        form = ComplexForm()
        template = engine.from_string(form_tmpl)
        return HttpResponse(template.render({"form": form, "saved": False}, request))

    if request.method == "POST":
        is_submit = request.POST.get("_submit") == "1"
        form = ComplexForm(request.POST, request.FILES)
        valid = form.is_valid()
        if is_submit and valid:
            request.session[session_key] = _to_session(form.cleaned_data)
        ctx = {"form": form, "saved": is_submit and valid}
        template = engine.from_string(form_tmpl if is_htmx else page_tmpl)
        return HttpResponse(template.render(ctx, request))

    saved = request.session.get(session_key)
    form = ComplexForm(initial=saved) if saved else ComplexForm()
    ctx = {"form": form, "saved": bool(saved)}
    template = engine.from_string(card_tmpl if is_htmx else page_tmpl)
    return HttpResponse(template.render(ctx, request))
