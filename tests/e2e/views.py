"""Views for e2e testing — render forms for Playwright to interact with."""

from django import forms
from django.http import HttpRequest, HttpResponse
from django.template import engines

from django_formwork.forms import FormworkForm
from django_formwork.views import FormworkSearchView, FormworkValidateView
from django_formwork.widgets import (
    ComboBox,
    DropZone,
    ImageUpload,
    MultiSelect,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
    Toggle,
    ValidatedTextarea,
)

# ---------------------------------------------------------------------------
# Test forms
# ---------------------------------------------------------------------------


class BasicForm(FormworkForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Your name"}),
        help_text="Enter your full name",
    )
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    priority = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("low", "Low"), ("med", "Medium"), ("high", "High")],
    )


class WidgetsForm(FormworkForm):
    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(widget=Range(attrs={"min": "0", "max": "100", "step": "10"}))
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
    )
    password = forms.CharField(widget=PasswordReveal(attrs={"placeholder": "Password"}))
    checkbox = forms.BooleanField(required=False)
    radio = forms.ChoiceField(
        choices=[("a", "Option A"), ("b", "Option B"), ("c", "Option C")],
        widget=forms.RadioSelect,
    )
    file = forms.FileField(required=False)


class SelectForm(FormworkForm):
    combo = forms.ChoiceField(
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
    )
    multi = forms.MultipleChoiceField(
        choices=[("py", "Python"), ("js", "JavaScript"), ("go", "Go"), ("rs", "Rust")],
        widget=MultiSelect,
        required=False,
    )


class AdvancedForm(FormworkForm):
    tags = forms.CharField(
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust"],
            attrs={"placeholder": "Type a language"},
        ),
        required=False,
    )
    multi_tags = forms.CharField(
        widget=ComboBox(
            suggestions=["Pizza", "Pasta", "Sushi"],
            multiple=True,
            attrs={"placeholder": "Comma-separated"},
        ),
        required=False,
    )
    city_search = forms.ChoiceField(
        widget=SearchSelect(search_url="/e2e/search/cities/"),
        required=False,
    )
    lang_search = forms.MultipleChoiceField(
        widget=MultiSelect(search_url="/e2e/search/languages/"),
        required=False,
    )
    documents = forms.FileField(
        widget=DropZone(attrs={"multiple": True}),
        required=False,
    )
    avatar = forms.ImageField(
        widget=ImageUpload,
        required=False,
    )
    bio = forms.CharField(
        widget=ValidatedTextarea(
            validate_url="/e2e/validate/bio/",
            attrs={"rows": "4", "placeholder": "Try typing 'badword'..."},
        ),
        required=False,
    )


# ---------------------------------------------------------------------------
# Server-side search and validation views
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
# Template (inline — no template files needed for e2e tests)
# ---------------------------------------------------------------------------

E2E_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>e2e test</title>
  <link rel="stylesheet" href="/static/formwork/formwork.css">
  <script src="https://unpkg.com/htmx.org@2/dist/htmx.min.js"></script>
  <script src="https://unpkg.com/idiomorph@0.7/dist/idiomorph-ext.min.js"></script>
  <script src="/static/formwork/formwork.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
  <div id="app">
    {% for form_item in forms %}
    <div class="form-section" data-form="{{ form_item.name }}">
      <h2>{{ form_item.name }}</h2>
      <form method="post" data-testid="{{ form_item.name }}"{% if form_item.multipart %} enctype="multipart/form-data"{% endif %}>
        {{ form_item.form.as_div }}
        <button type="submit">Submit</button>
      </form>
    </div>
    {% endfor %}
    {% if submitted %}
    <div id="submitted" data-form="{{ submitted_name }}">
      <p>Form submitted successfully</p>
    </div>
    {% endif %}
  </div>
