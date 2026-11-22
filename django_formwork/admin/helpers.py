"""The change form as templates read it: fieldsets of rows, read-only values and inline formsets."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from django.contrib.admin.utils import (
    display_for_field,
    flatten_fieldsets,
    help_text_for_field,
    label_for_field,
    lookup_field,
    quote,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.forms.formsets import DELETION_FIELD_NAME
from django.urls import NoReverseMatch, reverse
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import SafeString, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from django_formwork.admin.cells import (
    annotate_rows,
    cell_for_field,
    cell_for_value,
    display_annotations,
    html,
    list_cell,
    list_html,
)
from django_formwork.admin.paginator import page_links
from django_formwork.fields import DisplayField, _DisplayBoundField

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from django.contrib.admin.options import _FieldsetSpec
    from django.core.paginator import Page, Paginator
    from django.forms import BaseForm, BoundField, Media, ModelForm
    from django.http import HttpRequest
    from django_stubs_ext import StrPromise

    from django_formwork.admin.paginator import PageLink

__all__ = [
    "AdminField",
    "AdminForm",
    "DeletedGroup",
    "DeletedObject",
    "Fieldset",
    "InlineAdminForm",
    "InlineAdminFormSet",
    "InlinePager",
    "ReadonlyField",
    "deleted_groups",
    "display_field",
    "field_name",
    "list_display_field",
    "show_display_fields",
]

# The action and delete pages name this many objects of a kind and count the rest.
FIRST_OBJECTS = 8


def _show_errors_inline(form: BaseForm) -> None:
    """Show each field error under its field, unless the form's ``Meta.error_display`` sets a display."""
    if getattr(getattr(type(form), "Meta", None), "error_display", None) is None:
        form.error_display = "inline"  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]


@dataclass
class ReadonlyField:
    """A value the form shows but does not post."""

    name: str
    label: str
    contents: SafeString
    help_text: str = ""
    is_readonly: bool = True


@dataclass
class AdminField:
    """One cell of a fieldset row: a form field or a read-only value."""

    field: BoundField | None = None
    readonly: ReadonlyField | None = None

    @property
    def name(self) -> str:
        return self.field.name if self.field is not None else cast("ReadonlyField", self.readonly).name

    @property
    def is_hidden(self) -> bool:
        return self.field is not None and self.field.is_hidden

    @property
    def errors(self) -> Any:
        return self.field.errors if self.field is not None else ()

    @property
    def label_beside(self) -> bool:
        """A toggle or a checkbox without text of its own: the field label sits beside it, not above."""
        if self.field is None:
            return False
        widget_type = self.field.widget_type
        return widget_type == "toggle" or (
            widget_type == "checkbox" and not getattr(self.field.field.widget, "text", "")
        )


@dataclass
class Fieldset:
    """A titled group of rows; ``collapse`` in ``classes`` folds it behind its title."""

    name: str | StrPromise | None
    rows: list[list[AdminField]]
    description: str = ""
    classes: tuple[str, ...] = ()

    @property
    def collapsible(self) -> bool:
        return "collapse" in self.classes

    @property
    def has_errors(self) -> bool:
        return any(cell.errors for row in self.rows for cell in row)

    @property
    def is_wide(self) -> bool:
        return "wide" in self.classes


def readonly_contents(name: Any, obj: models.Model | None, model_admin: Any) -> SafeString:
    """A read-only field's value, linked to the related object's change page where the site has one."""
    empty = model_admin.get_empty_value_display()
    if obj is None:
        return mark_safe(conditional_escape(empty))  # noqa: S308
    try:
        model_field, attr, value = lookup_field(name, obj, model_admin)
    except AttributeError, ValueError, ObjectDoesNotExist:
        return mark_safe(conditional_escape(empty))  # noqa: S308
    if model_field is None:
        boolean = getattr(attr, "boolean", False)
        cell = cell_for_value(value, getattr(attr, "empty_value_display", empty), boolean=boolean)
        return mark_safe(cell["text"] if cell["kind"] == "html" else html(cell))  # noqa: S308
    if isinstance(model_field.remote_field, models.ManyToOneRel | models.OneToOneRel) and value is not None:
        return _related_link(value, model_admin)
    if isinstance(model_field, models.ManyToManyField):
        related = list(value.all()) if value is not None else []
        if not related:
            return mark_safe(conditional_escape(empty))  # noqa: S308
        return format_html_join(", ", "{}", ((_related_link(item, model_admin),) for item in related))
    cell = cell_for_field(value, model_field, empty, obj=obj)
    if cell["kind"] in {"boolean", "badge"}:
        return mark_safe(html(cell))  # noqa: S308
    if cell["kind"] == "json":
        return format_html(
            '<pre class="max-h-80 overflow-auto rounded-field bg-base-200 px-3 py-2 font-mono text-xs">{}</pre>',
            cell["text"],
        )
    if cell["kind"] == "file" and cell["url"]:
        return format_html('<a class="link link-primary" href="{}">{}</a>', cell["url"], cell["text"])
    return mark_safe(conditional_escape(display_for_field(value, model_field, empty)))  # noqa: S308


