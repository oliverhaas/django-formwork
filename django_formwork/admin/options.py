"""``ModelAdmin`` and the inlines, with Django's option and hook names.

The views render Jinja templates under ``formwork_admin/`` and formwork forms.
"""

from __future__ import annotations

import copy
import io
from functools import cached_property, partial, update_wrapper
from typing import TYPE_CHECKING, Any, ClassVar, cast
from urllib.parse import quote_plus

from django import forms
from django.apps import apps
from django.contrib import messages
from django.contrib.admin import options as django_options
from django.contrib.admin.utils import (
    NestedObjects,
    construct_change_message,
    flatten_fieldsets,
    get_deleted_objects,
    model_format_dict,
    model_ngettext,
    quote,
    unquote,
)
from django.contrib.auth import get_permission_codename
from django.core.exceptions import FieldDoesNotExist, FieldError, PermissionDenied, ValidationError
from django.db import IntegrityError, models, router, transaction
from django.forms.formsets import DELETION_FIELD_NAME, all_valid
from django.forms.models import modelform_defines_fields
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseRedirect,
    QueryDict,
)
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst, get_text_list
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from django_formwork.admin import exports, formats, imports
from django_formwork.admin.changelist import PRESERVED_FILTERS_VAR, ChangeList
from django_formwork.admin.filters import build_filterset
from django_formwork.admin.helpers import AdminForm, InlineAdminFormSet
from django_formwork.admin.info import describe_fields, describe_search, describe_table
from django_formwork.admin.jinja import AdminTemplateResponse
from django_formwork.admin.paginator import EstimatedCountPaginator
from django_formwork.admin.widgets import FORMFIELD_FOR_DBFIELD_DEFAULTS, relation_widget
from django_formwork.forms import FormworkModelForm
from django_formwork.formsets import (
    FormworkBaseInlineFormSet,
    FormworkBaseModelFormSet,
    formwork_inlineformset_factory,
    formwork_modelformset_factory,
)
from django_formwork.widgets import Select

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from uuid import UUID

    from django.contrib.admin.options import _FieldsetSpec
    from django.db.models.fields.related import RelatedField
    from django.http import HttpRequest
    from django.urls import URLPattern
    from django_stubs_ext import StrPromise

    from django_formwork.admin.filters import AdminFilterSet

__all__ = [
    "ACTION_CHECKBOX_NAME",
    "HORIZONTAL",
    "VERTICAL",
    "BaseModelAdmin",
    "InlineModelAdmin",
    "ModelAdmin",
    "StackedInline",
    "TabularInline",
]

ACTION_CHECKBOX_NAME = "_selected_action"
HORIZONTAL, VERTICAL = 1, 2


def _log_entries_installed() -> bool:
    return apps.is_installed("django.contrib.admin")


def get_content_type_for_model(obj: Any) -> Any:
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(obj, for_concrete_model=False)


