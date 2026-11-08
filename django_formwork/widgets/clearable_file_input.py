"""File upload in one input row, with the stored file and a button that clears it."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from django import forms

from ._base import _FILE_ICONS, _FILE_ICONS_JSON, _files_selected_text, _ModuleScript, _plural_forms, _UploadHintsMixin

_ICON_BY_EXTENSION = {extension: icon for icon, extensions in _FILE_ICONS.items() for extension in extensions.split()}


class ClearableFileInput(_UploadHintsMixin, forms.ClearableFileInput):
    """Django's ``ClearableFileInput`` in one input row, with an icon for the type of file.

    ``multiple`` in ``attrs`` picks several files, which need ``MultipleFileField``.
    ``accept`` and ``max_size`` are client-side hints only; validate the upload in the form.
    """

    template_name = "formwork/widgets/clearable_file_input.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/clearable_file_input.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        self.allow_multiple_selected = bool(attrs and attrs.get("multiple"))
        super().__init__(attrs)
        self.max_size = max_size

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # Django passes the clear box's state in the attrs, which the template renders on the file input.
        widget["clear_checked"] = widget["attrs"].pop("checked")
        widget["count_text"] = _plural_forms(_files_selected_text)
        widget["file_icons"] = _FILE_ICONS_JSON
        if widget["is_initial"]:
            widget["file_name"] = str(value).rsplit("/", 1)[-1]
            extension = PurePosixPath(widget["file_name"]).suffix[1:].lower()
            widget["file_icon"] = _ICON_BY_EXTENSION.get(extension, "file")
        return context
