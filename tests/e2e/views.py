"""Views for e2e testing — one form with all widget types."""

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
# Test form — every widget type in one form
# ---------------------------------------------------------------------------


class WidgetForm(FormworkForm):
    """Comprehensive form with all widget types for e2e testing."""

    # Standard Django widgets (required — test error states on empty submit)
    text = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Type here"}),
        help_text="Enter some text",
    )
    email = forms.EmailField()
    textarea = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    select = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
    )
    radio = forms.ChoiceField(
        choices=[("x", "Option X"), ("y", "Option Y"), ("z", "Option Z")],
        widget=forms.RadioSelect,
    )
    checkbox = forms.BooleanField()
    file = forms.FileField(required=False)

    # Custom formwork widgets
    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100", "step": "10"}),
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
    )
    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Password"}),
    )
    datalist = forms.CharField(
        widget=DataList(
            datalist=["Alpha", "Beta", "Gamma", "Delta"],
            attrs={"placeholder": "Type or pick"},
        ),
        required=False,
    )

    # Dropdown widgets (static choices)
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
        choices=[
            ("py", "Python"),
            ("js", "JavaScript"),
            ("go", "Go"),
            ("rs", "Rust"),
        ],
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
    combobox_multi = forms.CharField(
        widget=ComboBox(
            suggestions=["Pizza", "Pasta", "Sushi"],
            multiple=True,
            attrs={"placeholder": "Comma-separated"},
        ),
        required=False,
    )

    # Htmx-powered dropdown widgets
    search_select_htmx = forms.ChoiceField(
        widget=SearchSelect(search_url="/e2e/search/cities/"),
        required=False,
    )
    multi_select_htmx = forms.MultipleChoiceField(
        widget=MultiSelect(search_url="/e2e/search/languages/"),
        required=False,
    )

    # Upload widgets
    dropzone = forms.FileField(
        widget=FileDropZone(attrs={"multiple": True}),
        required=False,
    )
    avatar = forms.ImageField(
        widget=ImageDropZone,
        required=False,
    )

    # Validated textarea
    bio = forms.CharField(
        widget=ValidatedTextarea(
            validate_url="/e2e/validate/bio/",
            attrs={"rows": "3", "placeholder": "Try typing 'badword'..."},
        ),
        required=False,
    )


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
# Templates (inline — no template files needed for e2e tests)
# ---------------------------------------------------------------------------

FORM_TEMPLATE = """<form id="widget-form" method="post" enctype="multipart/form-data" \
hx-post="/" hx-swap="morph:outerHTML" hx-target="#widget-form" hx-ext="morph">
  {% csrf_token %}
  {{ form }}
  <button type="submit">Submit</button>
</form>"""

PAGE_TEMPLATE = (
    """<!DOCTYPE html>
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
    """
    + FORM_TEMPLATE
    + """
  </div>
</body>
</html>"""
)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def index(request: HttpRequest) -> HttpResponse:
    """Render the widget test form; handle htmx POST for morph."""
    engine = engines["django"]
    is_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "POST":
        form = WidgetForm(request.POST, request.FILES)
        form.is_valid()
        if is_htmx:
            template = engine.from_string(FORM_TEMPLATE)
            return HttpResponse(template.render({"form": form}, request))
    else:
        form = WidgetForm()

    template = engine.from_string(PAGE_TEMPLATE)
    return HttpResponse(template.render({"form": form}, request))
