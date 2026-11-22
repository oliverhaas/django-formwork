"""The formwork widget each model field gets on an admin form, and the relation search.

One search serves every relation: its params name the site, the model and the field,
so the related admin's queryset, permissions and ``search_fields`` decide the rows.
"""

from __future__ import annotations

import copy
import datetime as dt
import re
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.apps import apps
from django.contrib.admin import widgets as django_widgets
from django.contrib.admin.utils import quote
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import models
from django.forms.models import ModelChoiceIterator
from django.forms.utils import to_current_timezone
from django.http import Http404
from django.urls import reverse
from django.utils.formats import get_format
from django.utils.http import urlencode
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _

from django_formwork.forms import FormworkForm
from django_formwork.widgets import (
    ClearableFileInput,
    DatePicker,
    DateTimePicker,
    Select,
    SelectMultiple,
    Textarea,
    TextInput,
    ToggleInput,
)
from django_formwork.widgets._base import _FormworkTemplatesMixin

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel
    from django.forms.renderers import BaseRenderer
    from django.http import HttpRequest

__all__ = [
    "FORMFIELD_FOR_DBFIELD_DEFAULTS",
    "RELATION_SEARCH_KEY",
    "AdminDateTimeWidget",
    "AdminDateWidget",
    "AdminSplitDateTime",
    "AdminTimeWidget",
    "RelatedChoiceField",
    "RelatedMultipleChoiceField",
    "RelatedWidgetWrapper",
    "date_input_format",
    "datetime_input_format",
    "formwork_widget",
    "relation_label",
    "relation_queryset",
    "relation_widget",
    "use_formwork_widgets",
]


def relation_queryset(request: HttpRequest, *, site: str, model: str, field: str) -> QuerySet[Any]:
    """The rows a relation's dropdown offers: the related admin's list, searched by its ``search_fields``.

    An empty ``field`` offers the rows of ``model`` itself, which an admin without ``search_fields`` pages.
    """
    # Deferred: sites imports options, which imports this module.
    from django_formwork.admin.sites import NotRegistered, get_site

    admin_site = get_site(site)
    if admin_site is None or not admin_site.has_permission(request):
        raise PermissionDenied
    try:
        source = apps.get_model(model)
        source_field = source._meta.get_field(field) if field else None
    except LookupError, ValueError, FieldDoesNotExist:
        raise Http404 from None
    if not admin_site.is_registered(source) or (source_field is not None and source_field.remote_field is None):
        raise Http404
    try:
        model_admin = admin_site.get_model_admin(source if source_field is None else source_field.remote_field.model)
    except NotRegistered:
        raise Http404 from None
    # A relation pages from here only when its admin can search, as Django's autocomplete asks.
    if source_field is not None and not model_admin.get_search_fields(request):
        raise Http404
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    queryset = model_admin.get_queryset(request)
    if source_field is not None:
        queryset = queryset.complex_filter(source_field.get_limit_choices_to())
    queryset = model_admin.choice_queryset(queryset)
    queryset, may_have_duplicates = model_admin.get_search_results(request, queryset, request.GET.get("q", "").strip())
    if may_have_duplicates:
        queryset = queryset.distinct()
    if not queryset.ordered:
        # Paging an unordered list repeats and skips rows. An annotation's GROUP BY drops the model's
        # ordering, which the field's own rows keep, so the pages follow it as they do.
        ordering = model_admin.get_ordering(request) or queryset.model._meta.ordering or ("-pk",)
        queryset = queryset.order_by(*ordering)
    return queryset


def relation_label(obj: models.Model, *, site: str, model: str, field: str) -> object:
    """A searched row as the related admin's ``choice_label()`` shows it."""
    from django_formwork.admin.sites import get_site

    admin_site = get_site(site)
    model_admin = admin_site.get_model_admin_or_none(type(obj)) if admin_site is not None else None
    return str(obj) if model_admin is None else model_admin.choice_label(obj)


class _RowsAtOnce(ModelChoiceIterator):
    """Django's options from one read of the rows, where Django's ``iterator()`` loads each row's relations alone."""

    def __iter__(self) -> Any:
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for obj in self.queryset.all():
            yield self.choice(obj)


class RelatedChoiceField(forms.ModelChoiceField):
    """A relation whose options read as the related admin's ``choice_label()`` shows them."""

    iterator = _RowsAtOnce

    def __init__(self, *args: Any, choice_label: Callable[[Any], object], **kwargs: Any) -> None:
        self.choice_label = choice_label
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj: Any) -> Any:
        return self.choice_label(obj)