def _related_link(obj: models.Model, model_admin: Any) -> SafeString:
    site = model_admin.admin_site
    opts = obj._meta
    if not site.is_registered(obj.__class__):
        return format_html("{}", obj)
    try:
        url = reverse(f"{site.name}:{opts.app_label}_{opts.model_name}_change", args=(quote(obj.pk),))
    except NoReverseMatch:
        return format_html("{}", obj)
    return format_html('<a class="link link-primary" href="{}">{}</a>', url, obj)


def field_name(name: Any) -> str:
    """The form field name of a ``fields`` or ``readonly_fields`` entry, which can be a function."""
    return name if isinstance(name, str) else name.__name__


def _label_and_help(name: Any, model_admin: Any, model: type[models.Model]) -> tuple[str, str]:
    label = label_for_field(name, model, model_admin, return_attr=False, form=None)
    try:
        help_text = help_text_for_field(name, model) if isinstance(name, str) else ""
    except AttributeError:
        help_text = ""
    return str(capfirst(label)), str(help_text)


def readonly_field(name: Any, obj: models.Model | None, model_admin: Any, model: type[models.Model]) -> ReadonlyField:
    label, help_text = _label_and_help(name, model_admin, model)
    return ReadonlyField(field_name(name), label, readonly_contents(name, obj, model_admin), help_text)


def display_field(name: Any, model_admin: Any, model: type[models.Model], *, saved_only: bool = False) -> DisplayField:
    """A ``readonly_fields`` entry as a form field, showing what ``readonly_contents()`` shows.

    With ``saved_only``, an unsaved instance shows the empty value, as the blank rows of an inline do.
    """
    label, help_text = _label_and_help(name, model_admin, model)

    def contents(obj: models.Model) -> SafeString:
        return readonly_contents(name, None if saved_only and obj.pk is None else obj, model_admin)

    return DisplayField(label=label, help_text=help_text, source=contents)


class _ListBoundField(_DisplayBoundField):
    """A ``list_display`` column of one row: its value is the ``Cell``, its display value the cell's markup."""

    @property
    def display_value(self) -> SafeString:
        return list_html(self.value())


def list_display_field(entry: Any, model_admin: Any, model: type[models.Model]) -> DisplayField:
    """A ``list_display`` entry as a form field, its value the cell the list shows."""
    label, help_text = _label_and_help(entry, model_admin, model)
    field = DisplayField(label=label, help_text=help_text, source=lambda obj: list_cell(entry, obj, model_admin))
    field.bound_field_class = _ListBoundField
    return field


def _contents(value: Any, empty: str) -> SafeString:
    """A value as the change form shows it read-only: an icon for a boolean, ``empty`` for none."""
    cell = cell_for_value(value, empty)
    return mark_safe(cell["text"] if cell["kind"] == "html" else html(cell))  # noqa: S308


def _shown(bound_field: BoundField, model_admin: Any) -> ReadonlyField:
    """A ``DisplayField`` as the change form shows a read-only value."""
    contents = _contents(bound_field.value(), model_admin.get_empty_value_display())
    return ReadonlyField(bound_field.name, str(bound_field.label), contents, str(bound_field.help_text))


class _AdminDisplayBoundField(_DisplayBoundField):
    """A ``DisplayField`` whose table cell shows its value as the change form does."""

    @property
    def display_value(self) -> SafeString:
        return _contents(self.value(), self.field.empty_value_display)  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]


