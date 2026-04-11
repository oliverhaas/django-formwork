from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-formwork")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

__all__ = [
    "AsyncFormMixin",
    "AsyncModelFormMixin",
    "FormworkJinja2Renderer",
    "FormworkRenderer",
    "__version__",
]
