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

# FormworkModel lives in django_formwork.models and is not re-exported here:
# eagerly importing it would force the Django apps registry to be ready before
# `import django_formwork` succeeds.  Users import it from the submodule.

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
