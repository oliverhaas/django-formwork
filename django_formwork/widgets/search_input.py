"""SearchInput widget."""

from __future__ import annotations

from django import forms


class SearchInput(forms.SearchInput):
    """Search input wrapped in a DaisyUI ``.input`` with a leading magnifier.

    A drop-in for ``forms.SearchInput`` that opts into formwork styling. It
    renders its own template rather than shadowing Django's built-in
    ``search.html``, so the admin and third-party forms keep their stock search
    box: you get the magnifier only where you set this widget.

    Usage::

        q = forms.CharField(widget=SearchInput(attrs={"placeholder": "Search…"}))
    """

    template_name = "formwork/widgets/search_input.html"