def show_display_fields(form_class: type[ModelForm[Any]], model_admin: Any) -> None:
    """Show each ``DisplayField`` of an admin-built form class as the change form shows a read-only value.

    Each such field is copied, so the class the project declared keeps its own."""
    for name, form_field in form_class.base_fields.items():
        if isinstance(form_field, DisplayField):
            shown = copy.copy(form_field)
            shown.bound_field_class = _AdminDisplayBoundField
            shown.empty_value_display = model_admin.get_empty_value_display()  # type: ignore[attr-defined]  # ty: ignore[missing-attribute]
            form_class.base_fields[name] = shown


def _rows(
    fields: Sequence[Any],
    form: ModelForm[Any],
    readonly: Sequence[Any],
    obj: models.Model | None,
    model_admin: Any,
) -> list[list[AdminField]]:
    rows = []
    for line in fields:
        names = line if isinstance(line, list | tuple) else (line,)
        row = []
        for name in names:
            if isinstance(form.fields.get(field_name(name)), DisplayField):
                row.append(AdminField(readonly=_shown(form[field_name(name)], model_admin)))
            elif name in readonly or name not in form.fields:
                row.append(AdminField(readonly=readonly_field(name, obj, model_admin, form._meta.model)))
            else:
                row.append(AdminField(field=form[name]))
        rows.append(row)
    return rows


class AdminForm:
    """The main form split into its fieldsets."""

    def __init__(
        self,
        form: ModelForm[Any],
        fieldsets: Sequence[tuple[str | StrPromise | None, dict[str, Any]]],
        prepopulated_fields: dict[str, Sequence[str]],
        readonly_fields: Sequence[Any] = (),
        model_admin: Any = None,
    ) -> None:
        _show_errors_inline(form)
        self.form = form
        self.fieldsets_spec = fieldsets
        self.prepopulated_fields = [
            {"field": name, "dependencies": list(dependencies)}
            for name, dependencies in prepopulated_fields.items()
            if name in form.fields
        ]
        self.readonly_fields = readonly_fields
        self.model_admin = model_admin

    @cached_property
    def fieldsets(self) -> list[Fieldset]:
        obj = getattr(self.form, "instance", None)
        if obj is not None and self.model_admin is not None:
            annotate_rows([obj], display_annotations(self.readonly_fields, self.model_admin))
        return [
            Fieldset(
                name=name,
                rows=_rows(options.get("fields", ()), self.form, self.readonly_fields, obj, self.model_admin),
                description=str(options.get("description", "") or ""),
                classes=tuple(options.get("classes", ())),
            )
            for name, options in self.fieldsets_spec
        ]

    def __iter__(self) -> Iterator[Fieldset]:
        return iter(self.fieldsets)

    @property
    def errors(self) -> Any:
        return self.form.errors

    @property
    def non_field_errors(self) -> Any:
        return self.form.non_field_errors()

    @property
    def hidden_fields(self) -> list[BoundField]:
        shown = set(flatten_fieldsets(cast("_FieldsetSpec", self.fieldsets_spec)))
        return [bf for bf in self.form.hidden_fields() if bf.name not in shown or bf.is_hidden]

    @property
    def media(self) -> Media:
        return self.form.media


@dataclass
class InlineAdminForm:
    """One row of an inline: its form, the saved object and where that object's own page is."""

    form: BaseForm
    fieldsets: list[Fieldset]
    original: models.Model | None
    change_url: str = ""
    view_on_site_url: str = ""
    hidden: list[BoundField] = field(default_factory=list)

    @property
    def deletion_field(self) -> BoundField | None:
        return self.form[DELETION_FIELD_NAME] if DELETION_FIELD_NAME in self.form.fields else None

    @property
    def cells(self) -> list[AdminField]:
        return [cell for fieldset in self.fieldsets for row in fieldset.rows for cell in row if not cell.is_hidden]

    @property
    def has_errors(self) -> bool:
        return bool(self.form.errors)