class RelatedMultipleChoiceField(forms.ModelMultipleChoiceField):
    """``RelatedChoiceField`` for a many-to-many field."""

    iterator = _RowsAtOnce

    def __init__(self, *args: Any, choice_label: Callable[[Any], object], **kwargs: Any) -> None:
        self.choice_label = choice_label
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj: Any) -> Any:
        return self.choice_label(obj)


class _RelationSearch(FormworkForm):
    """Registers ``relation_queryset`` once, under a key every relation widget reuses."""

    related: forms.ModelChoiceField[Any] = forms.ModelChoiceField(
        queryset=None,
        widget=Select(search_queryset=relation_queryset, search_label=relation_label, search_decorator=None),
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


class RelatedWidgetWrapper(_FormworkTemplatesMixin, forms.Widget):
    """A relation's widget, with links that add a row or edit the chosen one in a dialog.

    The same role as Django's ``RelatedFieldWidgetWrapper``. The related admin opens with ``_popup=1``.
    The Edit and Add links go to the end of the field's label row through ``label_links()``. A field
    in ``raw_id_fields`` also gets a button next to the widget that picks the row from the related
    list, as Django's ``ForeignKeyRawIdWidget`` does."""

    template_name = "formwork_admin/widgets/related_widget_wrapper.html"
    label_links_template_name = "formwork_admin/widgets/related_label_links.html"

    def __init__(
        self,
        widget: forms.Widget,
        rel: ManyToOneRel | ManyToManyRel,
        admin_site: Any,
        *,
        can_add_related: bool = False,
        can_change_related: bool = False,
        can_view_related: bool = False,
        can_lookup_related: bool = False,
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
        self.can_lookup_related = can_lookup_related
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

    def use_required_attribute(self, initial: Any) -> bool:
        return self.widget.use_required_attribute(initial)

    @property
    def media(self) -> forms.Media:
        return self.widget.media

    @property
    def choices(self) -> Any:
        return getattr(self.widget, "choices", ())

    @choices.setter
    def choices(self, value: Any) -> None:
        self.widget.choices = value  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]

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
        # The widget's own render, which a stub replaces in the saved rows of a tabular inline.
        rendered = self.widget.render(name, value, attrs, renderer)
        wrapper_context = self.get_wrapper_context(name, rendered, value)
        # Widget declares template_name optional; this class always sets it.
        return self._render(self.template_name, wrapper_context, renderer)  # ty: ignore[invalid-argument-type]

    def label_links(self, name: str, value: Any, renderer: BaseRenderer | None = None) -> SafeString:
        """The Edit (or View) and Add links, for the field template's label row."""
        context = self.get_wrapper_context(name, "", value)
        if "change_related_template_url" not in context and "add_related_url" not in context:
            return SafeString()
        return self._render(self.label_links_template_name, context, renderer)

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
        if self.can_lookup_related:
            # The rows the relation offers, as Django's raw ID lookup narrows the list to them.
            limit_choices_to: Any = self.rel.limit_choices_to
            if callable(limit_choices_to):
                limit_choices_to = limit_choices_to()
            params = django_widgets.url_params_from_lookup_dict(limit_choices_to)
            url = self._related_url("changelist")
            context["lookup_url"] = f"{url}?{urlencode(params)}" if params else url
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


# The strftime codes the admin's formats keep, as the codes of Django's ``date`` filter.
_DATE_FILTER_CODES = {"Y": "Y", "y": "y", "m": "m", "d": "d", "H": "H", "M": "i"}


def _input_format(strftime: str, codes: str, fallback: str) -> tuple[str, str]:
    if not set(re.findall(r"%(.)", strftime)) <= set(codes):
        strftime = fallback
    # Other letters are text.
    return strftime, re.sub(
        r"%(.)|([A-Za-z\\])", lambda match: _DATE_FILTER_CODES[match[1]] if match[1] else f"\\{match[2]}", strftime
    )


def date_input_format() -> tuple[str, str]:
    """How the admin writes a date to type: the language's first ``DATE_INPUT_FORMATS``, as Django's admin does.

    Returns the strftime format and the same format in the syntax of Django's ``date`` filter."""
    return _input_format(str(get_format("DATE_INPUT_FORMATS")[0]), "Yymd", "%Y-%m-%d")


def datetime_input_format() -> tuple[str, str]:
    """How the admin writes a date and a time to type: the language's first ``DATETIME_INPUT_FORMATS``, to the minute.

    Returns the strftime format and the same format in the syntax of Django's ``date`` filter."""
    strftime = re.sub(r"[:.]%S(\.%f)?", "", str(get_format("DATETIME_INPUT_FORMATS")[0]))
    return _input_format(strftime, "YymdHM", "%Y-%m-%d %H:%M")


class AdminDateWidget(DatePicker):
    """The calendar dropdown, with the date in the format of ``date_input_format()``."""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs, format=date_input_format()[0])


