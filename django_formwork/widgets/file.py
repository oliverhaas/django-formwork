"""File upload widgets: FileDropZone, ImageDropZone, ValidatedTextarea."""

from __future__ import annotations

from typing import Any

from django import forms

from ._base import _DropZoneMixin


class FileDropZone(_DropZoneMixin, forms.FileInput):
    """Drag-and-drop file upload zone."""

    template_name = "formwork/widgets/drop_zone.html"
    allow_multiple_selected = True

    def __init__(self, attrs: dict[str, Any] | None = None, *, max_size: int | None = None) -> None:
        super().__init__(attrs)
        self.max_size = max_size


class ImageDropZone(_DropZoneMixin, forms.FileInput):
    """Drag-and-drop image upload with preview."""

    template_name = "formwork/widgets/image_upload.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, max_size: int | None = None) -> None:
        defaults: dict[str, Any] = {"accept": "image/*"}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)
        self.max_size = max_size


class ValidatedTextarea(forms.Textarea):
    """Textarea with server-side validation and word highlighting."""

    template_name = "formwork/widgets/validated_textarea.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, validate_url: str | None = None) -> None:
        super().__init__(attrs)
        self.validate_url = validate_url

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["validate_url"] = self.validate_url
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        return context
