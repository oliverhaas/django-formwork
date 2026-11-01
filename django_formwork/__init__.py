"""django-formwork public API: every public name resolves lazily from the
package root (PEP 562), keeping ``import django_formwork`` free of
import-time Django requirements.  Submodule imports keep working.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

try:
    __version__ = version("django-formwork")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

if TYPE_CHECKING:
    from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
    from django_formwork.boundfield import FormworkBoundField
    from django_formwork.fields import (
        FormworkModelChoiceField,
        FormworkModelMultipleChoiceField,
    )
    from django_formwork.forms import (
        FormworkForm,
        FormworkModelForm,
        FormworkModelFormMetaclass,
    )
    from django_formwork.formsets import (
        FormworkBaseInlineFormSet,
        FormworkBaseModelFormSet,
        formwork_inlineformset_factory,
        formwork_modelformset_factory,
    )
    from django_formwork.models import FormworkModel
    from django_formwork.renderers import FormworkRenderer
    from django_formwork.tables import FormworkRowSaveMixin
    from django_formwork.views import (
        FormworkAutoSearchView,
        FormworkSearchView,
        FormworkValidateView,
    )
    from django_formwork.widgets.select import ChoiceLabel

#: Public name -> defining submodule, resolved lazily by ``__getattr__``.
_EXPORTS = {
    "AsyncFormMixin": "django_formwork.async_forms",
    "AsyncModelFormMixin": "django_formwork.async_forms",
    "ChoiceLabel": "django_formwork.widgets.select",
    "FormworkAutoSearchView": "django_formwork.views",
    "FormworkBaseInlineFormSet": "django_formwork.formsets",
    "FormworkBaseModelFormSet": "django_formwork.formsets",
    "FormworkBoundField": "django_formwork.boundfield",
    "FormworkForm": "django_formwork.forms",
    "FormworkModel": "django_formwork.models",
    "FormworkModelChoiceField": "django_formwork.fields",
    "FormworkModelForm": "django_formwork.forms",
    "FormworkModelFormMetaclass": "django_formwork.forms",
    "FormworkModelMultipleChoiceField": "django_formwork.fields",
    "FormworkRenderer": "django_formwork.renderers",
    "FormworkRowSaveMixin": "django_formwork.tables",
    "FormworkSearchView": "django_formwork.views",
    "FormworkValidateView": "django_formwork.views",
    "formwork_inlineformset_factory": "django_formwork.formsets",
    "formwork_modelformset_factory": "django_formwork.formsets",
}

__all__ = [
    "AsyncFormMixin",
    "AsyncModelFormMixin",
    "ChoiceLabel",
    "FormworkAutoSearchView",
    "FormworkBaseInlineFormSet",
    "FormworkBaseModelFormSet",
    "FormworkBoundField",
    "FormworkForm",
    "FormworkModel",
    "FormworkModelChoiceField",
    "FormworkModelForm",
    "FormworkModelFormMetaclass",
    "FormworkModelMultipleChoiceField",
    "FormworkRenderer",
    "FormworkRowSaveMixin",
    "FormworkSearchView",
    "FormworkValidateView",
    "__version__",
    "formwork_inlineformset_factory",
    "formwork_modelformset_factory",
]


def __getattr__(name: str) -> Any:  # noqa: ANN401 (lazy exports have heterogeneous types)
    module_path = _EXPORTS.get(name)
    if module_path is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    from importlib import import_module

    value = getattr(import_module(module_path), name)
    # Cache on the module so subsequent lookups skip __getattr__.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_EXPORTS})
