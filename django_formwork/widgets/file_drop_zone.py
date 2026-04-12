"""FileDropZone widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _DropZoneMixin


class FileDropZone(_DropZoneMixin, forms.FileInput):
    """Drag-and-drop file upload zone.

    Replaces the standard file input with a styled drop zone that accepts
    dragged files or click-to-browse.  Uses Alpine.js for drag state and
    file list display.

    Usage::

        attachment = forms.FileField(widget=FileDropZone)

        # Multiple files with type and size restrictions:
        docs = forms.FileField(
            widget=FileDropZone(
                attrs={"multiple": True, "accept": ".pdf,.doc,.docx"},
                max_size=10 * 1024 * 1024,  # 10 MB
            ),
        )
    """

    template_name = "formwork/widgets/drop_zone.html"
    allow_multiple_selected = True

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        super().__init__(attrs)
        self.max_size = max_size
