"""PasswordReveal widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _ModuleScript


class PasswordReveal(forms.PasswordInput):
    """Password input with a show/hide toggle button.

    Wraps the input in a ``<label class="password-reveal">`` container with
    a toggle button.  Uses Alpine.js for the reveal functionality.  DaisyUI's
    ``.input`` styling is applied via CSS ``@apply`` on the label, so the
    direct-child CSS selector for text inputs doesn't match it.

    Usage::

        password = forms.CharField(widget=PasswordReveal)
    """

    template_name = "formwork/widgets/password_reveal.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/password_reveal.js"),)

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, render_value=False)
