"""FileDropZone widget."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _DropZoneMixin, _ModuleScript


class FileDropZone(_DropZoneMixin, forms.FileInput):
    """Drag-and-drop file upload zone.

    Replaces the standard file input with a styled drop zone that accepts
    dragged files or click-to-browse.  Uses Alpine.js for drag state and
    file list display.

    By default the widget accepts a single file, matching
    ``forms.FileField``.  Passing ``multiple`` in ``attrs`` opts into
    multi-file selection; the widget then submits a list of files, so it
    must be paired with a list-aware field, not a plain ``FileField``.
    Django does not ship such a field; define one following the docs topic
    "Uploading multiple files".

    ``accept`` and ``max_size`` are client-side hints only: ``accept`` filters
    the browse dialog and ``max_size`` drives a pre-upload size check in the
    widget's JavaScript.  Neither validates the upload on the server; keep the
    real checks in the field or form ``clean``.

    Usage::

        attachment = forms.FileField(widget=FileDropZone)

        # Multiple files, with client-side accept/size hints.  MultipleFileField
        # is the list-aware field from the Django docs topic above.
        docs = MultipleFileField(
            widget=FileDropZone(
                attrs={"multiple": True, "accept": ".pdf,.doc,.docx"},
                max_size=10 * 1024 * 1024,  # 10 MB
            ),
        )
    """

    template_name = "formwork/widgets/drop_zone.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/drop_zone.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        self.allow_multiple_selected = bool(attrs and attrs.get("multiple"))
        super().__init__(attrs)
        self.max_size = max_size
