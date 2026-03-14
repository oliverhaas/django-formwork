from django.shortcuts import render
from forms import (
    AdvancedWidgetsForm,
    AllWidgetsForm,
    ContactForm,
    ErrorStatesForm,
    RegistrationForm,
    WidgetShowcaseForm,
)

from django_formwork.views import FormworkSearchView, FormworkValidateView

# ---------------------------------------------------------------------------
# Server-side search views
# ---------------------------------------------------------------------------

CITIES = [
    {"value": "nyc", "label": "New York", "icon": "\U0001f5fd"},
    {"value": "ldn", "label": "London", "icon": "\U0001f1ec\U0001f1e7"},
    {"value": "tyo", "label": "Tokyo", "icon": "\U0001f5fc"},
    {"value": "par", "label": "Paris", "icon": "\U0001f1eb\U0001f1f7"},
    {"value": "ber", "label": "Berlin", "icon": "\U0001f1e9\U0001f1ea"},
    {"value": "syd", "label": "Sydney", "icon": "\U0001f1e6\U0001f1fa"},
    {"value": "tor", "label": "Toronto", "icon": "\U0001f1e8\U0001f1e6"},
    {"value": "mum", "label": "Mumbai", "icon": "\U0001f1ee\U0001f1f3"},
    {"value": "sao", "label": "S\u00e3o Paulo", "icon": "\U0001f1e7\U0001f1f7"},
    {"value": "sin", "label": "Singapore", "icon": "\U0001f1f8\U0001f1ec"},
]

LANGUAGES = [
    {"value": "py", "label": "Python"},
    {"value": "js", "label": "JavaScript"},
    {"value": "ts", "label": "TypeScript"},
    {"value": "go", "label": "Go"},
    {"value": "rs", "label": "Rust"},
    {"value": "rb", "label": "Ruby"},
    {"value": "java", "label": "Java"},
    {"value": "cs", "label": "C#"},
    {"value": "cpp", "label": "C++"},
    {"value": "swift", "label": "Swift"},
    {"value": "kt", "label": "Kotlin"},
    {"value": "php", "label": "PHP"},
    {"value": "zig", "label": "Zig"},
    {"value": "elixir", "label": "Elixir"},
    {"value": "scala", "label": "Scala"},
    {"value": "dart", "label": "Dart"},
    {"value": "lua", "label": "Lua"},
    {"value": "r", "label": "R"},
    {"value": "julia", "label": "Julia"},
    {"value": "haskell", "label": "Haskell"},
    {"value": "clj", "label": "Clojure"},
    {"value": "elm", "label": "Elm"},
    {"value": "ocaml", "label": "OCaml"},
    {"value": "erlang", "label": "Erlang"},
]


class CitySearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):  # noqa: ARG002
        if not query:
            return CITIES
        return [c for c in CITIES if query.lower() in c["label"].lower()]


class LanguageSearchView(FormworkSearchView):
    def get_results(self, query, **kwargs):  # noqa: ARG002
        if not query:
            return LANGUAGES
        return [lang for lang in LANGUAGES if query.lower() in lang["label"].lower()]


# ---------------------------------------------------------------------------
# Server-side validation view
# ---------------------------------------------------------------------------

BANNED_WORDS = ["badword", "spam", "lorem"]


class BioValidateView(FormworkValidateView):
    def get_errors(self, text, **kwargs):  # noqa: ARG002
        errors = []
        lower = text.lower()
        for word in BANNED_WORDS:
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
# DaisyUI themes
# ---------------------------------------------------------------------------

DAISYUI_THEMES = [
    ("light", "Light"),
    ("dark", "Dark"),
    ("cupcake", "Cupcake"),
    ("bumblebee", "Bumblebee"),
    ("emerald", "Emerald"),
    ("corporate", "Corporate"),
    ("synthwave", "Synthwave"),
    ("retro", "Retro"),
    ("cyberpunk", "Cyberpunk"),
    ("valentine", "Valentine"),
    ("halloween", "Halloween"),
    ("garden", "Garden"),
    ("forest", "Forest"),
    ("aqua", "Aqua"),
    ("lofi", "Lo-fi"),
    ("pastel", "Pastel"),
    ("fantasy", "Fantasy"),
    ("wireframe", "Wireframe"),
    ("black", "Black"),
    ("luxury", "Luxury"),
    ("dracula", "Dracula"),
    ("cmyk", "CMYK"),
    ("autumn", "Autumn"),
    ("business", "Business"),
    ("acid", "Acid"),
    ("lemonade", "Lemonade"),
    ("night", "Night"),
    ("coffee", "Coffee"),
    ("winter", "Winter"),
    ("dim", "Dim"),
    ("nord", "Nord"),
    ("sunset", "Sunset"),
]


# ---------------------------------------------------------------------------
# Main page view
# ---------------------------------------------------------------------------


def index(request):
    is_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "POST":
        contact_form = ContactForm(request.POST, prefix="contact")
        contact_form.is_valid()

        # htmx morph — return just the contact form partial
        if is_htmx:
            return render(
                request,
                "partials/contact_form.html",
                {"contact_form": contact_form},
            )

        showcase_form = WidgetShowcaseForm(request.POST, request.FILES, prefix="showcase")
        all_widgets_form = AllWidgetsForm(request.POST, request.FILES, prefix="all")
        advanced_form = AdvancedWidgetsForm(request.POST, request.FILES, prefix="adv")
        showcase_form.is_valid()
        all_widgets_form.is_valid()
        advanced_form.is_valid()
    else:
        contact_form = ContactForm(prefix="contact")
        showcase_form = WidgetShowcaseForm(prefix="showcase")
        all_widgets_form = AllWidgetsForm(prefix="all")
        advanced_form = AdvancedWidgetsForm(prefix="adv")

    registration_form = RegistrationForm(prefix="reg")

    # Always render error form pre-bound with empty data to show error states.
    error_form = ErrorStatesForm(data={}, prefix="err")
    error_form.is_valid()

    field_group_form = ContactForm(prefix="fg")
    mixed_form = ContactForm(prefix="mix")

    return render(
        request,
        "index.html",
        {
            "contact_form": contact_form,
            "field_group_form": field_group_form,
            "registration_form": registration_form,
            "mixed_form": mixed_form,
            "showcase_form": showcase_form,
            "all_widgets_form": all_widgets_form,
            "advanced_form": advanced_form,
            "error_form": error_form,
            "themes": DAISYUI_THEMES,
        },
    )