class BaseModelAdmin:
    """What a model admin and an inline share: the form and its fields."""

    autocomplete_fields: Sequence[str] = ()
    raw_id_fields: Sequence[str] = ()
    fields: Sequence[Any] | None = None
    exclude: Sequence[str] | None = None
    fieldsets: Sequence[tuple[str | None, dict[str, Any]]] | None = None
    form: type[forms.ModelForm[Any]] = FormworkModelForm
    filter_vertical: Sequence[str] = ()
    filter_horizontal: Sequence[str] = ()
    radio_fields: ClassVar[dict[str, int]] = {}
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {}
    formfield_overrides: Mapping[type[models.Field[Any, Any]], Mapping[str, Any]] = {}
    readonly_fields: Sequence[Any] = ()
    ordering: Sequence[Any] | None = None
    sortable_by: Sequence[str] | None = None
    view_on_site: bool | Callable[[models.Model], str] = True
    show_full_result_count = True

    model: type[models.Model]
    admin_site: Any

    def __init__(self) -> None:
        overrides = copy.deepcopy(FORMFIELD_FOR_DBFIELD_DEFAULTS)
        for field_class, kwargs in self.formfield_overrides.items():
            overrides.setdefault(field_class, {}).update(kwargs)
        self.formfield_overrides = overrides

    # Form fields

    def formfield_for_dbfield(
        self, db_field: models.Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        """The form field for one model field, on a formwork widget."""
        if db_field.choices:
            return self.formfield_for_choice_field(db_field, request, **kwargs)
        if isinstance(db_field, models.ForeignKey | models.ManyToManyField):
            if db_field.__class__ in self.formfield_overrides:
                kwargs = {**self.formfield_overrides[db_field.__class__], **kwargs}
            if isinstance(db_field, models.ForeignKey):
                return self.formfield_for_foreignkey(db_field, request, **kwargs)
            return self.formfield_for_manytomany(db_field, request, **kwargs)
        if isinstance(db_field, models.BooleanField) and db_field.null and "widget" not in kwargs:
            choices = [("unknown", _("Unknown")), ("true", _("Yes")), ("false", _("No"))]
            kwargs["widget"] = Select(choices=choices, show_search=False)
            return db_field.formfield(**kwargs)
        for klass in db_field.__class__.mro():
            if klass in self.formfield_overrides:
                kwargs = {
                    **copy.deepcopy(self.formfield_overrides[cast("type[models.Field[Any, Any]]", klass)]),
                    **kwargs,
                }
                return db_field.formfield(**kwargs)
        return db_field.formfield(**kwargs)

    def formfield_for_choice_field(
        self, db_field: models.Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        if db_field.name in self.radio_fields:
            kwargs.setdefault("widget", self._radio_select(db_field))
            if "choices" not in kwargs:
                kwargs["choices"] = db_field.get_choices(include_blank=db_field.blank, blank_choice=[("", _("None"))])
        kwargs.setdefault("widget", Select(allow_clear=db_field.blank))
        return db_field.formfield(**kwargs)

    def _radio_select(self, db_field: models.Field[Any, Any]) -> forms.RadioSelect:
        # The choice group stacks its options; HORIZONTAL lays them out in a row.
        horizontal = self.radio_fields[db_field.name] == HORIZONTAL
        return forms.RadioSelect(attrs={"class": "flex-row flex-wrap gap-x-5"} if horizontal else None)

    def get_field_queryset(
        self, db: str | None, db_field: RelatedField[Any, Any], request: HttpRequest
    ) -> models.QuerySet[Any] | None:
        """The related admin's ordering, applied to the rows a relation offers."""
        related_admin = self.admin_site.get_model_admin_or_none(db_field.remote_field.model)
        if related_admin is None:
            return None
        ordering = related_admin.get_ordering(request)
        if not ordering:
            return None
        return db_field.remote_field.model._default_manager.using(db).order_by(*ordering)

    def _relation_searchable(self, db_field: RelatedField[Any, Any]) -> bool:
        # Every relation to a searchable admin pages from the server. autocomplete_fields
        # and raw_id_fields ask for it by name, and the checks hold the target to it.
        names = {*self.autocomplete_fields, *self.raw_id_fields}
        return db_field.name in names or self.admin_site.is_searchable(db_field.remote_field.model)

    def formfield_for_foreignkey(
        self, db_field: models.ForeignKey[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        db = kwargs.get("using")
        if "widget" not in kwargs:
            if db_field.name in self.radio_fields:
                kwargs["widget"] = self._radio_select(db_field)
                kwargs["empty_label"] = _("None") if db_field.blank else None
            else:
                kwargs["widget"] = relation_widget(
                    db_field,
                    self.admin_site,
                    searchable=self._relation_searchable(db_field),
                    allow_clear=db_field.blank,
                )
        if "queryset" not in kwargs:
            queryset = self.get_field_queryset(db, db_field, request)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return db_field.formfield(**kwargs)

    def formfield_for_manytomany(
        self, db_field: models.ManyToManyField[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> forms.Field | None:
        # A through model with fields of its own is edited as an inline.
        if not cast("type[models.Model]", db_field.remote_field.through)._meta.auto_created:
            return None
        db = kwargs.get("using")
        if "widget" not in kwargs:
            kwargs["widget"] = relation_widget(
                db_field, self.admin_site, searchable=self._relation_searchable(db_field)
            )
        if "queryset" not in kwargs:
            queryset = self.get_field_queryset(db, db_field, request)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return db_field.formfield(**kwargs)

    # Option getters

    def get_autocomplete_fields(self, request: HttpRequest) -> Sequence[str]:
        return self.autocomplete_fields

    def get_view_on_site_url(self, obj: models.Model | None = None) -> str | None:
        if obj is None or not self.view_on_site:
            return None
        if callable(self.view_on_site):
            return self.view_on_site(obj)
        if hasattr(obj, "get_absolute_url"):
            return reverse(
                f"{self.admin_site.name}:view_on_site",
                kwargs={"content_type_id": get_content_type_for_model(obj).pk, "object_id": obj.pk},
            )
        return None

    def get_empty_value_display(self) -> str:
        return str(getattr(self, "empty_value_display", None) or self.admin_site.empty_value_display)

    def get_exclude(self, request: HttpRequest, obj: models.Model | None = None) -> Sequence[str] | None:
        return self.exclude

    def get_fields(self, request: HttpRequest, obj: models.Model | None = None) -> Sequence[Any]:
        if self.fields:
            return self.fields
        form = self._get_form_for_get_fields(request, obj)
        return [*form.base_fields, *self.get_readonly_fields(request, obj)]

    def get_fieldsets(
        self, request: HttpRequest, obj: models.Model | None = None
    ) -> Sequence[tuple[str | None, dict[str, Any]]]:
        if self.fieldsets:
            return self.fieldsets
        return [(None, {"fields": self.get_fields(request, obj)})]

    def get_inlines(self, request: HttpRequest, obj: models.Model | None) -> Sequence[type[InlineModelAdmin]]:
        return getattr(self, "inlines", ())

    def get_ordering(self, request: HttpRequest) -> Sequence[Any]:
        return self.ordering or ()

    def get_readonly_fields(self, request: HttpRequest, obj: models.Model | None = None) -> Sequence[Any]:
        return self.readonly_fields

    def get_prepopulated_fields(
        self, request: HttpRequest, obj: models.Model | None = None
    ) -> dict[str, Sequence[str]]:
        return self.prepopulated_fields

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Any]:
        queryset = self.model._default_manager.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_sortable_by(self, request: HttpRequest) -> Sequence[Any]:
        return self.sortable_by if self.sortable_by is not None else self.get_list_display(request)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]

    # Permissions

    @property
    def opts(self) -> Any:
        return self.model._meta

    def _has_perm(self, request: HttpRequest, action: str) -> bool:
        codename = get_permission_codename(action, self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")  # ty: ignore[unresolved-attribute]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self._has_perm(request, "add")

    def has_change_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return self._has_perm(request, "change")

    def has_delete_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return self._has_perm(request, "delete")

    def has_view_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return self._has_perm(request, "view") or self.has_change_permission(request, obj)

    def has_view_or_change_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        return self.has_view_permission(request, obj) or self.has_change_permission(request, obj)

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.has_module_perms(self.opts.app_label)  # ty: ignore[unresolved-attribute]

    def _get_form_for_get_fields(self, request: HttpRequest, obj: models.Model | None) -> Any:
        return self.get_form(request, obj, fields=None)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]


class ModelAdmin(BaseModelAdmin):
    """The admin pages of one model: list, add, change, delete and history."""

    #: The Lucide icon next to the model in the navigation; unset, the site picks a shape.
    icon: str | None = None
    list_display: Sequence[Any] = ("__str__",)
    list_display_links: Sequence[Any] | None = ()
    list_filter: Sequence[Any] = ()
    list_select_related: bool | Sequence[str] = False
    list_per_page = 100
    list_max_show_all = 200
    list_editable: Sequence[str] = ()
    #: Load only these columns on the changelist (opt-in: a ``__str__`` that reads a deferred field queries per row).
    list_only_fields: Sequence[str] | None = None
    #: Skip loading these columns on the changelist.
    list_defer_fields: Sequence[str] | None = None
    #: Badge colours per choice value, by column: ``{"status": {"done": "success"}}``.
    list_badges: ClassVar[dict[str, dict[str, str]]] = {}
    search_fields: Sequence[str] = ()
    search_help_text: str | None = None
    date_hierarchy: str | None = None
    save_as = False
    save_as_continue = True
    save_on_top = False
    paginator = EstimatedCountPaginator
    preserve_filters = True
    show_facets = None
    inlines: Sequence[type[InlineModelAdmin]] = ()
    delete_confirmation_max_display = 100

    # Custom templates (a name or a list of names, looked up in the admin's Jinja engine).
    add_form_template: str | Sequence[str] | None = None
    change_form_template: str | Sequence[str] | None = None
    change_list_template: str | Sequence[str] | None = None
    delete_confirmation_template: str | Sequence[str] | None = None
    delete_selected_confirmation_template: str | Sequence[str] | None = None
    object_history_template: str | Sequence[str] | None = None
    import_template: str | Sequence[str] | None = None

    #: The export's columns: field names, admin methods, callables or ``__`` lookups; unset, every field.
    export_fields: Sequence[Any] | None = None
    #: The file types the Export menu offers, by name in ``formats.FORMATS``; empty hides the menu.
    export_formats: Sequence[str] = ("csv", "xlsx", "json")
    #: Above this many rows an export runs as a background task; None keeps every export in the request.
    export_background_threshold: int | None = 5000

    #: The file types the Import page reads, by name in ``formats.FORMATS``; empty hides the Import button.
    import_formats: Sequence[str] = ()
    #: The fields an import sets; unset, the add form's fields without the read-only ones.
    import_fields: Sequence[str] | None = None
    #: The fields that find the record a row updates; unset, the primary key.
    import_id_fields: Sequence[str] | None = None

    actions: Sequence[Any] | None = ()
    actions_on_top = True
    actions_on_bottom = False
    actions_selection_counter = True

    def __init__(self, model: type[models.Model], admin_site: Any) -> None:
        self.model = model
        self.admin_site = admin_site
        super().__init__()

    def __str__(self) -> str:
        return f"{self.opts.app_label}.{self.__class__.__name__}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__}: model={self.model.__qualname__} site={self.admin_site!r}>"

    # URLs

    def get_urls(self) -> list[URLPattern]:
        def wrap(view: Callable[..., HttpResponseBase]) -> Callable[..., HttpResponseBase]:
            def wrapper(*args: Any, **kwargs: Any) -> HttpResponseBase:
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            return update_wrapper(wrapper, view)

        info = self.opts.app_label, self.opts.model_name
        return [
            path("", wrap(self.changelist_view), name="{}_{}_changelist".format(*info)),
            path("add/", wrap(self.add_view), name="{}_{}_add".format(*info)),
            path("export/", wrap(self.export_view), name="{}_{}_export".format(*info)),
            path("import/", wrap(self.import_view), name="{}_{}_import".format(*info)),
            path("info/", wrap(self.info_view), name="{}_{}_info".format(*info)),
            path("<path:object_id>/history/", wrap(self.history_view), name="{}_{}_history".format(*info)),
            path("<path:object_id>/delete/", wrap(self.delete_view), name="{}_{}_delete".format(*info)),
            path("<path:object_id>/change/", wrap(self.change_view), name="{}_{}_change".format(*info)),
            path("<path:object_id>/", wrap(self.redirect_to_change), name="{}_{}_redirect".format(*info)),
        ]

    @property
    def urls(self) -> list[URLPattern]:
        return self.get_urls()

    def url_name(self, view: str) -> str:
        return f"{self.admin_site.name}:{self.opts.app_label}_{self.opts.model_name}_{view}"

    def redirect_to_change(self, request: HttpRequest, object_id: str) -> HttpResponse:
        return HttpResponseRedirect(reverse(self.url_name("change"), args=(object_id,)))

    @property
    def media(self) -> forms.Media:
        return forms.Media()

    def get_model_perms(self, request: HttpRequest) -> dict[str, bool]:
        return {
            "add": self.has_add_permission(request),
            "change": self.has_change_permission(request),
            "delete": self.has_delete_permission(request),
            "view": self.has_view_permission(request),
        }

    # Forms

    def get_form(
        self, request: HttpRequest, obj: models.Model | None = None, change: bool = False, **kwargs: Any
    ) -> type[forms.ModelForm[Any]]:
        fields = (
            kwargs.pop("fields")
            if "fields" in kwargs
            else flatten_fieldsets(cast("_FieldsetSpec", self.get_fieldsets(request, obj)))
        )
        excluded = self.get_exclude(request, obj)
        exclude = [] if excluded is None else list(excluded)
        readonly_fields = self.get_readonly_fields(request, obj)
        exclude.extend(name for name in readonly_fields if isinstance(name, str))
        if change and hasattr(request, "user") and not self.has_change_permission(request, obj):
            exclude.extend(fields or ())
        if excluded is None and hasattr(self.form, "_meta") and self.form._meta.exclude:
            exclude.extend(self.form._meta.exclude)
        new_attrs = dict.fromkeys(name for name in readonly_fields if name in getattr(self.form, "declared_fields", {}))
        form = type(self.form.__name__, (self.form,), new_attrs)
        defaults: dict[str, Any] = {
            "form": form,
            "fields": fields,
            "exclude": exclude or None,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            **kwargs,
        }
        if defaults["fields"] is None and not modelform_defines_fields(defaults["form"]):
            defaults["fields"] = forms.ALL_FIELDS
        try:
            return forms.modelform_factory(self.model, **defaults)
        except FieldError as error:
            msg = f"{error}. Check fields/fieldsets/exclude attributes of class {self.__class__.__name__}."
            raise FieldError(msg) from error

    def get_changelist(self, request: HttpRequest, **kwargs: Any) -> type[ChangeList]:
        return ChangeList

    def get_changelist_instance(self, request: HttpRequest) -> ChangeList:
        return self.get_changelist(request)(request, self)

    def get_object(self, request: HttpRequest, object_id: str, from_field: str | None = None) -> models.Model | None:
        queryset = self.get_queryset(request)
        model = queryset.model
        field = model._meta.pk if from_field is None else model._meta.get_field(from_field)
        try:
            value = field.to_python(object_id)
            return queryset.get(**{field.name: value})
        except model.DoesNotExist, ValidationError, ValueError:
            return None

    def get_changelist_form(self, request: HttpRequest, **kwargs: Any) -> type[forms.ModelForm[Any]]:
        defaults: dict[str, Any] = {
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            **kwargs,
        }
        if defaults.get("fields") is None and not modelform_defines_fields(defaults.get("form")):  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            defaults["fields"] = forms.ALL_FIELDS
        return forms.modelform_factory(self.model, form=self.form, **defaults)

    def get_changelist_formset(self, request: HttpRequest, **kwargs: Any) -> type[FormworkBaseModelFormSet]:
        return formwork_modelformset_factory(
            self.model,
            form=self.get_changelist_form(request),
            extra=0,
            fields=self.list_editable,
            formfield_callback=partial(self.formfield_for_dbfield, request=request),
            **kwargs,
        )

    def get_formsets_with_inlines(self, request: HttpRequest, obj: models.Model | None = None) -> Any:
        for inline in self.get_inline_instances(request, obj):
            yield inline.get_formset(request, obj), inline

    def get_inline_instances(self, request: HttpRequest, obj: models.Model | None = None) -> list[InlineModelAdmin]:
        instances = []
        for inline_class in self.get_inlines(request, obj):
            inline = inline_class(self.model, self.admin_site)
            if request:
                if not (
                    inline.has_view_or_change_permission(request, obj)
                    or inline.has_add_permission(request, obj)
                    or inline.has_delete_permission(request, obj)
                ):
                    continue
                if not inline.has_add_permission(request, obj):
                    inline.max_num = 0
            instances.append(inline)
        return instances

    def get_paginator(
        self,
        request: HttpRequest,
        queryset: models.QuerySet[Any],
        per_page: int,
        orphans: int = 0,
        allow_empty_first_page: bool = True,
    ) -> Any:
        return self.paginator(queryset, per_page, orphans, allow_empty_first_page)

    # Changelist options

    def get_list_display(self, request: HttpRequest) -> Sequence[Any]:
        return self.list_display

    def get_list_display_links(self, request: HttpRequest, list_display: Sequence[Any]) -> Sequence[Any] | None:
        if self.list_display_links or self.list_display_links is None or not list_display:
            return self.list_display_links
        return list(list_display)[:1]

    def get_list_filter(self, request: HttpRequest) -> Sequence[Any]:
        return self.list_filter

    def get_list_select_related(self, request: HttpRequest) -> bool | Sequence[str]:
        return self.list_select_related

    def get_search_fields(self, request: HttpRequest) -> Sequence[str]:
        return self.search_fields

    def get_search_results(
        self, request: HttpRequest, queryset: models.QuerySet[Any], search_term: str
    ) -> tuple[models.QuerySet[Any], bool]:
        """Django's search: every word matches some field, ``^``, ``=`` and ``@`` prefixes included."""
        return django_options.ModelAdmin.get_search_results(self, request, queryset, search_term)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    @cached_property
    def _filterset_classes(self) -> dict[tuple[Any, ...], type[AdminFilterSet] | None]:
        return {}

    def get_filterset_class(self, request: HttpRequest) -> type[AdminFilterSet] | None:
        """The filter bar's ``FilterSet``, built once per ``list_filter``, ``search_fields`` and ``date_hierarchy``."""
        list_filter = list(self.get_list_filter(request))
        if self.date_hierarchy and self.date_hierarchy not in list_filter:
            list_filter.append(self.date_hierarchy)
        search_fields = tuple(self.get_search_fields(request))
        key = (tuple(map(repr, list_filter)), search_fields)
        if key not in self._filterset_classes:
            self._filterset_classes[key] = build_filterset(self, list_filter, search_fields)
        return self._filterset_classes[key]

    def get_changelist_queryset(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> models.QuerySet[Any]:
        """The changelist's rows narrowed to ``list_only_fields`` or without ``list_defer_fields``."""
        if self.list_only_fields:
            return queryset.only(*self.list_only_fields)
        if self.list_defer_fields:
            return queryset.defer(*self.list_defer_fields)
        return queryset

    # Exports

    def has_export_permission(self, request: HttpRequest) -> bool:
        """Whoever sees the list can export it."""
        return self.has_view_or_change_permission(request)

    def get_export_fields(self, request: HttpRequest) -> Sequence[Any]:
        """``export_fields``, or every field and many-to-many field of the model."""
        if self.export_fields is not None:
            return self.export_fields
        return [field.name for field in (*self.opts.concrete_fields, *self.opts.many_to_many)]

    def get_export_columns(self, request: HttpRequest) -> list[exports.Column]:
        return exports.get_columns(self, request)

    def get_export_formats(self, request: HttpRequest) -> list[formats.FileFormat]:
        """The formats of ``export_formats`` that can run here; Excel needs openpyxl."""
        named = (formats.FORMATS.get(name) for name in self.export_formats)
        return [format_ for format_ in named if format_ is not None and format_.is_available()]

    def get_export_queryset(self, request: HttpRequest) -> models.QuerySet[Any]:
        """The changelist's rows for ``request.GET``, with every column loaded."""
        return self.get_changelist_instance(request).queryset.defer(None)

    def export_view(self, request: HttpRequest) -> HttpResponse:
        """Export the list as the changelist filters it: in the response, or as a task above the threshold."""
        if request.method != "POST":
            return HttpResponseRedirect(self.changelist_url(request))
        if not self.has_export_permission(request):
            raise PermissionDenied
        offered = {format_.name: format_ for format_ in self.get_export_formats(request)}
        export_format = offered.get(request.POST.get("format", ""))
        if export_format is None:
            return HttpResponseBadRequest(_("Pick one of the export formats."))
        query = request.POST.get("query", "")
        list_request = copy.copy(request)
        list_request.method = "GET"
        list_request.GET = QueryDict(query)
        queryset = self.get_export_queryset(list_request)
        threshold = self.export_background_threshold
        if threshold is not None and (count := queryset.count()) > threshold:
            self.start_export(request, export_format, query, count)
            changelist_url = self.changelist_url(request)
            return HttpResponseRedirect(f"{changelist_url}?{query}" if query else changelist_url)
        columns = self.get_export_columns(list_request)
        buffer = io.BytesIO()
        export_format.write(columns, exports.export_rows(columns, queryset), buffer)
        response = HttpResponse(buffer.getvalue(), content_type=export_format.content_type)
        filename = exports.export_filename(self.opts, export_format)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def start_export(self, request: HttpRequest, export_format: formats.FileFormat, query: str, count: int) -> None:
        """Queue an export job once the request's transaction commits, and say where the file turns up."""
        from django.contrib.contenttypes.models import ContentType

        from django_formwork.admin.models import ExportJob

        job = ExportJob.objects.create(
            user_id=cast("int | str", request.user.pk),
            site_name=self.admin_site.name,
            content_type=ContentType.objects.get_for_model(self.model, for_concrete_model=False),
            query=query,
            format=export_format.name,
        )
        transaction.on_commit(partial(self.admin_site.enqueue_export, job), using=router.db_for_write(ExportJob))
        job.refresh_from_db()
        exports_url = reverse(f"{self.admin_site.name}:exports", current_app=self.admin_site.name)
        name = model_ngettext(self.opts, count)
        if job.status == ExportJob.Status.DONE:
            download_url = reverse(f"{self.admin_site.name}:export_download", args=[job.pk])
            msg = format_html(
                _('Exported {count} {name}. <a href="{url}">Download the file</a>.'),
                count=count,
                name=name,
                url=download_url,
            )
            self.message_user(request, msg, messages.SUCCESS)
        elif job.status == ExportJob.Status.FAILED:
            msg = format_html(
                _('The export of {count} {name} failed. <a href="{url}">See Exports</a>.'),
                count=count,
                name=name,
                url=exports_url,
            )
            self.message_user(request, msg, messages.ERROR)
        else:
            msg = format_html(
                _('Exporting {count} {name} in the background. The file turns up under <a href="{url}">Exports</a>.'),
                count=count,
                name=name,
                url=exports_url,
            )
            self.message_user(request, msg, messages.INFO)

    # Imports

    def has_import_permission(self, request: HttpRequest) -> bool:
        """Whoever can add or change records can import; each row is checked again."""
        return self.has_add_permission(request) or self.has_change_permission(request)

    def get_import_formats(self, request: HttpRequest) -> list[formats.FileFormat]:
        """The formats of ``import_formats`` that can run here; Excel needs openpyxl."""
        named = (formats.FORMATS.get(name) for name in self.import_formats)
        return [format_ for format_ in named if format_ is not None and format_.is_available()]

    def get_import_fields(self, request: HttpRequest) -> Sequence[str]:
        """``import_fields``, or the add form's fields without the read-only ones and the files."""
        if self.import_fields is not None:
            return self.import_fields
        readonly = set(self.get_readonly_fields(request))
        names = flatten_fieldsets(cast("_FieldsetSpec", self.get_fieldsets(request)))
        return [name for name in names if name not in readonly and not self._is_file_field(name)]

    def _is_file_field(self, name: str) -> bool:
        try:
            return isinstance(self.opts.get_field(name), models.FileField)
        except FieldDoesNotExist:
            return False

    def get_import_id_fields(self, request: HttpRequest) -> Sequence[str]:
        """``import_id_fields``, or the primary key."""
        return self.import_id_fields if self.import_id_fields is not None else [self.opts.pk.name]

    def get_import_form(self, request: HttpRequest) -> type[forms.ModelForm[Any]]:
        """The form each row of an import runs through: the add form with ``get_import_fields()``."""
        return self.get_form(request, None, fields=list(self.get_import_fields(request)))

    def import_view(self, request: HttpRequest) -> HttpResponse:
        """Check a file's rows with the admin's form; a second post of the same file saves them."""
        if not self.has_import_permission(request):
            raise PermissionDenied
        import_formats = self.get_import_formats(request)
        if not import_formats:
            raise Http404
        posted = request.method == "POST"
        form = imports.ImportFileForm(
            request.POST if posted else None, request.FILES if posted else None, formats=import_formats
        )
        result = None
        stale = False
        if posted and form.is_valid():
            content = form.cleaned_data["file"].read()
            try:
                table = cast("formats.FileFormat", form.file_format).read(io.BytesIO(content))
                result = imports.check_import(self, request, table, content)
            except formats.FileError as error:
                form.add_error("file", str(error))
            else:
                if "_import" in request.POST:
                    stale = request.POST.get("digest") != result.digest
                    if not stale and result.can_import:
                        return self.response_import(request, form, result)
        return self._import_page(request, form, result, stale=stale)

    def _import_page(
        self, request: HttpRequest, form: forms.Form, result: imports.ImportResult | None, *, stale: bool = False
    ) -> HttpResponse:
        context = self.page_context(
            request,
            title=_("Import %(name)s") % {"name": self.opts.verbose_name_plural},
            subtitle=None,
            form=form,
            result=result,
            preview=imports.preview_rows(self, result) if result is not None else [],
            preview_limit=imports.PREVIEW_LIMIT,
            guide=imports.column_guide(self, request),
            stale=stale,
            media=self.media + form.media,
        )
        return self.render(request, self._templates(self.import_template, "import.html"), context)

    def response_import(self, request: HttpRequest, form: forms.Form, result: imports.ImportResult) -> HttpResponse:
        """Save the checked rows and return to the list, or show why nothing was saved."""
        try:
            added, changed = imports.save_import(self, request, result)
        except IntegrityError as error:
            form.add_error(None, _("Saving failed, nothing was imported: %(error)s") % {"error": error})
            return self._import_page(request, form, None)
        count = added + changed
        msg = ngettext(
            "Imported %(count)s %(name)s: %(added)s added, %(changed)s changed.",
            "Imported %(count)s %(name)s: %(added)s added, %(changed)s changed.",
            count,
        ) % {"count": count, "name": model_ngettext(self.opts, count), "added": added, "changed": changed}
        self.message_user(request, msg, messages.SUCCESS)
        return HttpResponseRedirect(self.changelist_url(request))

    # The info dialog

    def info_view(self, request: HttpRequest) -> HttpResponse:
        """The changelist's info dialog: what the search looks in, the fields and, for a superuser, the table."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        paginator = self.get_paginator(request, self.get_queryset(request).order_by("pk"), 1)
        context = {
            "opts": self.opts,
            "model_admin": self,
            "search_fields": describe_search(self.model, self.get_search_fields(request)),
            "search_help_text": self.search_help_text,
            "fields": describe_fields(self.opts),
            "ordering": [str(item) for item in self.get_ordering(request) or self.opts.ordering or ("-pk",)],
            "row_count": paginator.count,
            "row_count_is_estimate": getattr(paginator, "is_estimate", False),
            "table": describe_table(self.model) if getattr(request.user, "is_superuser", False) else None,
            "model_path": f"{self.model.__module__}.{self.model.__qualname__}",
            "admin_path": f"{type(self).__module__}.{type(self).__qualname__}",
        }
        return self.render(request, self._templates(None, "change_list_info.html"), context)

    # Actions

    def _get_base_actions(self) -> list[tuple[Callable[..., Any], str, str]]:
        actions: list[tuple[Callable[..., Any], str, str]] = []
        if self.actions is not None:
            actions.extend(
                (func, name, getattr(func, "short_description", None) or capfirst(name.replace("_", " ")))
                for name, func in self.admin_site.actions
            )
            # Django resolves a name to the class attribute, so a method action gets the admin as its first argument.
            actions.extend(action for action in map(self.get_action, self.actions or ()) if action is not None)
        return actions

    def _filter_actions_by_permissions(self, request: HttpRequest, actions: list[Any]) -> list[Any]:
        allowed = []
        for action in actions:
            callable_ = action[0]
            permissions = getattr(callable_, "allowed_permissions", ())
            if all(getattr(self, f"has_{permission}_permission")(request) for permission in permissions):
                allowed.append(action)
        return allowed

    def get_actions(self, request: HttpRequest) -> dict[str, tuple[Callable[..., Any], str, str]]:
        if self.actions is None:
            return {}
        actions = self._filter_actions_by_permissions(request, self._get_base_actions())
        return {name: (func, name, desc) for func, name, desc in actions}

    def get_action(self, action: str | Callable[..., Any]) -> tuple[Callable[..., Any], str, str] | None:
        if callable(action):
            func, name = action, action.__name__  # ty: ignore[unresolved-attribute]
        elif hasattr(self.__class__, action):
            func, name = getattr(self.__class__, action), action
        else:
            try:
                func, name = self.admin_site.get_action(action), action
            except KeyError:
                return None
        description = getattr(func, "short_description", None) or capfirst(name.replace("_", " "))
        return func, name, description

    def get_action_choices(self, request: HttpRequest) -> list[dict[str, Any]]:
        """The actions as the action bar draws them: name, label, icon and whether it destroys."""
        choices = []
        for func, name, description in self.get_actions(request).values():
            choices.append(
                {
                    "name": name,
                    "label": str(description) % model_format_dict(self.opts),
                    "icon": getattr(func, "icon", ""),
                    "danger": getattr(func, "danger", False),
                }
            )
        return choices

    def response_action(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> HttpResponse | None:
        """Run the posted action over the selected rows, or over every filtered row with ``select_across``."""
        name = request.POST.get("action", "")
        actions = self.get_actions(request)
        if name not in actions:
            self.message_user(request, _("No action selected."), messages.WARNING)
            return None
        func = actions[name][0]
        selected = request.POST.getlist(ACTION_CHECKBOX_NAME)
        select_across = request.POST.get("select_across") == "1"
        if not selected and not select_across:
            msg = _("Items must be selected in order to perform actions on them. No items have been changed.")
            self.message_user(request, msg, messages.WARNING)
            return None
        if not select_across:
            queryset = queryset.filter(pk__in=selected)
        response = func(self, request, queryset)
        if response is not None and hasattr(response, "status_code"):
            return response
        return HttpResponseRedirect(request.get_full_path())

    # Saving

    def save_form(self, request: HttpRequest, form: forms.ModelForm[Any], change: bool) -> models.Model:
        return form.save(commit=False)

    def save_model(self, request: HttpRequest, obj: models.Model, form: forms.ModelForm[Any], change: bool) -> None:
        obj.save()

    def delete_model(self, request: HttpRequest, obj: models.Model) -> None:
        obj.delete()

    def delete_queryset(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> None:
        queryset.delete()

    def save_formset(self, request: HttpRequest, form: forms.ModelForm[Any], formset: Any, change: bool) -> None:
        formset.save()

    def save_related(self, request: HttpRequest, form: forms.ModelForm[Any], formsets: list[Any], change: bool) -> None:
        form.save_m2m()
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, Any]:
        initial: dict[str, Any] = dict(request.GET.items())
        for key, value in initial.items():
            try:
                field = self.opts.get_field(key)
            except FieldDoesNotExist:
                continue
            if isinstance(field, models.ManyToManyField):
                initial[key] = value.split(",")
        return initial

    def construct_change_message(
        self, request: HttpRequest, form: forms.ModelForm[Any], formsets: list[Any], add: bool = False
    ) -> list[dict[str, Any]]:
        return construct_change_message(form, formsets, add)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    def get_deleted_objects(
        self, objs: Any, request: HttpRequest
    ) -> tuple[list[Any], dict[str, int], set[str], list[Any]]:
        return get_deleted_objects(objs, request, self.admin_site)

    # History

    def log_addition(self, request: HttpRequest, obj: models.Model, message: Any) -> Any:
        if not _log_entries_installed():
            return None
        from django.contrib.admin.models import ADDITION, LogEntry

        return LogEntry.objects.log_actions(
            user_id=cast("int | str | UUID", request.user.pk),
            queryset=[obj],
            action_flag=ADDITION,
            change_message=message,
            single_object=True,
        )

    def log_change(self, request: HttpRequest, obj: models.Model, message: Any) -> Any:
        if not _log_entries_installed():
            return None
        from django.contrib.admin.models import CHANGE, LogEntry

        return LogEntry.objects.log_actions(
            user_id=cast("int | str | UUID", request.user.pk),
            queryset=[obj],
            action_flag=CHANGE,
            change_message=message,
            single_object=True,
        )

    def log_deletions(self, request: HttpRequest, queryset: Any) -> Any:
        if not _log_entries_installed():
            return None
        from django.contrib.admin.models import DELETION, LogEntry

        return LogEntry.objects.log_actions(
            user_id=cast("int | str | UUID", request.user.pk), queryset=queryset, action_flag=DELETION
        )

    def message_user(
        self,
        request: HttpRequest,
        message: str,
        level: int | str = messages.INFO,
        extra_tags: str = "",
        fail_silently: bool = False,
    ) -> None:
        if not isinstance(level, int):
            try:
                level = cast("int", getattr(messages.constants, level.upper()))
            except AttributeError:
                levels = messages.constants.DEFAULT_TAGS.values()
                msg = f"Bad message level string: `{level}`. Possible values are: {', '.join(f'`{item}`' for item in levels)}"
                raise ValueError(msg) from None
        messages.add_message(request, level, message, extra_tags=extra_tags, fail_silently=fail_silently)

    # Responses

    def get_preserved_filters(self, request: HttpRequest) -> str:
        """The changelist state to return to, as ``_changelist_filters=...``."""
        match = request.resolver_match
        if not self.preserve_filters or match is None:
            return ""
        if match.url_name == f"{self.opts.app_label}_{self.opts.model_name}_changelist":
            preserved = self.get_changelist_instance(request).params.urlencode()
        else:
            preserved = request.GET.get(PRESERVED_FILTERS_VAR, "")
        return f"{PRESERVED_FILTERS_VAR}={quote_plus(preserved)}" if preserved else ""

    def get_icon(self) -> str:
        """The model's icon: ``icon``, or a placeholder shape that the site picks."""
        return self.icon or self.admin_site.placeholder_icon(self.model)

    def changelist_url(self, request: HttpRequest) -> str:
        """The changelist with the filters this page carried."""
        url = reverse(self.url_name("changelist"))
        preserved = request.GET.get(PRESERVED_FILTERS_VAR, "")
        if self.preserve_filters and preserved:
            return f"{url}?{preserved}"
        return url

    def with_preserved_filters(self, request: HttpRequest, url: str) -> str:
        preserved = self.get_preserved_filters(request)
        if not preserved:
            return url
        return f"{url}{'&' if '?' in url else '?'}{preserved}"

    def _object_link(self, obj: models.Model) -> str:
        url = reverse(self.url_name("change"), args=(quote(obj.pk),))
        return format_html('<a href="{}">{}</a>', url, obj)

    def response_add(
        self, request: HttpRequest, obj: models.Model, post_url_continue: str | None = None
    ) -> HttpResponse:
        msg_dict = {"name": self.opts.verbose_name, "obj": self._object_link(obj)}
        if "_continue" in request.POST or (
            "_saveasnew" in request.POST and self.save_as_continue and self.has_change_permission(request, obj)
        ):
            msg = _("The {name} “{obj}” was added successfully.")
            if self.has_change_permission(request, obj):
                msg += " " + _("You may edit it again below.")
            self.message_user(request, format_html(msg, **msg_dict), messages.SUCCESS)
            url = post_url_continue or reverse(self.url_name("change"), args=(quote(obj.pk),))
            return HttpResponseRedirect(self.with_preserved_filters(request, url))
        if "_addanother" in request.POST:
            msg = format_html(
                _("The {name} “{obj}” was added successfully. You may add another {name} below."), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            return HttpResponseRedirect(self.with_preserved_filters(request, request.path))
        msg = format_html(_("The {name} “{obj}” was added successfully."), **msg_dict)
        self.message_user(request, msg, messages.SUCCESS)
        return self.response_post_save_add(request, obj)

    def response_change(self, request: HttpRequest, obj: models.Model) -> HttpResponse:
        msg_dict = {"name": self.opts.verbose_name, "obj": self._object_link(obj)}
        if "_continue" in request.POST:
            msg = format_html(
                _("The {name} “{obj}” was changed successfully. You may edit it again below."), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            return HttpResponseRedirect(self.with_preserved_filters(request, request.path))
        if "_saveasnew" in request.POST:
            msg = format_html(_("The {name} “{obj}” was added successfully. You may edit it again below."), **msg_dict)
            self.message_user(request, msg, messages.SUCCESS)
            url = reverse(self.url_name("change"), args=(quote(obj.pk),))
            return HttpResponseRedirect(self.with_preserved_filters(request, url))
        if "_addanother" in request.POST:
            msg = format_html(
                _("The {name} “{obj}” was changed successfully. You may add another {name} below."), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            return HttpResponseRedirect(self.with_preserved_filters(request, reverse(self.url_name("add"))))
        msg = format_html(_("The {name} “{obj}” was changed successfully."), **msg_dict)
        self.message_user(request, msg, messages.SUCCESS)
        return self.response_post_save_change(request, obj)

    def _response_post_save(self, request: HttpRequest, obj: models.Model) -> HttpResponse:
        if self.has_view_or_change_permission(request):
            return HttpResponseRedirect(self.changelist_url(request))
        return HttpResponseRedirect(reverse(f"{self.admin_site.name}:index"))

    def response_post_save_add(self, request: HttpRequest, obj: models.Model) -> HttpResponse:
        return self._response_post_save(request, obj)

    def response_post_save_change(self, request: HttpRequest, obj: models.Model) -> HttpResponse:
        return self._response_post_save(request, obj)

    def response_delete(self, request: HttpRequest, obj_display: str, obj_id: Any) -> HttpResponse:
        msg = _("The %(name)s “%(obj)s” was deleted successfully.") % {
            "name": self.opts.verbose_name,
            "obj": obj_display,
        }
        self.message_user(request, msg, messages.SUCCESS)
        if self.has_change_permission(request, None) or self.has_view_permission(request, None):
            return HttpResponseRedirect(self.changelist_url(request))
        return HttpResponseRedirect(reverse(f"{self.admin_site.name}:index"))

    def _get_obj_does_not_exist_redirect(self, request: HttpRequest, object_id: str) -> HttpResponse:
        msg = _("%(name)s with ID “%(key)s” doesn’t exist. Perhaps it was deleted?") % {
            "name": self.opts.verbose_name,
            "key": unquote(object_id),
        }
        self.message_user(request, msg, messages.WARNING)
        return HttpResponseRedirect(reverse(f"{self.admin_site.name}:index"))

    # Templates

    def _templates(self, custom: str | Sequence[str] | None, name: str) -> Any:
        if custom:
            return custom
        app_label, model_name = self.opts.app_label, self.opts.model_name
        return [
            f"formwork_admin/{app_label}/{model_name}/{name}",
            f"formwork_admin/{app_label}/{name}",
            f"formwork_admin/{name}",
        ]

    def render(self, request: HttpRequest, templates: Any, context: dict[str, Any]) -> HttpResponse:
        request.current_app = self.admin_site.name
        return AdminTemplateResponse(request, templates, context)

    def page_context(self, request: HttpRequest, **context: Any) -> dict[str, Any]:
        """The site's context, this model's metadata and ``context``."""
        return {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "model_admin": self,
            "app_label": self.opts.app_label,
            "changelist_url": self.changelist_url(request),
            "has_view_permission": self.has_view_permission(request),
            "has_add_permission": self.has_add_permission(request),
            "has_change_permission": self.has_change_permission(request),
            "has_delete_permission": self.has_delete_permission(request),
            "preserved_filters": self.get_preserved_filters(request),
            **context,
        }

    # Views

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        cl = self.get_changelist_instance(request)
        actions = self.get_action_choices(request)

        if request.method == "POST" and "action" in request.POST and "_save" not in request.POST:
            if not actions:
                raise PermissionDenied
            response = self.response_action(request, queryset=cl.queryset)
            return response or HttpResponseRedirect(request.get_full_path())

        formset = None
        if self.list_editable and self.has_change_permission(request):
            FormSet = self.get_changelist_formset(request)  # noqa: N806
            if request.method == "POST" and "_save" in request.POST:
                pks = self._get_edited_object_pks(request, FormSet.get_default_prefix())
                formset = FormSet(request.POST, request.FILES, queryset=cl.root_queryset.filter(pk__in=pks))
                if formset.is_valid():
                    changed = 0
                    with transaction.atomic(using=router.db_for_write(self.model)):
                        for form in formset.forms:
                            if form.has_changed():
                                obj = self.save_form(request, form, change=True)
                                self.save_model(request, obj, form, change=True)
                                self.save_related(request, form, formsets=[], change=True)
                                self.log_change(request, obj, self.construct_change_message(request, form, []))
                                changed += 1
                    if changed:
                        name = model_ngettext(self.opts, changed)
                        msg = ngettext(
                            "%(count)s %(name)s was changed successfully.",
                            "%(count)s %(name)s were changed successfully.",
                            changed,
                        )
                        self.message_user(request, msg % {"count": changed, "name": name}, messages.SUCCESS)
                    return HttpResponseRedirect(request.get_full_path())
            else:
                formset = FormSet(queryset=cast("models.QuerySet[Any]", cl.page.object_list))
            cl.formset = formset

        context = self.page_context(
            request,
            cl=cl,
            title=cl.title,
            subtitle=None,
            actions=actions,
            action_checkbox_name=ACTION_CHECKBOX_NAME,
            actions_selection_counter=self.actions_selection_counter,
            formset=formset,
            media=self.media
            + (formset.media if formset is not None else forms.Media())
            + (cl.filter_form.media if cl.filter_form is not None else forms.Media()),
            export_formats=self.get_export_formats(request) if self.has_export_permission(request) else [],
            export_url=reverse(self.url_name("export"), current_app=self.admin_site.name),
            import_url=(
                reverse(self.url_name("import"), current_app=self.admin_site.name)
                if self.has_import_permission(request) and self.get_import_formats(request)
                else ""
            ),
            **(extra_context or {}),
        )
        return self.render(request, self._templates(self.change_list_template, "change_list.html"), context)

    def _get_edited_object_pks(self, request: HttpRequest, prefix: str) -> list[str]:
        pk_name = self.opts.pk.name
        start, end = f"{prefix}-", f"-{pk_name}"
        return [
            cast("str", value)
            for key, value in request.POST.items()
            if key.startswith(start) and key.endswith(end) and key[len(start) : -len(end)].isdigit()
        ]

    def add_view(
        self, request: HttpRequest, form_url: str = "", extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        return self.changeform_view(request, None, form_url, extra_context)

    def change_view(
        self, request: HttpRequest, object_id: str, form_url: str = "", extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        return self.changeform_view(request, object_id, form_url, extra_context)

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._changeform_view(request, object_id, form_url, extra_context)

    def _create_formsets(
        self, request: HttpRequest, obj: models.Model | None, change: bool
    ) -> tuple[list[Any], list[InlineModelAdmin]]:
        formsets: list[Any] = []
        inline_instances: list[InlineModelAdmin] = []
        prefixes: dict[str, int] = {}
        for FormSet, inline in self.get_formsets_with_inlines(request, obj if change else None):  # noqa: N806
            prefix = FormSet.get_default_prefix()
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
            if prefixes[prefix] != 1 or not prefix:
                prefix = f"{prefix}-{prefixes[prefix]}"
            formset = FormSet(**self.get_formset_kwargs(request, obj, inline, prefix))
            # A view-only inline posts nothing for its rows, so they skip validation unless deleted.
            if not inline.has_change_permission(request, obj if change else None):
                for index, form in enumerate(formset.initial_forms):
                    deleted = (
                        inline.has_delete_permission(request, obj)
                        and f"{formset.prefix}-{index}-DELETE" in request.POST
                    )
                    if not deleted:
                        form._errors = {}
                        form.cleaned_data = form.initial
            formsets.append(formset)
            inline_instances.append(inline)
        return formsets, inline_instances

    def get_formset_kwargs(
        self, request: HttpRequest, obj: models.Model | None, inline: InlineModelAdmin, prefix: str
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"instance": obj, "prefix": prefix, "queryset": inline.get_queryset(request)}
        if request.method == "POST":
            kwargs.update(data=request.POST.copy(), files=request.FILES, save_as_new="_saveasnew" in request.POST)
        return kwargs

    def get_inline_formsets(
        self,
        request: HttpRequest,
        formsets: list[Any],
        inline_instances: list[InlineModelAdmin],
        obj: models.Model | None = None,
    ) -> list[InlineAdminFormSet]:
        can_edit_parent = self.has_change_permission(request, obj) if obj else self.has_add_permission(request)
        wrapped = []
        for inline, formset in zip(inline_instances, formsets, strict=True):
            if can_edit_parent:
                permissions = {
                    "has_add_permission": inline.has_add_permission(request, obj),
                    "has_change_permission": inline.has_change_permission(request, obj),
                    "has_delete_permission": inline.has_delete_permission(request, obj),
                }
            else:
                permissions = dict.fromkeys(
                    ("has_add_permission", "has_change_permission", "has_delete_permission"), False
                )
                formset.extra = formset.max_num = 0
            wrapped.append(
                InlineAdminFormSet(
                    inline,
                    formset,
                    list(inline.get_fieldsets(request, obj)),
                    list(inline.get_readonly_fields(request, obj)),
                    has_view_permission=inline.has_view_permission(request, obj),
                    **permissions,
                ),
            )
        return wrapped

    def _changeform_view(
        self, request: HttpRequest, object_id: str | None, form_url: str, extra_context: dict[str, Any] | None
    ) -> HttpResponse:
        if request.method == "POST" and "_saveasnew" in request.POST:
            object_id = None
        add = object_id is None
        if add:
            if not self.has_add_permission(request):
                raise PermissionDenied
            obj = None
        else:
            obj = self.get_object(request, unquote(object_id))  # type: ignore[arg-type]
            if obj is None:
                if not self.has_view_or_change_permission(request):
                    raise PermissionDenied
                return self._get_obj_does_not_exist_redirect(request, object_id)  # type: ignore[arg-type]
            if not self.has_view_or_change_permission(request, obj):
                raise PermissionDenied

        fieldsets = self.get_fieldsets(request, obj)
        fields = flatten_fieldsets(cast("_FieldsetSpec", fieldsets))
        ModelForm = self.get_form(request, obj, change=not add, fields=fields)  # noqa: N806
        form_validated = False
        if request.method == "POST":
            if not add and not self.has_change_permission(request, obj):
                raise PermissionDenied
            form = ModelForm(request.POST, request.FILES, instance=obj)
            formsets, inline_instances = self._create_formsets(request, form.instance, change=not add)
            form_validated = form.is_valid()
            new_object = self.save_form(request, form, change=not add) if form_validated else form.instance
            if all_valid(formsets) and form_validated:
                self.save_model(request, new_object, form, not add)
                self.save_related(request, form, formsets, not add)
                change_message = self.construct_change_message(request, form, formsets, add)
                if add:
                    self.log_addition(request, new_object, change_message)
                    return self.response_add(request, new_object)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)
            form_validated = False
        elif add:
            form = ModelForm(initial=self.get_changeform_initial_data(request))
            formsets, inline_instances = self._create_formsets(request, form.instance, change=False)
        else:
            form = ModelForm(instance=obj)
            formsets, inline_instances = self._create_formsets(request, obj, change=True)

        can_change = add or self.has_change_permission(request, obj)
        readonly_fields = (
            self.get_readonly_fields(request, obj)
            if can_change
            else flatten_fieldsets(cast("_FieldsetSpec", fieldsets))
        )
        admin_form = AdminForm(
            form,
            list(fieldsets),
            self.get_prepopulated_fields(request, obj) if can_change else {},
            readonly_fields,
            model_admin=self,
        )
        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        media = self.media + admin_form.media
        for inline_formset in inline_formsets:
            media += inline_formset.media

        if add:
            title = _("Add %s")
        elif self.has_change_permission(request, obj):
            title = _("Change %s")
        else:
            title = _("View %s")
        error_count = len(form.errors) + sum(inline.error_count() for inline in inline_formsets)
        context = self.page_context(
            request,
            title=title % self.opts.verbose_name,
            subtitle=str(obj) if obj else None,
            adminform=admin_form,
            object_id=object_id,
            original=obj,
            media=media,
            inline_admin_formsets=inline_formsets,
            error_count=error_count,
            errors=error_count,
            **(extra_context or {}),
        )
        if request.method == "POST" and not form_validated and "_saveasnew" in request.POST:
            context["show_save"] = False
            context["show_save_and_continue"] = False
            add = False
        return self.render_change_form(request, context, add=add, change=not add, obj=obj, form_url=form_url)

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: models.Model | None = None,
    ) -> HttpResponse:
        can_add = self.has_add_permission(request)
        has_change = self.has_change_permission(request, obj)
        has_view = self.has_view_permission(request, obj)
        editable_inlines = any(
            inline.has_add_permission or inline.has_change_permission or inline.has_delete_permission
            for inline in context.get("inline_admin_formsets", ())
        )
        # The same buttons as Django's submit_row tag.
        can_save = (has_change and change) or (can_add and add) or editable_inlines
        show_save = context.get("show_save", True) and can_save
        history = bool(obj) and _log_entries_installed() and self.has_view_or_change_permission(request, obj)
        context.update(
            {
                "add": add,
                "change": change,
                "has_add_permission": can_add,
                "has_change_permission": has_change,
                "has_view_permission": has_view,
                "has_delete_permission": self.has_delete_permission(request, obj),
                "has_editable_inline_admin_formsets": editable_inlines,
                "has_file_field": context["adminform"].form.is_multipart()
                or any(inline.formset.is_multipart() for inline in context.get("inline_admin_formsets", ())),
                "form_url": form_url,
                "content_type_id": get_content_type_for_model(self.model).pk
                if apps.is_installed("django.contrib.contenttypes")
                else None,
                "save_as": self.save_as,
                "save_on_top": self.save_on_top,
                "view_on_site_url": self.get_view_on_site_url(obj),
                "history_url": self.with_preserved_filters(
                    request, reverse(self.url_name("history"), args=(quote(obj.pk),))
                )
                if history and obj
                else "",
                "delete_url": self.with_preserved_filters(
                    request, reverse(self.url_name("delete"), args=(quote(obj.pk),))
                )
                if obj and change and context.get("show_delete", True) and self.has_delete_permission(request, obj)
                else "",
                "show_save": show_save,
                "show_save_and_continue": can_save and has_view and context.get("show_save_and_continue", True),
                "show_save_and_add_another": can_add
                and (not self.save_as or add)
                and can_save
                and context.get("show_save_and_add_another", True),
                "show_save_as_new": change and self.save_as and can_add,
                "show_close": not show_save,
                "can_change": has_change or editable_inlines,
            }
        )
        templates = self._templates(
            self.add_form_template if add and self.add_form_template else self.change_form_template, "change_form.html"
        )
        return self.render(request, templates, context)

    def delete_view(
        self, request: HttpRequest, object_id: str, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._delete_view(request, object_id, extra_context)

    def _delete_view(self, request: HttpRequest, object_id: str, extra_context: dict[str, Any] | None) -> HttpResponse:
        obj = self.get_object(request, unquote(object_id))
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, object_id)
        deleted_objects, model_count, perms_needed, protected = self.get_deleted_objects([obj], request)
        if request.method == "POST" and not protected:
            if perms_needed:
                raise PermissionDenied
            obj_display = str(obj)
            obj_id = obj.serializable_value(self.opts.pk.attname)
            self.log_deletions(request, [obj])
            self.delete_model(request, obj)
            return self.response_delete(request, obj_display, obj_id)
        object_name = str(self.opts.verbose_name)
        title = _("Cannot delete %(name)s") % {"name": object_name} if perms_needed or protected else _("Delete")
        context = self.page_context(
            request,
            title=title,
            subtitle=None,
            object_name=object_name,
            object=obj,
            original=obj,
            deleted_objects=deleted_objects,
            delete_confirmation_max_display=self.delete_confirmation_max_display,
            model_count=list(dict(model_count).items()),
            perms_lacking=sorted(str(name) for name in perms_needed),
            protected=protected,
            change_url=self.with_preserved_filters(request, reverse(self.url_name("change"), args=(quote(obj.pk),))),
            media=self.media,
            **(extra_context or {}),
        )
        return self.render(
            request, self._templates(self.delete_confirmation_template, "delete_confirmation.html"), context
        )

    def history_view(
        self, request: HttpRequest, object_id: str, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        if not _log_entries_installed():
            raise Http404
        from django.contrib.admin.models import LogEntry

        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, object_id)
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        entries = (
            LogEntry.objects.filter(object_id=unquote(object_id), content_type=get_content_type_for_model(self.model))
            .select_related("user")
            .order_by("-action_time")
        )
        paginator = self.get_paginator(request, entries, 100)
        page = paginator.get_page(request.GET.get("p", 1))
        context = self.page_context(
            request,
            title=_("Change history: %s") % obj,
            subtitle=None,
            action_list=list(page.object_list),
            page_obj=page,
            page_range=list(paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)),
            object=obj,
            original=obj,
            change_url=self.with_preserved_filters(request, reverse(self.url_name("change"), args=(quote(obj.pk),))),
            media=self.media,
            **(extra_context or {}),
        )
        return self.render(request, self._templates(self.object_history_template, "object_history.html"), context)


class InlineModelAdmin(BaseModelAdmin):
    """Rows of a related model edited on the parent's change page."""

    model: type[models.Model]
    fk_name: str | None = None
    formset: type[FormworkBaseInlineFormSet] = FormworkBaseInlineFormSet
    extra = 3
    min_num: int | None = None
    max_num: int | None = None
    template: str | None = None
    verbose_name: str | StrPromise | None = None
    verbose_name_plural: str | StrPromise | None = None
    can_delete = True
    show_change_link = False
    classes: Sequence[str] | None = None
    #: ``"tabular"`` draws a table row per object, ``"stacked"`` a card per object.
    layout = "stacked"

    def __init__(self, parent_model: type[models.Model], admin_site: Any) -> None:
        self.admin_site = admin_site
        self.parent_model = parent_model
        self.has_registered_model = admin_site.is_registered(self.model)
        super().__init__()
        meta = self.model._meta
        if self.verbose_name_plural is None:
            self.verbose_name_plural = (
                meta.verbose_name_plural if self.verbose_name is None else f"{self.verbose_name}s"
            )
        if self.verbose_name is None:
            self.verbose_name = meta.verbose_name

    @property
    def media(self) -> forms.Media:
        return forms.Media()

    def get_extra(self, request: HttpRequest, obj: models.Model | None = None, **kwargs: Any) -> int:
        return self.extra

    def get_min_num(self, request: HttpRequest, obj: models.Model | None = None, **kwargs: Any) -> int | None:
        return self.min_num

    def get_max_num(self, request: HttpRequest, obj: models.Model | None = None, **kwargs: Any) -> int | None:
        return self.max_num

    def has_add_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        if self.opts.auto_created:
            return self._has_any_perms_for_target_model(request, ["change"])
        return super().has_add_permission(request)

    def has_change_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        if self.opts.auto_created:
            return self._has_any_perms_for_target_model(request, ["change"])
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        if self.opts.auto_created:
            return self._has_any_perms_for_target_model(request, ["change"])
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request: HttpRequest, obj: models.Model | None = None) -> bool:
        if self.opts.auto_created:
            return self._has_any_perms_for_target_model(request, ["view", "change"])
        return super().has_view_permission(request, obj)

    def _has_any_perms_for_target_model(self, request: HttpRequest, perms: list[str]) -> bool:
        # An auto-created through model takes the permissions of the model on the far side.
        opts = self.opts
        for field in opts.fields:
            if field.remote_field and field.remote_field.model != self.parent_model:
                opts = field.remote_field.model._meta
                break
        return any(
            request.user.has_perm(f"{opts.app_label}.{get_permission_codename(perm, opts)}")  # ty: ignore[unresolved-attribute]
            for perm in perms
        )

    def get_formset(
        self, request: HttpRequest, obj: models.Model | None = None, **kwargs: Any
    ) -> type[FormworkBaseInlineFormSet]:
        fields = (
            kwargs.pop("fields")
            if "fields" in kwargs
            else flatten_fieldsets(cast("_FieldsetSpec", self.get_fieldsets(request, obj)))
        )
        excluded = self.get_exclude(request, obj)
        exclude = [] if excluded is None else list(excluded)
        exclude.extend(name for name in self.get_readonly_fields(request, obj) if isinstance(name, str))
        if excluded is None and hasattr(self.form, "_meta") and self.form._meta.exclude:
            exclude.extend(self.form._meta.exclude)
        can_delete = self.can_delete and self.has_delete_permission(request, obj)
        defaults: dict[str, Any] = {
            "form": self.form,
            "formset": self.formset,
            "fk_name": self.fk_name,
            "fields": fields,
            "exclude": exclude or None,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            "extra": self.get_extra(request, obj, **kwargs),
            "min_num": self.get_min_num(request, obj, **kwargs),
            "max_num": self.get_max_num(request, obj, **kwargs),
            "can_delete": can_delete,
            **kwargs,
        }
        can_change = self.has_change_permission(request, obj) if request else True
        can_add = self.has_add_permission(request, obj) if request else True
        defaults["form"] = _delete_protected_form(
            defaults["form"], self, request, can_change=can_change, can_add=can_add
        )
        if defaults["fields"] is None and not modelform_defines_fields(defaults["form"]):
            defaults["fields"] = forms.ALL_FIELDS
        return formwork_inlineformset_factory(self.parent_model, self.model, **defaults)

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Any]:
        queryset = super().get_queryset(request)
        if not self.has_view_or_change_permission(request):
            queryset = queryset.none()
        return queryset

    def _get_form_for_get_fields(self, request: HttpRequest, obj: models.Model | None = None) -> Any:
        return self.get_formset(request, obj, fields=None).form


def _delete_protected_form(
    base: type[forms.ModelForm[Any]], inline: InlineModelAdmin, request: HttpRequest, *, can_change: bool, can_add: bool
) -> type[forms.ModelForm[Any]]:
    """The inline's form, refusing a deletion that would cascade into protected rows."""

    class DeleteProtectedModelForm(base):  # type: ignore[valid-type, misc]  # ty: ignore[unsupported-base]
        def hand_clean_DELETE(self) -> None:  # noqa: N802
            if not self.cleaned_data.get(DELETION_FIELD_NAME, False):
                return
            using = router.db_for_write(self._meta.model)
            collector = NestedObjects(using=using)
            if self.instance._state.adding:
                return
            collector.collect([self.instance])  # ty: ignore[invalid-argument-type]
            if collector.protected:
                objs = [
                    _("%(class_name)s %(instance)s") % {"class_name": capfirst(p._meta.verbose_name), "instance": p}
                    for p in collector.protected
                ]
                params = {
                    "class_name": self._meta.model._meta.verbose_name,
                    "instance": self.instance,
                    "related_objects": get_text_list(objs, _("and")),
                }
                msg = _(
                    "Deleting %(class_name)s %(instance)s would require deleting the following protected related objects: %(related_objects)s"
                )
                raise ValidationError(msg, code="deleting_protected", params=params)

        def is_valid(self) -> bool:
            result = super().is_valid()
            self.hand_clean_DELETE()
            return result

        def has_changed(self) -> bool:
            # A form the user cannot change or add counts as unchanged, so it never saves.
            if not can_change and not self.instance._state.adding:
                return False
            if not can_add and self.instance._state.adding:
                return False
            return super().has_changed()

    DeleteProtectedModelForm.__name__ = base.__name__
    return DeleteProtectedModelForm


class StackedInline(InlineModelAdmin):
    layout = "stacked"


class TabularInline(InlineModelAdmin):
    layout = "tabular"
