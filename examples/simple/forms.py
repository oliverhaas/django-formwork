from django import forms
from django.urls import reverse_lazy

from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    ComboBox,
    DataList,
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


class ContactForm(FormworkForm):
    name = forms.CharField(
        max_length=100,
        help_text="Your full name",
        widget=forms.TextInput(attrs={"placeholder": "Jane Doe"}),
    )
    email = forms.EmailField(
        help_text="We'll never share your email",
        widget=forms.EmailInput(attrs={"placeholder": "jane@example.com"}),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us what you need..."}),
        help_text="What can we help you with?",
    )
    priority = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("low", "Low"), ("medium", "Medium"), ("high", "High")],
    )


class WidgetShowcaseForm(FormworkForm):
    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Enter your password"}),
        help_text="PasswordReveal — password field with show/hide toggle button",
    )
    agree_to_terms = forms.BooleanField(
        widget=Toggle,
        required=False,
        help_text="Toggle — DaisyUI toggle switch for BooleanField",
    )
    volume = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100", "step": "10"}),
        help_text="Range — HTML range slider with min/max/step via attrs",
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        help_text="Rating — star rating, use make_choices(n) for n stars",
    )
    file_upload = forms.FileField(required=False, help_text="Standard Django FileInput")


class AllWidgetsForm(FormworkForm):
    """Demonstrates all Django widget types with DaisyUI styling."""

    # Text-like inputs — all styled via CSS @apply input
    text = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Enter text"}),
        help_text="TextInput — standard Django widget, styled via CSS",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "user@example.com"}),
        help_text="EmailInput — standard Django widget",
    )
    url = forms.URLField(
        widget=forms.URLInput(attrs={"placeholder": "https://example.com"}),
        help_text="URLInput — standard Django widget",
    )
    search = forms.CharField(
        widget=forms.SearchInput(attrs={"placeholder": "Search..."}),
        help_text="SearchInput — standard Django widget",
        required=False,
    )
    phone = forms.CharField(
        widget=forms.TelInput(attrs={"placeholder": "+1 (555) 000-0000"}),
        help_text="TelInput — standard Django widget",
        required=False,
    )
    number = forms.IntegerField(
        widget=forms.NumberInput(attrs={"placeholder": "42"}),
        help_text="NumberInput — standard Django widget",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Secret"}),
        help_text="PasswordInput — standard Django widget (no reveal toggle)",
    )
    color = forms.CharField(
        widget=forms.ColorInput,
        help_text="ColorInput — native browser color picker",
        required=False,
    )

    # Date/time inputs
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="DateInput — native date picker via type=date",
        required=False,
    )
    time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="TimeInput — native time picker via type=time",
        required=False,
    )
    datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="DateTimeInput — native datetime picker",
        required=False,
    )

    # Textarea
    textarea = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Write something..."}),
        help_text="Textarea — standard Django widget, styled via CSS",
    )

    # Select widgets
    select = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("a", "Option A"), ("b", "Option B"), ("c", "Option C")],
        help_text="Select — standard Django widget, single value",
    )
    datalist = forms.CharField(
        widget=DataList(
            datalist=["Chrome", "Firefox", "Safari", "Edge", "Opera", "Brave", "Vivaldi", "Arc"],
            attrs={"placeholder": "Type or pick a browser"},
        ),
        help_text="DataList — native <datalist>, client-side, single value, free-text",
        required=False,
    )
    search_select = forms.ChoiceField(
        choices=[
            ("", ""),
            ("nyc", "New York"),
            ("ldn", "London"),
            ("tyo", "Tokyo"),
            ("par", "Paris"),
            ("ber", "Berlin"),
            ("syd", "Sydney"),
            ("tor", "Toronto"),
            ("mum", "Mumbai"),
            ("sao", "S\u00e3o Paulo"),
            ("sin", "Singapore"),
            ("hkg", "Hong Kong"),
            ("dxb", "Dubai"),
        ],
        widget=SearchSelect,
        help_text="SearchSelect — client-side filtering, single value from choices",
        required=False,
    )
    select_multiple = forms.MultipleChoiceField(
        choices=[("python", "Python"), ("js", "JavaScript"), ("go", "Go"), ("rust", "Rust")],
        widget=MultiSelect,
        help_text="MultiSelect — client-side filtering, multiple values from choices",
        required=False,
    )
    country = forms.MultipleChoiceField(
        choices=[
            ("af", "Afghanistan"),
            ("al", "Albania"),
            ("dz", "Algeria"),
            ("ar", "Argentina"),
            ("au", "Australia"),
            ("at", "Austria"),
            ("be", "Belgium"),
            ("br", "Brazil"),
            ("ca", "Canada"),
            ("cl", "Chile"),
            ("cn", "China"),
            ("co", "Colombia"),
            ("hr", "Croatia"),
            ("cz", "Czech Republic"),
            ("dk", "Denmark"),
            ("eg", "Egypt"),
            ("fi", "Finland"),
            ("fr", "France"),
            ("de", "Germany"),
            ("gr", "Greece"),
            ("hu", "Hungary"),
            ("in", "India"),
            ("id", "Indonesia"),
            ("ie", "Ireland"),
            ("il", "Israel"),
            ("it", "Italy"),
            ("jp", "Japan"),
            ("mx", "Mexico"),
            ("nl", "Netherlands"),
            ("nz", "New Zealand"),
            ("no", "Norway"),
            ("pl", "Poland"),
            ("pt", "Portugal"),
            ("ro", "Romania"),
            ("ru", "Russia"),
            ("za", "South Africa"),
            ("kr", "South Korea"),
            ("es", "Spain"),
            ("se", "Sweden"),
            ("ch", "Switzerland"),
            ("th", "Thailand"),
            ("tr", "Turkey"),
            ("ua", "Ukraine"),
            ("gb", "United Kingdom"),
            ("us", "United States"),
        ],
        widget=MultiSelect(
            icons={
                "af": "\U0001f1e6\U0001f1eb",
                "al": "\U0001f1e6\U0001f1f1",
                "dz": "\U0001f1e9\U0001f1ff",
                "ar": "\U0001f1e6\U0001f1f7",
                "au": "\U0001f1e6\U0001f1fa",
                "at": "\U0001f1e6\U0001f1f9",
                "be": "\U0001f1e7\U0001f1ea",
                "br": "\U0001f1e7\U0001f1f7",
                "ca": "\U0001f1e8\U0001f1e6",
                "cl": "\U0001f1e8\U0001f1f1",
                "cn": "\U0001f1e8\U0001f1f3",
                "co": "\U0001f1e8\U0001f1f4",
                "hr": "\U0001f1ed\U0001f1f7",
                "cz": "\U0001f1e8\U0001f1ff",
                "dk": "\U0001f1e9\U0001f1f0",
                "eg": "\U0001f1ea\U0001f1ec",
                "fi": "\U0001f1eb\U0001f1ee",
                "fr": "\U0001f1eb\U0001f1f7",
                "de": "\U0001f1e9\U0001f1ea",
                "gr": "\U0001f1ec\U0001f1f7",
                "hu": "\U0001f1ed\U0001f1fa",
                "in": "\U0001f1ee\U0001f1f3",
                "id": "\U0001f1ee\U0001f1e9",
                "ie": "\U0001f1ee\U0001f1ea",
                "il": "\U0001f1ee\U0001f1f1",
                "it": "\U0001f1ee\U0001f1f9",
                "jp": "\U0001f1ef\U0001f1f5",
                "mx": "\U0001f1f2\U0001f1fd",
                "nl": "\U0001f1f3\U0001f1f1",
                "nz": "\U0001f1f3\U0001f1ff",
                "no": "\U0001f1f3\U0001f1f4",
                "pl": "\U0001f1f5\U0001f1f1",
                "pt": "\U0001f1f5\U0001f1f9",
                "ro": "\U0001f1f7\U0001f1f4",
                "ru": "\U0001f1f7\U0001f1fa",
                "za": "\U0001f1ff\U0001f1e6",
                "kr": "\U0001f1f0\U0001f1f7",
                "es": "\U0001f1ea\U0001f1f8",
                "se": "\U0001f1f8\U0001f1ea",
                "ch": "\U0001f1e8\U0001f1ed",
                "th": "\U0001f1f9\U0001f1ed",
                "tr": "\U0001f1f9\U0001f1f7",
                "ua": "\U0001f1fa\U0001f1e6",
                "gb": "\U0001f1ec\U0001f1e7",
                "us": "\U0001f1fa\U0001f1f8",
            },
        ),
        help_text="MultiSelect — client-side, multiple values, search auto-enabled (30+ options), with icons",
        required=False,
    )

    # Radio and checkbox
    radio = forms.ChoiceField(
        choices=[("sm", "Small"), ("md", "Medium"), ("lg", "Large")],
        widget=forms.RadioSelect,
        help_text="RadioSelect — standard Django widget, single value",
    )
    checkbox = forms.BooleanField(
        required=False,
        help_text="CheckboxInput — standard Django widget",
    )
    checkbox_multiple = forms.MultipleChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("push", "Push")],
        widget=forms.CheckboxSelectMultiple,
        help_text="CheckboxSelectMultiple — standard Django widget, multiple values",
        required=False,
    )

    # File
    file = forms.FileField(
        required=False,
        help_text="FileInput — standard Django widget, styled via CSS",
    )

    # Custom formwork widgets
    toggle = forms.BooleanField(
        widget=Toggle,
        required=False,
        help_text="Toggle — DaisyUI toggle switch for BooleanField",
    )
    range_slider = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100", "step": "10"}),
        help_text="Range — HTML range slider with min/max/step",
    )
    star_rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        help_text="Rating — star rating, use make_choices(n) for n stars",
    )
    password_reveal = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Reveal me"}),
        help_text="PasswordReveal — password with show/hide toggle",
    )


