"""Views for e2e testing — widget showcase with one page per topic."""

from django import forms
from django.forms.models import construct_instance
from django.http import HttpRequest, HttpResponse
from django.template import engines
from e2e.models import AutoSaveFormData, BasicFormData

from django_formwork.forms import FormworkForm, FormworkModelForm
from django_formwork.views import FormworkSearchView, FormworkValidateView
from django_formwork.widgets import (
    ComboBox,
    DataList,
    FileDropZone,
    ImageDropZone,
    MultiSelect,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
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
            "Required ChoiceField \u2014 rendered as a DaisyUI select dropdown. "
            "Defaults to \u201cLow\u201d, validated against the choice list server-side."
        ),
    )
    notify = forms.ChoiceField(
        choices=NOTIFY_CHOICES,
        widget=forms.RadioSelect,
        initial="email",
        help_text=(
            "Required ChoiceField with RadioSelect \u2014 each option is a "
            "DaisyUI radio. Pre-selects \u201cEmail\u201d via initial."
        ),
    )
    agree = forms.BooleanField(
        label="I agree to the terms",
        help_text=(
            "Required BooleanField \u2014 DaisyUI checkbox. Must be checked "
            "to submit; enforced client-side and server-side."
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
                "Required CharField \u2014 TextInput styled as a DaisyUI input. "
                "Validates non-empty on both client and server side."
            ),
            "email": (
                "Required EmailField \u2014 EmailInput with type=email for native "
                "browser validation. Server-side format check via Django."
            ),
            "message": ("Optional CharField \u2014 Textarea styled as a DaisyUI textarea. No validation required."),
            "attachment": (
                "Optional FileField \u2014 standard file input with DaisyUI "
                "file-input styling. No type or size restrictions."
            ),
        }


class AutoSaveForm(FormworkModelForm):
    """Auto-save form: validates on every change, suppresses required errors."""

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial="low",
        help_text=(
            "Required ChoiceField \u2014 DaisyUI select. Auto-saves on change, "
            "validated server-side against the choice list."
        ),
    )
    notify = forms.ChoiceField(
        choices=NOTIFY_CHOICES,
        widget=forms.RadioSelect,
        initial="email",
        help_text=("Required ChoiceField with RadioSelect \u2014 DaisyUI radios. Auto-saves on change."),
    )
    agree = forms.BooleanField(
        label="I agree to the terms",
        help_text=("Required BooleanField \u2014 DaisyUI checkbox. Must be checked; validated server-side only."),
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
                "Required CharField \u2014 DaisyUI input. Auto-saves after "
                "you stop typing. Required error suppressed until all fields filled."
            ),
            "email": (
                "Required EmailField \u2014 DaisyUI input with type=email. "
                "Format validated server-side on every change."
            ),
            "message": ("Optional CharField \u2014 DaisyUI textarea. Auto-saves after you stop typing."),
            "attachment": ("Optional FileField \u2014 DaisyUI file-input. Auto-saves on file selection."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model has blank=True (allows partial saves) but visually these
        # fields are required — set required=True for the asterisk.
        self.fields["name"].required = True
        self.fields["email"].required = True
        # Strip the HTML required attribute so native validation doesn't
        # fire — keep field.required=True for the template asterisk.
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


class SearchSelectForm(FormworkForm):
    """SearchSelect \u2014 plain, with icons, and server-side search."""

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
        label="City (plain)",
    )
    city_icons = forms.ChoiceField(
        choices=[
            ("", ""),
            ("nyc", "New York"),
            ("ldn", "London"),
            ("tyo", "Tokyo"),
            ("par", "Paris"),
        ],
        widget=SearchSelect(
            icons={
                "nyc": "\U0001f5fd",
                "ldn": "\U0001f1ec\U0001f1e7",
                "tyo": "\U0001f5fc",
                "par": "\U0001f1eb\U0001f1f7",
            },
            descriptions={
                "nyc": "The Big Apple",
                "ldn": "Capital of England",
                "tyo": "Capital of Japan",
                "par": "City of Light",
            },
        ),
        required=False,
        label="City (icons + descriptions)",
    )
    city_htmx = forms.ChoiceField(
        widget=SearchSelect(search_url="/e2e/search/cities/"),
        required=False,
        label="City (server-side search)",
    )
    country_htmx_icons = forms.ChoiceField(
        widget=SearchSelect(search_url="/e2e/search/countries/"),
        required=False,
        label="Country (server search, icons + descriptions)",
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


class MultiSelectForm(FormworkForm):
    """MultiSelect \u2014 plain, with icons (auto-search), and server-side search."""

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
        choices=[(code, name) for code, _flag, name in _COUNTRIES],
        widget=MultiSelect(
            icons={code: flag for code, flag, _name in _COUNTRIES},
        ),
        required=False,
        label="Countries (icons, auto-search)",
    )
    languages_htmx = forms.MultipleChoiceField(
        widget=MultiSelect(search_url="/e2e/search/languages/"),
        required=False,
        label="Languages (server-side search)",
    )


