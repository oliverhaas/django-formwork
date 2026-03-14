"""Views for e2e testing — widget showcase with one page per topic."""

from django import forms
from django.http import HttpRequest, HttpResponse
from django.template import engines

from django_formwork.forms import FormworkForm
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


class BasicForm(FormworkForm):
    """Contact form using only Django's built-in widgets."""

    name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Your name"}),
        help_text="Enter your full name",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Your message..."}),
    )
    priority = forms.ChoiceField(
        choices=[
            ("", "Select\u2026"),
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
    )
    notify = forms.ChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("none", "None")],
        widget=forms.RadioSelect,
    )
    agree = forms.BooleanField(label="I agree to the terms")
    attachment = forms.FileField(required=False)


class SimpleForm(FormworkForm):
    """Toggle, range slider, password reveal, datalist."""

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
        ),
        required=False,
        label="City (with icons)",
    )
    city_htmx = forms.ChoiceField(
        widget=SearchSelect(search_url="/e2e/search/cities/"),
        required=False,
        label="City (server-side search)",
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


class RatingForm(FormworkForm):
    """Rating \u2014 5 stars, 3 stars, hearts, clearable."""

    stars_5 = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        label="5 stars (classic)",
    )
    stars_3 = forms.TypedChoiceField(
        choices=Rating.make_choices(3),
        coerce=int,
        widget=Rating,
        label="3 stars",
    )
    hearts = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating(star_class="mask-heart"),
        label="Hearts",
    )
    clearable = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating(allow_clear=True),
        required=False,
        label="Clearable",
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
            attrs={"rows": "4", "placeholder": "Try typing 'badword' or 'spam'..."},
        ),
        required=False,
    )


class ComplexForm(FormworkForm):
    """Cross-field validation: password confirmation, date ranges, terms."""

    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Password"}),
    )
    confirm_password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Confirm password"}),
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    terms = forms.BooleanField(label="I accept the terms and conditions")

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


def _form_html(url):
    return (
        '<form id="widget-form" method="post" enctype="multipart/form-data" '
        f'hx-post="{url}" hx-swap="morph:outerHTML" hx-target="#widget-form" hx-ext="morph">\n'
        "  {% csrf_token %}\n"
        "  {{ form }}\n"
        '  <button type="submit" class="btn btn-primary mt-4">Submit</button>\n'
        "</form>"
    )


def _page_html(url, title):
    return (
        '<!DOCTYPE html>\n<html lang="en" data-theme="light">\n<head>\n  '
        + _HEAD
        + f"\n  <title>{title}</title>\n</head>\n"
        '<body class="p-8 bg-base-200">\n' + _THEME_SWITCHER + "\n"
        '<div class="max-w-2xl mx-auto">\n'
        '  <div class="card bg-base-100 shadow-sm">\n'
        '    <div class="card-body">\n'
        f'      <h2 class="card-title">{title}</h2>\n'
        "      " + _form_html(url) + "\n"
        "    </div>\n"
        "  </div>\n"
        "</div>\n"
        "</body>\n</html>"
    )


_PAGES = [
    ("/basic/", "Basic Forms", "Contact form using Django\u2019s built-in widgets"),
    ("/elements/", "Standalone Elements", "Raw HTML inputs auto-styled by formwork.css"),
    ("/simple/", "Simple Custom Widgets", "Toggle, range slider, password reveal, datalist"),
    ("/search-select/", "SearchSelect", "Static, with icons, and server-side search"),
    ("/multi-select/", "MultiSelect", "Plain, icons with auto-search, and htmx"),
    ("/combobox/", "ComboBox", "Single, multiple, with icons, and server-side"),
    ("/rating/", "Rating", "Stars, hearts, and clearable variations"),
    ("/uploads/", "File Uploads", "Drop zones and image uploads with restrictions"),
    ("/textarea/", "ValidatedTextarea", "Server-side validation with word highlighting"),
    ("/complex/", "Complex Forms", "Password confirmation, date ranges, and terms"),
]

_CARD_GRID = "\n".join(
    f'      <a href="{url}" class="card bg-base-100 shadow-sm'
    f' hover:shadow-md transition-shadow">\n'
    f'        <div class="card-body py-4">\n'
    f'          <h3 class="card-title text-sm">{title}</h3>\n'
    f'          <p class="text-xs text-base-content/60">{desc}</p>\n'
    f"        </div>\n"
    f"      </a>"
    for url, title, desc in _PAGES
)