class RegistrationForm(FormworkForm):
    """Two-column layout demo — rendered with grid grid-cols-2 on the <form>."""

    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Jane"}),
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Doe"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "jane@example.com"}),
        help_text="We'll send a confirmation link",
    )
    phone = forms.CharField(
        widget=forms.TelInput(attrs={"placeholder": "+1 (555) 000-0000"}),
        required=False,
        help_text="Optional, for account recovery",
    )
    password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Min. 8 characters"}),
        help_text="At least 8 characters",
    )
    confirm_password = forms.CharField(
        widget=PasswordReveal(attrs={"placeholder": "Repeat password"}),
    )


class ErrorStatesForm(FormworkForm):
    """Shows every widget type in its error state (server-side validation)."""

    text = forms.CharField(help_text="Required text input")
    email = forms.EmailField(help_text="Must be a valid email")
    textarea = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), help_text="Required textarea")
    select = forms.ChoiceField(
        choices=[("", "Select\u2026"), ("a", "A"), ("b", "B")],
        help_text="Required select",
    )
    search_select = forms.ChoiceField(
        choices=[("", ""), ("a", "Alpha"), ("b", "Beta")],
        widget=SearchSelect,
        help_text="Required search select",
    )
    select_multiple = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B"), ("c", "C")],
        widget=MultiSelect,
        help_text="Required multi-select",
    )
    radio = forms.ChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=forms.RadioSelect,
        help_text="Required radio group",
    )
    checkbox = forms.BooleanField(help_text="Must be checked")
    checkbox_multiple = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=forms.CheckboxSelectMultiple,
        help_text="Required checkbox group",
    )
    file = forms.FileField(help_text="Required file")
    toggle = forms.BooleanField(widget=Toggle, help_text="Must be toggled on")
    range_slider = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100"}),
        help_text="Required range",
    )
    star_rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        help_text="Required rating",
    )
    password_reveal = forms.CharField(
        widget=PasswordReveal,
        help_text="Required password",
    )


