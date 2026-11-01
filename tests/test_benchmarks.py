"""Rendering benchmark for a large formwork form."""

import time

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.renderers import FormworkRenderer
from django_formwork.widgets import (
    ComboBox,
    DataList,
    FileDropZone,
    PasswordReveal,
    Range,
    Rating,
    Select,
    SelectMultiple,
    Toggle,
)

COUNTRY_CHOICES = [
    ("us", "United States"),
    ("gb", "United Kingdom"),
    ("de", "Germany"),
    ("fr", "France"),
    ("jp", "Japan"),
    ("au", "Australia"),
    ("br", "Brazil"),
    ("ca", "Canada"),
    ("in", "India"),
    ("mx", "Mexico"),
]

LANGUAGE_CHOICES = [
    ("py", "Python"),
    ("js", "JavaScript"),
    ("go", "Go"),
    ("rs", "Rust"),
    ("ts", "TypeScript"),
    ("rb", "Ruby"),
    ("java", "Java"),
    ("cs", "C#"),
]


class LargeForm(FormworkForm):
    """15-field form with a mix of standard and custom widgets."""

    name = forms.CharField(max_length=100, help_text="Your full name")
    email = forms.EmailField(help_text="Email address")
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), help_text="Message body")
    password = forms.CharField(widget=PasswordReveal, help_text="Password")
    url = forms.URLField(required=False, help_text="Website URL")
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, widget=Select, help_text="Country")
    languages = forms.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=SelectMultiple,
        required=False,
        help_text="Languages",
    )
    tags = forms.CharField(
        widget=ComboBox(suggestions=["django", "htmx", "alpine", "tailwind"]),
        required=False,
        help_text="Tags",
    )
    browser = forms.CharField(
        widget=DataList(suggestions=["Chrome", "Firefox", "Safari"]),
        required=False,
        help_text="Browser",
    )
    volume = forms.IntegerField(
        widget=Range(attrs={"min": "0", "max": "100"}),
        initial=50,
        help_text="Volume",
    )
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
        help_text="Rating",
    )
    dark_mode = forms.BooleanField(widget=Toggle, required=False, help_text="Dark mode")
    priority = forms.ChoiceField(
        choices=[("low", "Low"), ("med", "Medium"), ("high", "High")],
        widget=forms.RadioSelect,
        help_text="Priority",
    )
    attachment = forms.FileField(widget=FileDropZone, required=False, help_text="Attachment")
    agree = forms.BooleanField(help_text="I agree to the terms")


def _bench_render(form_cls, renderer, n):
    """Render n forms and return (total_seconds, avg_ms, html_length)."""
    # Warm up template cache.
    form = form_cls()
    form.renderer = renderer
    str(form)

    start = time.perf_counter()
    for _ in range(n):
        form = form_cls()
        form.renderer = renderer
        html = str(form)
    elapsed = time.perf_counter() - start
    return elapsed, (elapsed / n) * 1000, len(html)


N = 1000


@pytest.mark.benchmark
def test_benchmark_form_rendering():
    """Benchmark: render 1000 large forms."""
    renderer = FormworkRenderer()
    total, avg_ms, html_len = _bench_render(LargeForm, renderer, N)
    print(f"\n  {N} forms in {total:.2f}s ({avg_ms:.2f}ms/form, {html_len} chars)")
