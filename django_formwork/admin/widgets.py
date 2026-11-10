"""The formwork widget each model field gets on an admin form, and the relation search.

One search serves every relation: its params name the site, the model and the field,
so the related admin's queryset, permissions and ``search_fields`` decide the rows.
"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

from django import forms
from django.apps import apps
from django.contrib.admin.utils import quote
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import models
from django.forms.utils import to_current_timezone
from django.http import Http404
from django.urls import reverse
from django.utils.formats import get_format
from django.utils.translation import gettext_lazy as _

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
    from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel
    from django.forms.renderers import BaseRenderer
    from django.http import HttpRequest
    from django.utils.safestring import SafeString

__all__ = [
    "FORMFIELD_FOR_DBFIELD_DEFAULTS",
    "RELATION_SEARCH_KEY",
    "AdminDateTimeWidget",
    "AdminDateWidget",
    "RelatedWidgetWrapper",
    "date_input_format",
    "relation_queryset",
    "relation_widget",
]


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


# The query parameters of a related admin page that opens in the dialog, as in Django's admin.
IS_POPUP_VAR = "_popup"
TO_FIELD_VAR = "_to_field"


class RelatedWidgetWrapper(forms.Widget):
    """A relation's widget, with buttons that add a row or change the chosen one in a dialog.

    The same role as Django's ``RelatedFieldWidgetWrapper``. The related admin opens with ``_popup=1``."""

    template_name = "formwork_admin/widgets/related_widget_wrapper.html"

    def __init__(
        self,
        widget: forms.Widget,
        rel: ManyToOneRel | ManyToManyRel,
        admin_site: Any,
        *,
        can_add_related: bool = False,
        can_change_related: bool = False,
        can_view_related: bool = False,
    ) -> None:
        self.needs_multipart_form = widget.needs_multipart_form
        self.attrs = widget.attrs
        self.widget = widget
        self.rel = rel
        self.admin_site = admin_site
        self.can_add_related = can_add_related
        # Several chosen rows have no one row to change.
        single = not getattr(widget, "allow_multiple_selected", False)
        self.can_change_related = single and can_change_related
        self.can_view_related = single and can_view_related
        self.use_fieldset = widget.use_fieldset

    def __deepcopy__(self, memo: dict[int, Any]) -> RelatedWidgetWrapper:
        obj = copy.copy(self)
        obj.widget = copy.deepcopy(self.widget, memo)
        obj.attrs = obj.widget.attrs
        memo[id(self)] = obj
        return obj

    @property
    def is_hidden(self) -> bool:
        return self.widget.is_hidden

    @property
    def media(self) -> forms.Media:
        return self.widget.media

    @property
    def choices(self) -> Any:
        return getattr(self.widget, "choices", ())

    @choices.setter
    def choices(self, value: Any) -> None:
        self.widget.choices = value  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]

    def _related_url(self, action: str, *args: Any) -> str:
        opts = self.rel.model._meta
        return reverse(
            f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_{action}",
            args=args,
            current_app=self.admin_site.name,
        )

    def render(
        self, name: str, value: Any, attrs: dict[str, Any] | None = None, renderer: BaseRenderer | None = None
    ) -> SafeString:
        context = self.widget.get_context(name, value, attrs)
        # The stubs lack Widget._render.
        render = self.widget._render  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        rendered = render(self.widget.template_name, context, renderer)
        wrapper_context = self.get_wrapper_context(name, rendered, context["widget"].get("value"))
        return self._render(self.template_name, wrapper_context, renderer)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]

    def get_wrapper_context(self, name: str, rendered_widget: str, value: Any = None) -> dict[str, Any]:
        opts = self.rel.model._meta
        context: dict[str, Any] = {
            "rendered_widget": rendered_widget,
            "name": name,
            "model": opts.verbose_name,
            "model_label": opts.label_lower,
            "can_change_related": self.can_change_related,
            "can_view_related": self.can_view_related,
            # The buttons follow radio buttons or checkboxes, as wide as their labels.
            "choice_list": isinstance(self.widget, forms.RadioSelect),
            # The links open the full page; a plain click adds these and opens it in the dialog.
            "popup_query": f"{TO_FIELD_VAR}={self.rel.get_related_field().name}&{IS_POPUP_VAR}=1",
        }
        if self.can_add_related:
            context["add_related_url"] = self._related_url("add")
        if self.can_change_related or self.can_view_related:
            context["change_related_template_url"] = self._related_url("change", "__fk__")
            # Radio buttons and a native select hold the value in a list.
            if isinstance(value, list | tuple):
                value = value[0] if value else None
            if value not in (None, ""):
                context["change_related_url"] = self._related_url("change", quote(value))
        return context

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        return self.widget.value_from_datadict(data, files, name)

    def value_omitted_from_data(self, data: Any, files: Any, name: str) -> bool:
        return self.widget.value_omitted_from_data(data, files, name)

    def id_for_label(self, id_: str) -> str:
        return self.widget.id_for_label(id_)


def date_input_format() -> tuple[str, str]:
    """How the admin writes a date to type: the language's first ``DATE_INPUT_FORMATS``, as Django's admin does.

    Returns the strftime format and the same format in the syntax of Django's ``date`` filter."""
    strftime = str(get_format("DATE_INPUT_FORMATS")[0])
    if not set(re.findall(r"%(.)", strftime)) <= {"Y", "y", "m", "d"}:
        strftime = "%Y-%m-%d"
    # Y, y, m and d are the same codes in both syntaxes; other letters are text.
    return strftime, re.sub(r"%(.)|([A-Za-z\\])", lambda match: match[1] or f"\\{match[2]}", strftime)


class AdminDateWidget(DatePicker):
    """The calendar dropdown, with the date in the format of ``date_input_format()``."""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs, format=date_input_format()[0])


# The native control, to the second, so a value nobody touched saves unchanged.
_TIME_ATTRS = {"type": "time", "step": 1}


class AdminDateTimeWidget(forms.MultiWidget):
    """The calendar dropdown for the day and a time input next to it.

    The two post one value, so the field stays a ``DateTimeField``, which an import also fills."""

    template_name = "formwork_admin/widgets/split_datetime.html"
    supports_microseconds = False

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        date = AdminDateWidget({"aria-label": _("Date")})
        time = forms.TimeInput({**_TIME_ATTRS, "aria-label": _("Time")}, format="%H:%M:%S")
        super().__init__((date, time), attrs)

    def decompress(self, value: Any) -> list[Any]:
        if isinstance(value, str):
            # Posted text: the day and the time that value_from_datadict joined.
            date, _space, time = value.partition(" ")
            return [date, time]
        if value:
            value = to_current_timezone(value)
            return [value.date(), value.time()]
        return [None, None]

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        date, time = super().value_from_datadict(data, files, name)
        return f"{date or ''} {time or ''}" if date or time else ""


FORMFIELD_FOR_DBFIELD_DEFAULTS: dict[type[models.Field[Any, Any]], dict[str, Any]] = {
    models.DateTimeField: {"widget": AdminDateTimeWidget},
    models.DateField: {"widget": AdminDateWidget},
    models.TimeField: {"widget": forms.TimeInput(attrs=_TIME_ATTRS, format="%H:%M:%S")},
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
