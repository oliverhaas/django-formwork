"""File upload drawn as a drop area."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _DropZoneMixin, _ModuleScript


class FileDropzoneInput(_DropZoneMixin, forms.FileInput):
    """Dashed drop area for one file, or for several with ``multiple`` in ``attrs``.

    Several files need a list-aware field, as in Django's "Uploading multiple files" topic.
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