class NullBooleanSelect(Select):
    """The dropdown over Unknown, Yes and No; it reads and posts values as Django's ``NullBooleanSelect``."""

    format_value = forms.NullBooleanSelect.format_value  # type: ignore[assignment]  # ty: ignore[incompatible-method-override]
    value_from_datadict = forms.NullBooleanSelect.value_from_datadict

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        choices = (("unknown", _("Unknown")), ("true", _("Yes")), ("false", _("No")))
        super().__init__(attrs, choices=choices, show_search=False)


def _has_seconds(value: Any) -> bool:
    if isinstance(value, dt.time):
        return bool(value.second)
    seconds = str(value or "").split(":")[2:3]
    return bool(seconds) and seconds[0].strip("0.") != ""


class AdminTimeWidget(forms.TimeInput):
    """The browser's time input, to the minute, and to the second for a time with seconds.

    A time that nobody touched posts back the same value, so it saves unchanged."""

    input_type = "time"

    def format_value(self, value: Any) -> str | None:
        if isinstance(value, dt.time):
            return value.strftime("%H:%M:%S" if _has_seconds(value) else "%H:%M")
        return super().format_value(value)

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        if _has_seconds(value):
            context["widget"]["attrs"]["step"] = 1
        return context


class AdminDateTimeWidget(DateTimePicker):
    """The calendar dropdown with a time, showing the value in the format of ``datetime_input_format()``."""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs, format=datetime_input_format()[1])