class AdvancedWidgetsForm(FormworkForm):
    """Demonstrates new formwork widgets: uploads, combobox, validated textarea."""

    favorite_language = forms.CharField(
        label="Favorite language",
        widget=ComboBox(
            suggestions=["Python", "JavaScript", "Go", "Rust", "TypeScript"],
            attrs={"placeholder": "Type a language"},
        ),
        help_text="ComboBox — client-side filtering, single value, free-text input",
        required=False,
    )
    toppings = forms.CharField(
        widget=ComboBox(
            suggestions=["Pepperoni", "Mushrooms", "Olives", "Onions", "Peppers"],
            multiple=True,
            attrs={"placeholder": "Type toppings, comma-separated"},
        ),
        help_text="ComboBox(multiple=True) — client-side filtering, toggle selection, comma-separated free-text",
        required=False,
    )
    city = forms.ChoiceField(
        widget=SearchSelect(
            search_url=reverse_lazy("city-search"),
            icons={
                "nyc": "\U0001f5fd",
                "ldn": "\U0001f1ec\U0001f1e7",
                "tyo": "\U0001f5fc",
                "par": "\U0001f1eb\U0001f1f7",
            },
        ),
        help_text="SearchSelect(search_url=...) — server-side search via htmx, single value, with icons",
        required=False,
    )
    languages = forms.MultipleChoiceField(
        widget=MultiSelect(search_url=reverse_lazy("language-search")),
        help_text="MultiSelect(search_url=...) — server-side search via htmx, multiple values",
        required=False,
    )
    documents = forms.FileField(
        widget=DropZone(attrs={"multiple": True, "accept": ".pdf,.doc,.docx"}),
        help_text="DropZone — drag-and-drop, multiple files, accept validation (.pdf, .doc, .docx)",
        required=False,
    )
    avatar = forms.ImageField(
        widget=ImageUpload(attrs={"accept": "image/png,image/jpeg"}),
        help_text="ImageUpload — drag-and-drop image, PNG and JPEG only, with preview",
        required=False,
    )
    bio = forms.CharField(
        widget=ValidatedTextarea(
            validate_url=reverse_lazy("validate-bio"),
            attrs={"rows": "4", "placeholder": "Try typing 'badword' or 'spam'..."},
        ),
        help_text="ValidatedTextarea(validate_url=...) — server-side validation via htmx, highlights errors",
        required=False,
    )
