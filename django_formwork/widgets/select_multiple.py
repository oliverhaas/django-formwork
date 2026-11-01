"""Multi-select dropdown of checkbox rows (Alpine-based)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms
from django.utils.translation import ngettext

from ._base import _ModuleScript, _plural_forms
from .select import SearchableSelectMixin

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.core.files.uploadedfile import UploadedFile
    from django.utils.datastructures import MultiValueDict


def _selected_text(count: int) -> str:
    return ngettext("%(count)s selected", "%(count)s selected", count)


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

    def __init__(self, *args: Any, open_icon: str = "chevron-down", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
        widget["selected_labels"] = [option["label"] for option in selected]
        widget["selected_json"] = json.dumps([[str(option["value"]), option["label"]] for option in selected])
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
