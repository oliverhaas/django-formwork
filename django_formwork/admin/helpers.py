"""The change form as templates read it: fieldsets of rows, read-only values and inline formsets."""

from __future__ import annotations

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

from django_formwork.admin.cells import cell_for_field, cell_for_value, html

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from django.contrib.admin.options import _FieldsetSpec
    from django.forms import BaseForm, BoundField, Media, ModelForm
    from django_stubs_ext import StrPromise

__all__ = ["AdminField", "AdminForm", "Fieldset", "InlineAdminForm", "InlineAdminFormSet", "ReadonlyField"]


def _show_errors_inline(form: BaseForm) -> None:
    """Show each field error under its field, unless the form's ``Meta.error_display`` sets a display."""
    if getattr(getattr(type(form), "Meta", None), "error_display", None) is None:
        form.error_display = "inline"  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]


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


def readonly_field(name: Any, obj: models.Model | None, model_admin: Any, model: type[models.Model]) -> ReadonlyField:
    label = label_for_field(name, model, model_admin, return_attr=False, form=None)
    try:
        help_text = help_text_for_field(name, model) if isinstance(name, str) else ""
    except AttributeError:
        help_text = ""
    key = name if isinstance(name, str) else name.__name__
    return ReadonlyField(key, str(capfirst(label)), readonly_contents(name, obj, model_admin), str(help_text))


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
            if name in readonly or name not in form.fields:
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


class InlineAdminFormSet:
    """An inline's formset, its rows split into fieldsets and its empty row for adding."""

    def __init__(
        self,
        inline: Any,
        formset: Any,
        fieldsets: Sequence[tuple[str | StrPromise | None, dict[str, Any]]],
        readonly_fields: Sequence[Any] = (),
        *,
        has_add_permission: bool = True,
        has_change_permission: bool = True,
        has_delete_permission: bool = True,
        has_view_permission: bool = True,
    ) -> None:
        self.opts = inline
        self.formset = formset
        self.fieldsets_spec = fieldsets
        self.readonly_fields = readonly_fields
        self.has_add_permission = has_add_permission
        self.has_change_permission = has_change_permission
        self.has_delete_permission = has_delete_permission
        self.has_view_permission = has_view_permission

    def _admin_form(self, form: ModelForm[Any], original: models.Model | None) -> InlineAdminForm:
        _show_errors_inline(form)
        readonly = self.readonly_fields
        if original is not None and not self.has_change_permission:
            readonly = [
                *readonly,
                *(name for name in form.fields if name not in {DELETION_FIELD_NAME, form._meta.model._meta.pk.name}),
            ]
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
        hidden = [bf for bf in form if bf.is_hidden or (bf.name not in shown and bf.name != DELETION_FIELD_NAME)]
        change_url = ""
        if (
            original is not None
            and self.opts.show_change_link
            and self.opts.admin_site.is_registered(original.__class__)
        ):
            opts = original._meta
            change_url = reverse(
                f"{self.opts.admin_site.name}:{opts.app_label}_{opts.model_name}_change",
                args=(quote(original.pk),),
            )
        return InlineAdminForm(form, fieldsets, original, change_url=change_url, hidden=hidden)

    @cached_property
    def forms(self) -> list[InlineAdminForm]:
        return [
            self._admin_form(form, form.instance if form.instance.pk is not None else None)
            for form in self.formset.initial_forms + self.formset.extra_forms
        ]

    def __iter__(self) -> Iterator[InlineAdminForm]:
        return iter(self.forms)

    @cached_property
    def empty_form(self) -> InlineAdminForm:
        return self._admin_form(self.formset.empty_form, None)

    @cached_property
    def headers(self) -> list[dict[str, Any]]:
        """The tabular inline's column headers, read from the empty row."""
        headers = []
        for cell in self.empty_form.cells:
            if cell.field is not None:
                headers.append(
                    {
                        "label": cell.field.label,
                        "required": cell.field.field.required,
                        "help_text": cell.field.help_text,
                    }
                )
            elif cell.readonly is not None:
                headers.append({"label": cell.readonly.label, "required": False, "help_text": cell.readonly.help_text})
        return headers

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
        return self.verbose_name if self.formset.max_num == 1 else self.verbose_name_plural

    @property
    def can_add(self) -> bool:
        return self.has_add_permission and self.formset.max_num > len(self.formset.forms)

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
