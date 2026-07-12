"""ImageDropZone widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _DropZoneMixin, _ModuleScript


class ImageDropZone(_DropZoneMixin, forms.FileInput):
    """Drag-and-drop image upload with preview.

    Like :class:`FileDropZone` but restricted to images and shows a
    thumbnail preview after selection.  Uses Alpine.js for drag state,
    preview via ``FileReader``, and a remove button.

    Usage::

        avatar = forms.ImageField(widget=ImageDropZone)
    """

    template_name = "formwork/widgets/image_upload.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/image_upload.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        defaults: dict[str, Any] = {"accept": "image/*"}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)
        self.max_size = max_size
