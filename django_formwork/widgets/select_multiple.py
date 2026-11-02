"""Multi-select dropdown of checkbox rows (Alpine-based)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms
from django.utils.html import conditional_escape, format_html
from django.utils.translation import ngettext

from ._base import _ModuleScript, _plural_forms
from .select import SearchableSelectMixin

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.core.files.uploadedfile import UploadedFile
    from django.utils.datastructures import MultiValueDict
    from django.utils.safestring import SafeString


def _selected_text(count: int) -> str:
    return ngettext("%(count)s selected", "%(count)s selected", count)


def _pick_html(option: Mapping[str, Any]) -> SafeString:
    """What the toggle shows for one selected option, as the row does: icon, then rich label or text."""
    text = option["label_html"] or option["label"]
    return format_html("{} {}", option["icon"], text) if option["icon"] else conditional_escape(text)


class SelectMultiple(SearchableSelectMixin, forms.SelectMultiple):
    """Multi-select Alpine dropdown; a blank marker posts the name even with nothing selected.

    Server-search mode posts hidden inputs, because the list holds only one page.
    """

    template_name = "formwork/widgets/select_multiple.html"
    search_variant = "select_multiple"

    class Media:
        js = (_ModuleScript("formwork/widgets/select_multiple.js"),)

    #: Past this many selections the toggle shows a count instead of the labels.
    summary_threshold = 3

    def __init__(self, *args: Any, open_icon: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: An icon in place of DaisyUI's caret on the toggle; None keeps the caret.
        self.open_icon = open_icon

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["open_icon"] = self.open_icon
        widget["summary_threshold"] = self.summary_threshold
        # Stated positively: the endpoint renders rows without widget context, so
        # a negated guard would name them.
        widget["option_name"] = "" if widget["search_url"] else name
        selected = widget["selected_options"]
        picks = [_pick_html(option) for option in selected]
        widget["selected_picks"] = picks
        widget["selected_json"] = json.dumps(
            [[str(option["value"]), pick] for option, pick in zip(selected, picks, strict=True)]
        )
        widget["selected_count_text"] = _selected_text(len(selected)) % {"count": len(selected)}
        widget["count_text"] = _plural_forms(_selected_text)
        return context

    def value_from_datadict(
        self,
        data: Mapping[str, Any],
        files: MultiValueDict[str, UploadedFile],
        name: str,
    ) -> object:
        values = super().value_from_datadict(data, files, name)
        if not isinstance(values, list):
            return values
        return [value for value in values if value != ""]

    def value_omitted_from_data(self, data: Mapping[str, Any], files: Mapping[str, Any], name: str) -> bool:  # noqa: ARG002
        return name not in data
