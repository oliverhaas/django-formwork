from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-formwork")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from django_formwork.fields import (
    ChoiceLabel,
    FormworkModelChoiceField,
    FormworkModelMultipleChoiceField,
)
from django_formwork.forms import (
    FormworkForm,
    FormworkJinja2Form,
    FormworkJinja2ModelForm,
    FormworkModelForm,
)
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

__all__ = [
    "ChoiceLabel",
    "FormworkForm",
    "FormworkJinja2Form",
    "FormworkJinja2ModelForm",
    "FormworkJinja2Renderer",
    "FormworkModelChoiceField",
    "FormworkModelForm",
    "FormworkModelMultipleChoiceField",
    "FormworkRenderer",
    "__version__",
]
