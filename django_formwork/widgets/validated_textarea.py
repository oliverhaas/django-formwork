"""ValidatedTextarea widget."""

from __future__ import annotations

from typing import Any

from django import forms


class ValidatedTextarea(forms.Textarea):
    """Textarea with server-side validation and word highlighting.

    Renders a textarea with a highlight overlay.  When ``validate_url``
    is provided, htmx sends the text to the server after a debounce.
    The server returns highlighted HTML (with ``<mark>`` tags around
    errors) that displays beneath the transparent textarea, plus error
    messages via out-of-band swap.

    Without ``validate_url``, renders as a normal textarea.

    Usage::

        content = forms.CharField(
            widget=ValidatedTextarea(validate_url=reverse_lazy("validate-text")),
        )
    """

    template_name = "formwork/widgets/validated_textarea.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, validate_url: str | None = None) -> None:
        super().__init__(attrs)
        self.validate_url = validate_url

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["validate_url"] = self.validate_url
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        return context