</body>
</html>
"""


def _render(request: HttpRequest, form_items: list[dict], submitted_name: str = "") -> HttpResponse:
    engine = engines["django"]
    template = engine.from_string(E2E_TEMPLATE)
    context = {
        "forms": form_items,
        "submitted": bool(submitted_name),
        "submitted_name": submitted_name,
    }
    return HttpResponse(template.render(context, request))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def index(request: HttpRequest) -> HttpResponse:
    """Render all test forms on a single page."""
    submitted_name = ""

    if request.method == "POST":
        basic = BasicForm(request.POST, prefix="basic")
        widgets = WidgetsForm(request.POST, request.FILES, prefix="widgets")
        selects = SelectForm(request.POST, prefix="selects")
        advanced = AdvancedForm(request.POST, request.FILES, prefix="adv")
        for form in [basic, widgets, selects, advanced]:
            if form.is_valid():
                submitted_name = form.prefix
    else:
        basic = BasicForm(prefix="basic")
        widgets = WidgetsForm(prefix="widgets")
        selects = SelectForm(prefix="selects")
        advanced = AdvancedForm(prefix="adv")

    return _render(
        request,
        [
            {"name": "basic", "form": basic, "multipart": False},
            {"name": "widgets", "form": widgets, "multipart": True},
            {"name": "selects", "form": selects, "multipart": False},
            {"name": "advanced", "form": advanced, "multipart": True},
        ],
        submitted_name,
    )


def error_form(request: HttpRequest) -> HttpResponse:
    """Render a form pre-filled with errors."""
    form = BasicForm(data={}, prefix="err")
    form.is_valid()
    return _render(request, [{"name": "errors", "form": form, "multipart": False}])


# ---------------------------------------------------------------------------
# Morph test page — tests idiomorph full-form swap behaviour
# ---------------------------------------------------------------------------


class MorphForm(FormworkForm):
    """Form with all widget types for morph testing."""

    text = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Type here"}),
    )
    email = forms.EmailField()
    textarea = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    select = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
    )
    search_select = forms.ChoiceField(
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
    )
    multi_select = forms.MultipleChoiceField(
        choices=[("py", "Python"), ("js", "JavaScript"), ("go", "Go"), ("rs", "Rust")],
        widget=MultiSelect,
        required=False,
    )
    combobox = forms.CharField(
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust"],
            attrs={"placeholder": "Type a language"},
        ),
        required=False,
    )
    password = forms.CharField(widget=PasswordReveal(attrs={"placeholder": "Password"}))
    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(widget=Range(attrs={"min": "0", "max": "100", "step": "10"}))
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
    )
    checkbox = forms.BooleanField(required=False)
    radio = forms.ChoiceField(
        choices=[("a", "Option A"), ("b", "Option B"), ("c", "Option C")],
        widget=forms.RadioSelect,
    )


MORPH_FORM_TEMPLATE = """<form id="morph-form" method="post" hx-post="/morph/" hx-swap="morph:outerHTML" hx-target="#morph-form" hx-ext="morph">
  {% csrf_token %}
  {{ form }}
  <button type="submit">Submit</button>
</form>"""


MORPH_PAGE_TEMPLATE = (
    """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>morph test</title>
  <link rel="stylesheet" href="/static/formwork/formwork.css">
  <script src="https://unpkg.com/htmx.org@2/dist/htmx.min.js"></script>
  <script src="https://unpkg.com/idiomorph@0.7/dist/idiomorph-ext.min.js"></script>
  <script src="/static/formwork/formwork.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body>
  <div id="app">
    """
    + MORPH_FORM_TEMPLATE
    + """
  </div>
</body>
</html>"""
)


def morph_page(request: HttpRequest) -> HttpResponse:
    """Render the morph test page; handle htmx POST returning just the form."""
    engine = engines["django"]
    is_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "POST":
        form = MorphForm(request.POST, prefix="m")
        form.is_valid()
        if is_htmx:
            template = engine.from_string(MORPH_FORM_TEMPLATE)
            return HttpResponse(template.render({"form": form}, request))
    else:
        form = MorphForm(prefix="m")

    template = engine.from_string(MORPH_PAGE_TEMPLATE)
    return HttpResponse(template.render({"form": form}, request))
