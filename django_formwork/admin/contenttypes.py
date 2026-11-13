"""Inlines for a model that points at its parent through a ``GenericForeignKey``.

The classes match ``django.contrib.contenttypes.admin``'s: ``ct_field`` and ``ct_fk_field``
name the content type and the object ID fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.forms import BaseGenericInlineFormSet, generic_inlineformset_factory

from django_formwork.admin.options import InlineModelAdmin
from django_formwork.formsets import _BatchedUniquenessMixin
from django_formwork.tables import TableRenderMixin

if TYPE_CHECKING:
    from django.forms.models import BaseModelFormSet

__all__ = [
    "FormworkBaseGenericInlineFormSet",
    "GenericInlineModelAdmin",
    "GenericStackedInline",
    "GenericTabularInline",
]


class FormworkBaseGenericInlineFormSet(TableRenderMixin, _BatchedUniquenessMixin, BaseGenericInlineFormSet):
    """Django's generic inline formset, with the batched uniqueness checks of formwork's formsets."""


class GenericInlineModelAdmin(InlineModelAdmin):
    """Rows of a related model whose ``GenericForeignKey`` points at the parent."""

    ct_field = "content_type"
    ct_fk_field = "object_id"
    formset: type[BaseModelFormSet[Any, Any]] = FormworkBaseGenericInlineFormSet

    def _formset_factory(self, defaults: dict[str, Any]) -> type[BaseModelFormSet[Any, Any]]:
        defaults.pop("fk_name", None)
        options: dict[str, Any] = {"ct_field": self.ct_field, "fk_field": self.ct_fk_field, **defaults}
        return generic_inlineformset_factory(self.model, **options)


class GenericStackedInline(GenericInlineModelAdmin):
    layout = "stacked"


class GenericTabularInline(GenericInlineModelAdmin):
    layout = "tabular"
