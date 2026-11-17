"""Project-local widgets for the CRM example."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils.html import format_html

from django_formwork.widgets import TextInput

if TYPE_CHECKING:
    from django.forms.renderers import BaseRenderer


class WebsiteInput(TextInput):
    """A URL input with an Open link at the end of its label row."""

    input_type = "url"

    def label_links(self, name: str, value: Any, renderer: BaseRenderer | None = None) -> str:  # noqa: ARG002
        # Only a web address gets a link: a form with errors shows back whatever was posted.
        if not isinstance(value, str) or not value.startswith(("https://", "http://")):
            return ""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" title="{}" '
            'class="link link-hover inline-flex items-center gap-1">'
            '<i class="icon icon-external-link" aria-hidden="true"></i>Open</a>',
            value,
            value,
        )
