"""The formwork widget each model field gets on an admin form, and the relation search.

One search serves every relation: its params name the site, the model and the field,
so the related admin's queryset, permissions and ``search_fields`` decide the rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import models
from django.http import Http404

from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    ClearableFileInput,
    DatePicker,
    Select,
    SelectMultiple,
    Textarea,
    TextInput,
    ToggleInput,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

__all__ = ["FORMFIELD_FOR_DBFIELD_DEFAULTS", "RELATION_SEARCH_KEY", "relation_queryset", "relation_widget"]


def relation_queryset(request: HttpRequest, *, site: str, model: str, field: str) -> QuerySet[Any]:
    """The rows a relation's dropdown offers: the related admin's list, searched by its ``search_fields``."""
    # Deferred: sites imports options, which imports this module.
    from django_formwork.admin.sites import NotRegistered, get_site

    admin_site = get_site(site)
    if admin_site is None or not admin_site.has_permission(request):
        raise PermissionDenied
    try:
        source = apps.get_model(model)
        source_field = source._meta.get_field(field)
    except LookupError, ValueError, FieldDoesNotExist:
        raise Http404 from None
    if not admin_site.is_registered(source) or source_field.remote_field is None:
        raise Http404
    try:
        model_admin = admin_site.get_model_admin(source_field.remote_field.model)
    except NotRegistered:
        raise Http404 from None
    if not model_admin.get_search_fields(request):
        raise Http404
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    queryset = model_admin.get_queryset(request).complex_filter(source_field.get_limit_choices_to())
    queryset, may_have_duplicates = model_admin.get_search_results(request, queryset, request.GET.get("q", "").strip())
    if may_have_duplicates:
        queryset = queryset.distinct()
    if not queryset.ordered:
        # Paging an unordered list repeats and skips rows.
        queryset = queryset.order_by(*(model_admin.get_ordering(request) or ("-pk",)))
    return queryset


class _RelationSearch(FormworkForm):
    """Registers ``relation_queryset`` once, under a key every relation widget reuses."""

    related: forms.ModelChoiceField[Any] = forms.ModelChoiceField(
        queryset=None,
        widget=Select(search_queryset=relation_queryset, search_decorator=None),
    )


RELATION_SEARCH_KEY: str = _RelationSearch.base_fields["related"].widget.search_key


def relation_widget(
    db_field: models.ForeignKey[Any, Any] | models.ManyToManyField[Any, Any],
    admin_site: Any,
    *,
    searchable: bool,
    multiple: bool | None = None,
    **kwargs: Any,
) -> forms.Widget:
    """The dropdown of a relation; ``searchable`` pages its rows from the server.

    ``multiple`` picks several rows, by default for a many-to-many field.
    """
    if multiple is None:
        multiple = isinstance(db_field, models.ManyToManyField)
    widget_class = SelectMultiple if multiple else Select
    to_field = getattr(db_field.remote_field, "field_name", None)
    # The search returns primary keys, so a relation to another column lists its rows inline.
    if not searchable or to_field not in {None, db_field.related_model._meta.pk.name}:
        return widget_class(**kwargs)
    return widget_class(
        search_key=RELATION_SEARCH_KEY,
        search_params={"site": admin_site.name, "model": db_field.model._meta.label_lower, "field": db_field.name},
        **kwargs,
    )


# The native picker, to the second, so a value nobody touched saves unchanged.
_DATETIME = {"widget": forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}, format="%Y-%m-%dT%H:%M:%S")}

FORMFIELD_FOR_DBFIELD_DEFAULTS: dict[type[models.Field[Any, Any]], dict[str, Any]] = {
    models.DateTimeField: _DATETIME,
    models.DateField: {"widget": DatePicker},
    models.TimeField: {"widget": forms.TimeInput(attrs={"type": "time", "step": 1}, format="%H:%M:%S")},
    models.TextField: {"widget": Textarea(attrs={"rows": 4})},
    models.JSONField: {"widget": Textarea(attrs={"rows": 6, "class": "font-mono text-sm"})},
    models.URLField: {"widget": TextInput(input_type="url")},
    models.EmailField: {"widget": TextInput(input_type="email")},
    models.CharField: {"widget": TextInput},
    models.SlugField: {"widget": TextInput},
    models.UUIDField: {"widget": TextInput(attrs={"class": "font-mono"})},
    models.GenericIPAddressField: {"widget": TextInput},
    models.FileField: {"widget": ClearableFileInput},
    models.ImageField: {"widget": ClearableFileInput(attrs={"accept": "image/*"})},
    models.BooleanField: {"widget": ToggleInput},
}
