from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-formwork")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from django_formwork.renderers import FormworkRenderer

__all__ = ["FormworkRenderer", "__version__"]
