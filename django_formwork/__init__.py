from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-formwork")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.fields import (
    FormworkChoiceLabel,
    FormworkModelChoiceField,
    FormworkModelMultipleChoiceField,
)
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

__all__ = [
    "AsyncFormMixin",
    "AsyncModelFormMixin",
    "FormworkChoiceLabel",
    "FormworkJinja2Renderer",
    "FormworkModelChoiceField",
    "FormworkModelMultipleChoiceField",
    "FormworkRenderer",
    "__version__",
]
