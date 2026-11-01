"""Image upload drawn as a drop area with a preview."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms
from django.forms.widgets import FILE_INPUT_CONTRADICTION, CheckboxInput

from ._base import _DropZoneMixin, _ModuleScript

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.core.files.uploadedfile import UploadedFile
    from django.utils.datastructures import MultiValueDict


class ImageDropzoneInput(_DropZoneMixin, forms.FileInput):
    """Dashed drop area that previews the stored image, with a button that clears it.

    ``preview_url`` replaces the stored file's URL; ``""`` hides the preview. ``accept`` and
    ``max_size`` are client-side hints only.
    """

    template_name = "formwork/widgets/image_dropzone.html"

    class Media:
        js = (_ModuleScript("formwork/widgets/image_dropzone.js"),)

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
        hint: str = "",
        preview_url: str | None = None,
    ) -> None:
        super().__init__({"accept": "image/*", **(attrs or {})})
        self.max_size = max_size
        self.hint = hint
        self.preview_url = preview_url

    def clear_checkbox_name(self, name: str) -> str:
        return f"clear_{name}"

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # Render-time attrs can carry both, so a view can preview a file it has not stored yet.
        widget["hint"] = widget["attrs"].pop("hint", self.hint)
        preview_url = widget["attrs"].pop("preview_url", self.preview_url)
        if preview_url is None:
            preview_url = getattr(value, "url", "") if value else ""
        widget["preview_url"] = preview_url
        widget["clear_name"] = self.clear_checkbox_name(name)
        return context

    def value_from_datadict(self, data: Mapping[str, Any], files: MultiValueDict[str, UploadedFile], name: str) -> Any:  # noqa: ANN401
        upload = super().value_from_datadict(data, files, name)
        if not self.is_required and CheckboxInput().value_from_datadict(data, files, self.clear_checkbox_name(name)):
            # False clears the stored file, as with ClearableFileInput; a new upload contradicts it.
            return FILE_INPUT_CONTRADICTION if upload else False
        return upload

    def value_omitted_from_data(
        self, data: Mapping[str, Any], files: MultiValueDict[str, UploadedFile], name: str
    ) -> bool:
        return super().value_omitted_from_data(data, files, name) and not data.get(self.clear_checkbox_name(name))
