"""File upload drawn as a drop area."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _FILE_ICONS_JSON, _files_selected_text, _ModuleScript, _plural_forms, _UploadHintsMixin


class FileDropzoneInput(_UploadHintsMixin, forms.FileInput):
    """Dashed drop area for one file, or for several with ``multiple`` in ``attrs``.

    Several files need ``MultipleFileField``, which cleans to a list.
    ``accept`` and ``max_size`` are client-side hints only; validate the upload in the form.
    """

    template_name = "formwork/widgets/file_dropzone.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/file_dropzone.js"),)

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
        context["widget"]["count_text"] = _plural_forms(_files_selected_text)
        context["widget"]["file_icons"] = _FILE_ICONS_JSON
        return context