_INDEX_HTML = (
    '<!DOCTYPE html>\n<html lang="en" data-theme="light">\n<head>\n  '
    + _HEAD
    + "\n  <title>Formwork Showcase</title>\n</head>\n"
    '<body class="p-8 bg-base-200">\n' + _THEME_SWITCHER + "\n"
    '<div class="max-w-2xl mx-auto">\n'
    '  <h1 class="text-2xl font-bold mb-6">Formwork Showcase</h1>\n'
    '  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">\n' + _CARD_GRID + "\n"
    "  </div>\n"
    "</div>\n"
    "</body>\n</html>"
)

_ELEMENTS_HTML = (
    '<!DOCTYPE html>\n<html lang="en" data-theme="light">\n<head>\n  '
    + _HEAD
    + "\n  <title>Standalone Elements</title>\n</head>\n"
    '<body class="p-8 bg-base-200">\n' + _THEME_SWITCHER + "\n"
    '<div class="max-w-2xl mx-auto">\n'
    '  <div class="card bg-base-100 shadow-sm">\n'
    '    <div class="card-body">\n'
    '      <h2 class="card-title">Standalone Elements</h2>\n'
    '      <p class="text-sm text-base-content/60 mb-4">'
    "These raw HTML inputs are auto-styled by formwork.css \u2014"
    " no Django form needed.</p>\n"
    '      <div class="grid gap-4">\n'
    '        <input type="text" placeholder="Text input">\n'
    '        <input type="email" placeholder="Email input">\n'
    '        <input type="password" placeholder="Password input">\n'
    "        <select>\n"
    '          <option value="">Select\u2026</option>\n'
    "          <option>Option A</option>\n"
    "          <option>Option B</option>\n"
    "          <option>Option C</option>\n"
    "        </select>\n"
    '        <textarea placeholder="Textarea" rows="3"></textarea>\n'
    '        <label class="flex items-center gap-2">'
    '<input type="checkbox"> Checkbox</label>\n'
    '        <label class="flex items-center gap-2">'
    '<input type="radio" name="radio-demo"> Radio A</label>\n'
    '        <label class="flex items-center gap-2">'
    '<input type="radio" name="radio-demo"> Radio B</label>\n'
    '        <input type="file">\n'
    '        <input type="range" min="0" max="100">\n'
    "      </div>\n"
    "    </div>\n"
    "  </div>\n"
    "</div>\n"
    "</body>\n</html>"
)

_TEMPLATES = {
    "basic": (_form_html("/basic/"), _page_html("/basic/", "Basic Forms")),
    "simple": (_form_html("/simple/"), _page_html("/simple/", "Simple Custom Widgets")),
    "search-select": (
        _form_html("/search-select/"),
        _page_html("/search-select/", "SearchSelect"),
    ),
    "multi-select": (
        _form_html("/multi-select/"),
        _page_html("/multi-select/", "MultiSelect"),
    ),
    "combobox": (_form_html("/combobox/"), _page_html("/combobox/", "ComboBox")),
    "rating": (_form_html("/rating/"), _page_html("/rating/", "Rating")),
    "uploads": (_form_html("/uploads/"), _page_html("/uploads/", "File Uploads")),
    "textarea": (
        _form_html("/textarea/"),
        _page_html("/textarea/", "ValidatedTextarea"),
    ),
    "complex": (_form_html("/complex/"), _page_html("/complex/", "Complex Forms")),
}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _form_view(request: HttpRequest, form_class: type, key: str) -> HttpResponse:
    """Generic form view: render page on GET, handle htmx morph on POST."""
    engine = engines["django"]
    form_tmpl, page_tmpl = _TEMPLATES[key]
    is_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        form.is_valid()
        if is_htmx:
            template = engine.from_string(form_tmpl)
            return HttpResponse(template.render({"form": form}, request))
    else:
        form = form_class()

    template = engine.from_string(page_tmpl)
    return HttpResponse(template.render({"form": form}, request))


def index_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse(_INDEX_HTML)


def basic_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, BasicForm, "basic")


def elements_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse(_ELEMENTS_HTML)


def simple_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, SimpleForm, "simple")


def search_select_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, SearchSelectForm, "search-select")


def multi_select_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, MultiSelectForm, "multi-select")


def combobox_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, ComboBoxForm, "combobox")


def rating_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, RatingForm, "rating")


def uploads_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, UploadsForm, "uploads")


def textarea_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, TextareaForm, "textarea")


def complex_view(request: HttpRequest) -> HttpResponse:
    return _form_view(request, ComplexForm, "complex")
