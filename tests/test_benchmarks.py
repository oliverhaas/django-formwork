"""Rendering benchmarks: DTL vs Jinja2 form rendering performance."""

import time

import pytest
from django import forms

from django_formwork.forms import FormworkForm, FormworkJinja2Form
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer
from django_formwork.widgets import (
    ComboBox,
    DataList,
    FileDropZone,
    MultiSelect,
    PasswordReveal,
    Range,
    Rating,
    SearchSelect,
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
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, widget=SearchSelect, help_text="Country")
    languages = forms.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=MultiSelect,
        required=False,
        help_text="Languages",
    )
    tags = forms.CharField(
        widget=ComboBox(suggestions=["django", "htmx", "alpine", "tailwind"]),
        required=False,
        help_text="Tags",
    )
    browser = forms.CharField(
        widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
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


class LargeJinja2Form(FormworkJinja2Form):
    """Same form but with Jinja2 renderer."""

    name = forms.CharField(max_length=100, help_text="Your full name")
    email = forms.EmailField(help_text="Email address")
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), help_text="Message body")
    password = forms.CharField(widget=PasswordReveal, help_text="Password")
    url = forms.URLField(required=False, help_text="Website URL")
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, widget=SearchSelect, help_text="Country")
    languages = forms.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=MultiSelect,
        required=False,
        help_text="Languages",
    )
    tags = forms.CharField(
        widget=ComboBox(suggestions=["django", "htmx", "alpine", "tailwind"]),
        required=False,
        help_text="Tags",
    )
    browser = forms.CharField(
        widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
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
def test_benchmark_dtl_rendering():
    """Benchmark: render 1000 large forms with DTL renderer."""
    renderer = FormworkRenderer()
    total, avg_ms, html_len = _bench_render(LargeForm, renderer, N)
    print(f"\n  DTL: {N} forms in {total:.2f}s ({avg_ms:.2f}ms/form, {html_len} chars)")


@pytest.mark.benchmark
def test_benchmark_jinja2_rendering():
    """Benchmark: render 1000 large forms with Jinja2 renderer."""
    renderer = FormworkJinja2Renderer()
    total, avg_ms, html_len = _bench_render(LargeJinja2Form, renderer, N)
    print(f"\n  Jinja2: {N} forms in {total:.2f}s ({avg_ms:.2f}ms/form, {html_len} chars)")


@pytest.mark.benchmark
def test_benchmark_comparison():
    """Benchmark: DTL vs Jinja2 head-to-head comparison."""
    dtl_renderer = FormworkRenderer()
    j2_renderer = FormworkJinja2Renderer()

    dtl_total, dtl_avg, dtl_len = _bench_render(LargeForm, dtl_renderer, N)
    j2_total, j2_avg, j2_len = _bench_render(LargeJinja2Form, j2_renderer, N)

    results = [
        ("DTL", dtl_total, dtl_avg, dtl_len),
        ("Jinja2", j2_total, j2_avg, j2_len),
    ]
    fastest = min(results, key=lambda r: r[1])

    print(f"\n  === Renderer comparison: {N} renders of 15-field form ===")
    for name, total, avg, length in results:
        ratio = total / fastest[1]
        marker = " <-- fastest" if name == fastest[0] else f" ({ratio:.2f}x slower)"
        print(f"  {name:12s} {total:.2f}s ({avg:.2f}ms/form, {length} chars){marker}")