class ComboBoxForm(FormworkForm):
    """ComboBox \u2014 single, multiple, with icons, and server-side search."""

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
    language_htmx = forms.CharField(
        widget=ComboBox(
            search_url="/e2e/search/languages/",
            attrs={"placeholder": "Server-side search"},
        ),
        required=False,
        label="Language (server-side)",
    )
    language_htmx_icons = forms.CharField(
        widget=ComboBox(
            search_url="/e2e/search/languages-icons/",
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
            "Server-side validated textarea \u2014 try typing "
            "\u201cbadword\u201d or \u201cspam\u201d to see "
            "inline error highlighting."
        ),
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
        widget=SearchSelect(search_url="/e2e/search/countries/"),
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
        widget=MultiSelect(search_url="/e2e/search/languages/"),
        required=False,
        label="Languages",
    )
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


class E2ECitySearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):
        if not query:
            return E2E_CITIES
        return [c for c in E2E_CITIES if query.lower() in c["label"].lower()]


class E2ELanguageSearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):
        if not query:
            return E2E_LANGUAGES
        return [lang for lang in E2E_LANGUAGES if query.lower() in lang["label"].lower()]


class E2ELanguageIconsSearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):
        if not query:
            return E2E_LANGUAGES_ICONS
        return [lang for lang in E2E_LANGUAGES_ICONS if query.lower() in lang["label"].lower()]


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


class E2ECountrySearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):
        if not query:
            return E2E_COUNTRIES_SEARCH
        return [c for c in E2E_COUNTRIES_SEARCH if query.lower() in c["label"].lower()]


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
<link rel="stylesheet" href="/static/formwork/formwork-dist.css">
<script src="https://unpkg.com/htmx.org@2/dist/htmx.min.js"></script>
<script src="https://unpkg.com/idiomorph@0.7/dist/idiomorph-ext.min.js"></script>
<script src="/static/formwork/formwork.js"></script>
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
        f'hx-post="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        '    <button type="submit" class="btn btn-primary">Submit</button>\n'
        "    {% if saved %}\n"
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph">Delete</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</form>"
    )


def _complex_form_html(url, form_id):
    return (
        f'<form id="{form_id}" method="post" enctype="multipart/form-data" novalidate '
        f'hx-post="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph" hx-sync="this:replace" '
        f'hx-trigger="input delay:1500ms, change delay:300ms, submit">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        f'    <button type="submit" name="_submit" value="1" class="btn btn-primary">Submit</button>\n'
        "    {% if saved %}\n"
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph">Delete</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</form>"
    )


def _autosave_form_html(url, form_id):
    return (
        f'<form id="{form_id}" method="post" enctype="multipart/form-data" novalidate '
        f'hx-post="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph" '
        f'hx-trigger="input delay:500ms, change delay:200ms">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <div class="flex gap-2 mt-4">\n'
        f'    <button type="submit" class="btn btn-primary" '
        f'hx-post="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f"""hx-ext="morph" hx-vals='{{"_submit": "1"}}'>Submit</button>\n"""
        "    {% if saved %}\n"
        f'    <button type="button" class="btn" '
        f'hx-delete="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph">Reset</button>\n'
        f'    <button type="button" class="btn btn-error ml-auto" '
        f'hx-delete="{url}" hx-swap="morph:outerHTML" hx-target="#{form_id}" '
        f'hx-ext="morph">Delete</button>\n'
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
        "Raw HTML inputs without a Django form \u2014 auto-styled by formwork.css",
    ),
    ("simple", "/simple/", "Simple Custom Widgets", "Toggle, range slider, password reveal, datalist, and star rating"),
    (
        "search-select",
        "/search-select/",
        "SearchSelect",
        "Searchable dropdown \u2014 static, with icons, and server-side search via htmx",
    ),
    (
        "multi-select",
        "/multi-select/",
        "MultiSelect",
        "Multi-select dropdown \u2014 plain, with icons and auto-search, and server-side via htmx",
    ),
    (
        "combobox",
        "/combobox/",
        "ComboBox",
        "Filterable text input \u2014 single, multiple, with icons, and server-side via htmx",
    ),
    ("uploads", "/uploads/", "File Uploads", "Drag-and-drop file and image uploads with size and type restrictions"),
    ("textarea", "/textarea/", "ValidatedTextarea", "Server-side validation with inline word highlighting via htmx"),
    (
        "complex",
        "/complex/",
        "Complex Form",
        "Auto-validated cross-field form \u2014 passwords, dates, SearchSelect, MultiSelect with morph resilience",
    ),
    (
        "autosave",
        "/autosave/",
        "Auto-Save Form",
        "Auto-saves on every field change \u2014 server-side validation with idiomorph morphing",
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
    "<script>\n"
    '  document.body.addEventListener("htmx:afterSettle", function(e) {\n'
    "    if (window.Alpine) Alpine.initTree(e.detail.target);\n"
    "  });\n"
    "</script>\n"
    "</body>\n</html>"
)

_ELEMENTS_INNER = (
    '<p class="text-sm text-base-content/60 mb-4">'
    "These raw HTML inputs are auto-styled by formwork.css \u2014"
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
    """Model-backed basic form view — always reads/writes the first row."""
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
    """Auto-save form view — saves on every field change with submit button."""
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