@dataclass
class InlinePager:
    """The page of an inline's rows that a change form shows, and links to the other pages.

    ``param`` names the page in the change form's URL. ``max_num`` is the inline's own limit; the
    formset holds the share of it that is left for this page.
    """

    paginator: Paginator[Any]
    page: Page[Any]
    param: str
    request: HttpRequest
    max_num: int

    @property
    def count(self) -> int:
        return self.paginator.count

    @property
    def page_num(self) -> int:
        return self.page.number

    @cached_property
    def page_links(self) -> list[PageLink]:
        """The pager's links around the current page."""
        return page_links(self.paginator, self.page.number)

    def page_url(self, number: int) -> str:
        """The change form at another page of these rows, the other inlines at the pages they show."""
        query = self.request.GET.copy()
        query.pop(self.param, None)
        if number > 1:
            query[self.param] = str(number)
        return f"{self.request.path}?{query.urlencode()}" if query else self.request.path

    @property
    def requested(self) -> bool:
        """True when the URL names a page of these rows, so their group starts open."""
        return self.param in self.request.GET


class InlineAdminFormSet:
    """An inline's formset, its rows split into fieldsets and its empty row for adding."""

    def __init__(
        self,
        inline: Any,
        formset: Any,
        fieldsets: Sequence[tuple[str | StrPromise | None, dict[str, Any]]],
        readonly_fields: Sequence[Any] = (),
        *,
        prepopulated_fields: dict[str, Sequence[str]] | None = None,
        has_add_permission: bool = True,
        has_change_permission: bool = True,
        has_delete_permission: bool = True,
        has_view_permission: bool = True,
        pager: InlinePager | None = None,
    ) -> None:
        self.opts = inline
        self.formset = formset
        self.pager = pager
        self.fieldsets_spec = fieldsets
        self.readonly_fields = readonly_fields
        self.prepopulated_fields = [
            {"field": name, "dependencies": list(dependencies)}
            for name, dependencies in (prepopulated_fields or {}).items()
            if name in formset.form.base_fields
        ]
        self.has_add_permission = has_add_permission
        self.has_change_permission = has_change_permission
        self.has_delete_permission = has_delete_permission
        self.has_view_permission = has_view_permission

    def _admin_form(self, form: ModelForm[Any], original: models.Model | None) -> InlineAdminForm:
        _show_errors_inline(form)
        readonly = self.readonly_fields
        if original is not None and not self.has_change_permission:
            # The form shows the values of a row the user cannot change as DisplayFields, and these its hidden ones.
            locked = [name for name in form.fields if name not in {DELETION_FIELD_NAME, form._meta.model._meta.pk.name}]
            readonly = [*readonly, *locked]
        fieldsets = [
            Fieldset(
                name=name,
                rows=_rows(options.get("fields", ()), form, readonly, original, self.opts),
                description=str(options.get("description", "") or ""),
                classes=tuple(options.get("classes", ())),
            )
            for name, options in self.fieldsets_spec
        ]
        shown = {cell.name for fieldset in fieldsets for row in fieldset.rows for cell in row}
        hidden = [
            bf
            for bf in form
            if bf.is_hidden
            or (bf.name not in shown and bf.name != DELETION_FIELD_NAME and not isinstance(bf.field, DisplayField))
        ]
        return InlineAdminForm(form, fieldsets, original, change_url=self._change_url(form), hidden=hidden)

    def _change_url(self, form: BaseForm) -> str:
        """The page of the row's saved object, where the inline links it."""
        original = getattr(form, "instance", None)
        if original is None or original.pk is None or not self.opts.show_change_link:
            return ""
        if not self.opts.admin_site.is_registered(original.__class__):
            return ""
        opts = original._meta
        return reverse(
            f"{self.opts.admin_site.name}:{opts.app_label}_{opts.model_name}_change", args=(quote(original.pk),)
        )

    @cached_property
    def forms(self) -> list[InlineAdminForm]:
        originals = [form.instance for form in self.formset.initial_forms]
        annotate_rows(originals, display_annotations(self.readonly_fields, self.opts))
        return [
            self._admin_form(form, form.instance if form.instance.pk is not None else None)
            for form in self.formset.initial_forms + self.formset.extra_forms
        ]

    def __iter__(self) -> Iterator[InlineAdminForm]:
        return iter(self.forms)

    @cached_property
    def empty_form(self) -> InlineAdminForm:
        return self._admin_form(self.formset.empty_form, None)

    @property
    def prefix(self) -> str:
        return self.formset.prefix

    @property
    def verbose_name(self) -> str:
        return str(self.opts.verbose_name)

    @property
    def verbose_name_plural(self) -> str:
        return str(self.opts.verbose_name_plural)

    @property
    def group_name(self) -> str:
        """The name of the whole inline: singular when it holds one row at most, as in Django."""
        max_num = self.pager.max_num if self.pager else self.formset.max_num
        return self.verbose_name if max_num == 1 else self.verbose_name_plural

    @property
    def count(self) -> int:
        """The saved rows of the inline, on every page."""
        return self.pager.count if self.pager else self.formset.initial_form_count()

    @property
    def can_add(self) -> bool:
        return self.has_add_permission and self.formset.max_num > len(self.formset.forms)

    def table(self, footer: str = "") -> SafeString:
        """The tabular layout: formwork's formset table, flush in the inline's card.

        ``footer`` goes at the right end of the Add another row: the pager, for a paged inline.
        """
        self.forms  # noqa: B018 (the rows take their error display and their read-only values)
        formset = self.formset
        formset.row_url = self._change_url
        context = formset.get_table_context(flush=True)
        context.update(
            footer=footer,
            empty_text=_("No %(name)s yet.") % {"name": self.group_name},
            add_text=_("Add another %(name)s") % {"name": self.verbose_name},
        )
        return formset.render_table(context)

    @property
    def non_form_errors(self) -> Any:
        return self.formset.non_form_errors()

    @property
    def media(self) -> Media:
        return self.opts.media + self.formset.media

    @property
    def is_tabular(self) -> bool:
        return getattr(self.opts, "layout", "stacked") == "tabular"

    @property
    def collapsible(self) -> bool:
        """``collapse`` in the inline's ``classes`` folds it behind its title, as it folds a fieldset."""
        return "collapse" in (getattr(self.opts, "classes", None) or ())

    def error_count(self) -> int:
        return sum(1 for form in self.formset.forms if form.errors) + bool(self.formset.non_form_errors())


