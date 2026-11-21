"""Multi-select dropdown of checkbox rows (Alpine-based)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.translation import ngettext

from ._base import _PLURAL_SAMPLES, _ModuleScript, _plural_forms, _StubMixin
from .select import SearchableSelectMixin, _trigger_context, label_extras

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


class SelectMultiple(_StubMixin, SearchableSelectMixin, forms.SelectMultiple):
    """Multi-select Alpine dropdown; a blank marker posts the name even with nothing selected.

    Server-search mode posts hidden inputs, because the list holds only one page.
    """

    template_name = "formwork/widgets/select_multiple.html"
    #: The option rows alone, which a server search answers with.
    option_list_template_name = "formwork/widgets/partials/select_multiple_options.html"
    stub_template_name = "formwork/widgets/select_multiple_stub.html"
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
        # Stated positively: the endpoint renders rows without widget context, so
        # a negated guard would name them. A searched list and the rows of a table
        # column hold other rows than the selected ones, so hidden inputs post those.
        widget["option_name"] = "" if widget["search_url"] or widget["options_template_id"] else name
        self._toggle_context(widget)
        widget["selected_json"] = json.dumps(
            [
                [str(option["value"]), pick]
                for option, pick in zip(widget["selected_options"], widget["selected_picks"], strict=True)
            ]
        )
        widget["count_text"] = _plural_forms(_selected_text)
        widget["autowidth_copy"] = self.autowidth_copy(widget)
        return context

    def get_stub_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:  # noqa: ANN401
        if self.stub_copy is None:
            # A row with choices of its own loads them to size its stub, as the full select does.
            return self.get_context(name, value, attrs)
        # forms.SelectMultiple's own context builds every option; the stub shows the selected ones alone.
        context = forms.Widget.get_context(self, name, value, attrs)
        widget = context["widget"]
        values = {str(value) for value in widget["value"] if value}
        widget["selected_options"] = [
            {"value": choice, "label": str(label), **label_extras(label, badges=self.badges)}
            for choice, label in self._labels_of(values)
        ]
        _trigger_context(widget)
        self._toggle_context(widget)
        widget["trigger_placeholder"] = widget["attrs"].get("placeholder", "")
        widget["autowidth_copy"] = self.stub_copy()
        return context

    def autowidth_copy(self, widget: Mapping[str, Any]) -> str:
        # The toggle of the full select sizes itself by the label text, also with badges.
        labels = super().autowidth_copy({**widget, "badges": False})
        count = len(widget["options"])
        if not labels or count <= self.summary_threshold:
            return labels
        # Past the threshold the toggle shows the count: each plural form, with the most digits the count can have.
        counts = dict.fromkeys(_selected_text(sample) % {"count": count} for sample in _PLURAL_SAMPLES.values())
        return format_html_join("\n", "{}", ((line,) for line in (labels, *counts)))

    def _toggle_context(self, widget: dict[str, Any]) -> None:
        """What the closed toggle shows: the selected options, or their count past ``summary_threshold``."""
        selected = widget["selected_options"]
        widget["open_icon"] = self.open_icon
        widget["summary_threshold"] = self.summary_threshold
        widget["selected_picks"] = [_pick_html(option) for option in selected]
        widget["selected_count_text"] = _selected_text(len(selected)) % {"count": len(selected)}

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