FORMFIELD_FOR_DBFIELD_DEFAULTS: dict[type[models.Field[Any, Any]], dict[str, Any]] = {
    models.DateTimeField: {"widget": AdminDateTimeWidget},
    models.DateField: {"widget": AdminDateWidget},
    models.TimeField: {"widget": AdminTimeWidget},
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


class AdminSplitDateTime(AdminDateTimeWidget):
    """The date and time picker for a ``SplitDateTimeField``, which takes the day and the time apart."""

    def decompress(self, value: Any) -> list[Any]:
        # The field compares its initial value with the posted one in parts.
        if value:
            value = to_current_timezone(value)
            return [value.date(), value.time()]
        return [None, None]

    def value_from_datadict(self, data: Any, files: Any, name: str) -> list[str]:
        value = str(super().value_from_datadict(data, files, name) or "")
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T(.+)", value)
        # Text that names no day goes to the date field, which reports it.
        return [match[1], match[2]] if match else [value, ""]

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(value, (list, tuple)):
            value = "T".join(str(part) for part in value if part)
        return super().get_context(name, value, attrs)


# The classes Django's admin widgets add for its own CSS and JavaScript.
_DJANGO_CLASSES = frozenset(
    {
        "vDateField",
        "vTimeField",
        "vLargeTextField",
        "vTextField",
        "vURLField",
        "vIntegerField",
        "vBigIntegerField",
        "vUUIDField",
        "radiolist",
        "inline",
        "selectfilter",
        "selectfilterstacked",
        "admin-autocomplete",
    }
)

# A choice field with radio buttons in a row: Django's HORIZONTAL radio_fields, or its "radiolist inline" class.
RADIO_ROW_CLASS = "flex-row flex-wrap gap-x-5"

# Builds formwork's widget from the attrs, Django's widget, the form field and the admin site.
_Builder = Callable[[dict[str, Any], Any, forms.Field, Any], forms.Widget]


def _attrs_only(build: Callable[[dict[str, Any]], forms.Widget]) -> _Builder:
    return lambda attrs, _widget, _field, _admin_site: build(attrs)


def _with_class(attrs: dict[str, Any], css_class: str) -> dict[str, Any]:
    return {**attrs, "class": f"{attrs['class']} {css_class}" if attrs.get("class") else css_class}


def _textarea(attrs: dict[str, Any]) -> forms.Widget:
    # Django's Textarea defaults of 40 columns and 10 rows are strings; numbers come from the project.
    attrs = {key: value for key, value in attrs.items() if (key, value) not in {("cols", "40"), ("rows", "10")}}
    return Textarea({"rows": 4, **attrs})


def _radio_select(attrs: dict[str, Any], widget: Any, _field: forms.Field, _admin_site: Any) -> forms.Widget:
    if "inline" in str(widget.attrs.get("class", "")).split():
        attrs = _with_class(attrs, RADIO_ROW_CLASS)
    return forms.RadioSelect(attrs)


def _split_datetime(attrs: dict[str, Any], _widget: Any, field: forms.Field, _admin_site: Any) -> forms.Widget:
    return AdminSplitDateTime(attrs) if isinstance(field, forms.MultiValueField) else AdminDateTimeWidget(attrs)


def _relation(attrs: dict[str, Any], widget: Any, field: forms.Field, admin_site: Any) -> forms.Widget:
    # The autocomplete widgets name the model field; the raw id widgets name its relation.
    db_field = widget.field if hasattr(widget, "field") else widget.rel.field
    single = isinstance(db_field, models.ForeignKey)
    return relation_widget(
        db_field,
        admin_site,
        searchable=admin_site.is_searchable(db_field.remote_field.model),
        attrs=attrs,
        **({"allow_clear": not field.required} if single else {}),
    )


_FORMWORK_WIDGETS: dict[type[forms.Widget], _Builder] = {
    django_widgets.BaseAdminDateWidget: _attrs_only(AdminDateWidget),
    django_widgets.AdminDateWidget: _attrs_only(AdminDateWidget),
    django_widgets.BaseAdminTimeWidget: _attrs_only(AdminTimeWidget),
    django_widgets.AdminTimeWidget: _attrs_only(AdminTimeWidget),
    django_widgets.AdminSplitDateTime: _split_datetime,
    django_widgets.AdminRadioSelect: _radio_select,
    django_widgets.AdminTextareaWidget: _attrs_only(_textarea),
    django_widgets.AdminTextInputWidget: _attrs_only(TextInput),
    django_widgets.AdminEmailInputWidget: _attrs_only(partial(TextInput, input_type="email")),
    django_widgets.AdminURLFieldWidget: _attrs_only(partial(TextInput, input_type="url")),
    django_widgets.AdminIntegerFieldWidget: _attrs_only(forms.NumberInput),
    django_widgets.AdminBigIntegerFieldWidget: _attrs_only(forms.NumberInput),
    django_widgets.AdminUUIDInputWidget: _attrs_only(lambda attrs: TextInput(_with_class(attrs, "font-mono"))),
    django_widgets.AdminFileWidget: _attrs_only(ClearableFileInput),
    django_widgets.FilteredSelectMultiple: _attrs_only(SelectMultiple),
    django_widgets.AutocompleteSelect: _relation,
    django_widgets.AutocompleteSelectMultiple: _relation,
    django_widgets.ForeignKeyRawIdWidget: _relation,
    django_widgets.ManyToManyRawIdWidget: _relation,
}


def formwork_widget(widget: forms.Widget, field: forms.Field, admin_site: Any) -> forms.Widget | None:
    """Formwork's widget in place of one of Django's admin widgets on ``field``, or ``None`` for any other widget.

    Only Django's own classes are replaced; a subclass keeps its markup and scripts. The new widget
    keeps the attrs, without the classes that only Django's admin CSS and JavaScript read."""
    kind = type(widget)
    if kind is django_widgets.RelatedFieldWidgetWrapper or kind is RelatedWidgetWrapper:
        wrapper = cast("Any", widget)
        inner = formwork_widget(wrapper.widget, field, admin_site)
        if inner is None and kind is RelatedWidgetWrapper:
            return None
        return RelatedWidgetWrapper(
            inner or wrapper.widget,
            wrapper.rel,
            admin_site,
            can_add_related=bool(wrapper.can_add_related),
            can_change_related=wrapper.can_change_related,
            can_view_related=wrapper.can_view_related,
        )
    build = _FORMWORK_WIDGETS.get(kind)
    if build is None:
        return None
    # Django's wrapper marks the widget it wraps for its own JavaScript.
    attrs = {key: value for key, value in widget.attrs.items() if key != "data-context"}
    classes = [name for name in str(attrs.pop("class", "")).split() if name not in _DJANGO_CLASSES]
    if classes:
        attrs["class"] = " ".join(classes)
    new = build(attrs, widget, field, admin_site)
    # What Field.__init__ sets on the widget it gets.
    new.is_required = field.required
    new.is_localized = bool(field.localize)
    new.attrs.update(field.widget_attrs(new))
    if isinstance(field, forms.ChoiceField):
        new.choices = field.choices  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]
    return new


def use_formwork_widgets(form_class: type[forms.ModelForm[Any]], admin_site: Any) -> None:
    """Puts formwork's widgets in place of Django's admin widgets on a form class the admin built.

    Each such field is copied, so the class the project declared keeps its own."""
    for name, field in form_class.base_fields.items():
        widget = formwork_widget(field.widget, field, admin_site)
        if widget is not None:
            swapped = copy.copy(field)
            swapped.widget = widget
            form_class.base_fields[name] = swapped