class DeletedObject:
    """A line of the delete pages in Django's words, "Item: Kettle", with the object as a link where it has one.

    The pages group the lines of a ``model`` under its name and there show the ``link`` alone. Both build when
    a page shows them, so a page names only the objects it lists out of thousands.
    """

    def __init__(self, obj: models.Model, link: Callable[[], SafeString]) -> None:
        self.model = type(obj)
        self._link = link

    @cached_property
    def link(self) -> SafeString:
        return self._link()

    def __html__(self) -> SafeString:
        return format_html("{}: {}", capfirst(self.model._meta.verbose_name), self.link)

    __str__ = __html__


@dataclass
class DeletedGroup:
    """The objects of one model at one level of a delete page: the first few, each with its own groups."""

    name: str
    count: int = 0
    objects: list[tuple[SafeString, SafeString, list[DeletedGroup]]] = field(default_factory=list)

    @property
    def more(self) -> int:
        return self.count - len(self.objects)


def deleted_groups(items: Sequence[Any], limit: int | None) -> list[DeletedGroup]:
    """Django's nested list of the objects a deletion takes with it, as groups per model at each level.

    A group lists its first ``FIRST_OBJECTS``, and the page at most ``limit`` objects over all levels, as
    ``delete_confirmation_max_display`` counts them. A line without a model, which an overridden
    ``get_deleted_objects()`` can return, makes a group of its own.
    """
    shown = 0

    def group(level: Sequence[Any]) -> list[DeletedGroup]:
        nonlocal shown
        # Django's list puts an object's own list right after it.
        pairs: list[tuple[Any, Sequence[Any]]] = []
        for item in level:
            if isinstance(item, list):
                pairs[-1] = (pairs[-1][0], item)
            else:
                pairs.append((item, []))
        groups: dict[object, DeletedGroup] = {}
        for line, children in pairs:
            model = getattr(line, "model", None)
            key = model or object()
            if key not in groups:
                groups[key] = DeletedGroup(capfirst(model._meta.verbose_name_plural) if model else "")
            found = groups[key]
            found.count += 1
            if len(found.objects) < FIRST_OBJECTS and (limit is None or shown < limit):
                shown += 1
                found.objects.append((line, getattr(line, "link", line), group(children)))
        return list(groups.values())

    return group(items)
