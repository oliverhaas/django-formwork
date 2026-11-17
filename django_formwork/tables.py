"""Render a form as a table row (``as_row``) and a formset as an editable table (``as_rows``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ImproperlyConfigured
from django.forms import Media
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.choices import flatten_choices
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.models import QuerySet
    from django.forms import BoundField
    from django.http import HttpRequest, HttpResponse

__all__ = ["FormworkRowSaveMixin", "RowRenderMixin", "Table", "TableCell", "TableRenderMixin", "TableRow"]

#: Hidden input carrying the form prefix so the save endpoint can rebind the
#: same field namespace the row was rendered with.
PREFIX_INPUT_NAME = "_formwork_prefix"

ROW_TEMPLATE = "formwork/tables/row.html"
TABLE_TEMPLATE = "formwork/tables/table.html"


@dataclass
class TableCell:
    """One cell of a row: a field's widget, or ``display`` content for a value the row does not post."""

    name: str
    field: BoundField | None = None
    display: Any = ""

    @classmethod
    def for_field(cls, bound_field: BoundField) -> TableCell:
        """A widget cell, or for a disabled field its value as text."""
        if not bound_field.field.disabled:
            return cls(bound_field.name, field=bound_field)
        form = bound_field.form
        instance = getattr(form, "instance", None)
        display_getter = getattr(instance, f"get_{bound_field.name}_display", None) if instance is not None else None
        if callable(display_getter):
            display = display_getter()
        elif instance is not None:
            value = getattr(instance, bound_field.name, None)
            if value is None:
                display = ""
            elif hasattr(value, "all"):  # related manager (M2M / reverse FK)
                display = ", ".join(str(obj) for obj in value.all())
            else:
                display = str(value)
        else:
            choices: Iterator[tuple[Any, Any]] = flatten_choices(getattr(bound_field.field, "choices", ()))
            labels = {str(key): label for key, label in choices}
            value = bound_field.value()
            values = value if isinstance(value, (list, tuple)) else [value]
            display = ", ".join(str(labels.get(str(v), v)) for v in values if v is not None)
        return cls(bound_field.name, display=display)

    @cached_property
    def widget(self) -> SafeString:
        """The widget, named by the field's label: the cell has no ``<label>`` of its own."""
        bound_field = self.field
        if bound_field is None:
            return SafeString("")
        return bound_field.as_widget(attrs={"aria-label": str(bound_field.label)})

    @cached_property
    def links(self) -> str:
        """The widget's label links, which a cell puts after the widget."""
        return getattr(self.field, "label_links", "") if self.field is not None else ""

    @property
    def changed(self) -> bool:
        """The posted value differs from the initial one, so a failed save keeps the cell marked."""
        if self.field is None:
            return False
        form = self.field.form
        return form.is_bound and self.name in form.changed_data


@dataclass
class TableRow:
    """One form as a ``<tbody>``: its cells, its hidden inputs and its actions."""

    form: Any
    cells: list[TableCell]
    hidden: SafeString = field(default_factory=lambda: SafeString(""))
    #: Not saved yet: the row has Remove instead of Delete.
    new: bool = False
    #: The formset's DELETE field, shown as the Delete toggle.
    deletion_field: BoundField | None = None
    #: The row's own page, shown as an Open link.
    link: str = ""
    #: Each change posts the row to this URL.
    save_url: str = ""
    #: The row ends with a column for Open, Delete and Remove.
    actions: bool = False
    template_name: str = ROW_TEMPLATE

    @classmethod
    def for_form(
        cls,
        form: Any,  # noqa: ANN401
        *,
        new: bool = False,
        can_delete: bool = False,
        save_url: str = "",
        actions: bool = False,
    ) -> TableRow:
        hidden_inputs = getattr(form, "row_hidden_inputs", None) if save_url else None
        if hidden_inputs is None:
            hidden_inputs = mark_safe("".join(str(bound_field) for bound_field in form.hidden_fields()))  # noqa: S308
        deletion_field = None
        if can_delete and not new and DELETION_FIELD_NAME in form.fields:
            deletion_field = form[DELETION_FIELD_NAME]
        return cls(
            form=form,
            cells=[TableCell.for_field(bf) for bf in form.visible_fields() if bf.name != DELETION_FIELD_NAME],
            hidden=hidden_inputs,
            new=new,
            deletion_field=deletion_field,
            save_url=save_url,
            actions=actions,
            template_name=getattr(form, "template_name_row", ROW_TEMPLATE),
        )

    @property
    def id(self) -> str:
        return f"formwork-row-{self.form.prefix or 'form'}"

    @property
    def columns(self) -> int:
        return len(self.cells) + self.actions

    @property
    def non_field_errors(self) -> Any:  # noqa: ANN401
        return self.form.non_field_errors()


@dataclass
class Table:
    """A formset as one ``<table>``: a header, a row per form, and a template row for adding."""

    formset: Any
    headers: list[dict[str, Any]]
    rows: list[TableRow]
    #: The row that Add another copies; ``None`` hides Add another.
    empty_row: TableRow | None = None
    save_url: str = ""
    #: The table runs to the edges of a card, and its outer columns take the card's padding.
    flush: bool = False
    verbose_name: Any = ""
    verbose_name_plural: Any = ""
    template_name: str = TABLE_TEMPLATE

    @classmethod
    def for_formset(cls, formset: Any, *, save_url: str = "", flush: bool = False) -> Table:  # noqa: ANN401
        """The table of a Django formset, with rows to add unless it saves row by row."""
        can_add = not save_url and getattr(formset, "can_add", True) and not getattr(formset, "edit_only", False)
        can_delete = not save_url and formset.can_delete
        initial = formset.initial_form_count()
        new_rows = len(formset.forms) > initial
        actions = not save_url and (can_add or can_delete or new_rows)
        rows = [
            TableRow.for_form(form, new=index >= initial, can_delete=can_delete, save_url=save_url, actions=actions)
            for index, form in enumerate(formset.forms)
        ]
        model = getattr(formset, "model", None)
        opts = model._meta if model is not None else None  # noqa: SLF001
        return cls(
            formset=formset,
            headers=[
                {
                    "name": bound_field.name,
                    "label": bound_field.label,
                    "required": getattr(bound_field, "is_mandatory", bound_field.field.required)
                    and not bound_field.field.disabled,
                    "help_text": bound_field.help_text,
                }
                for bound_field in formset.empty_form.visible_fields()
                if bound_field.name != DELETION_FIELD_NAME
            ],
            rows=rows,
            empty_row=TableRow.for_form(formset.empty_form, new=True, actions=actions) if can_add else None,
            save_url=save_url,
            flush=flush,
            verbose_name=opts.verbose_name if opts is not None else _("row"),
            verbose_name_plural=opts.verbose_name_plural if opts is not None else _("rows"),
            template_name=getattr(formset, "template_name_table", TABLE_TEMPLATE),
        )

    @property
    def actions(self) -> bool:
        return any(row.actions for row in self.rows) or (self.empty_row is not None and self.empty_row.actions)

    def render(self) -> SafeString:
        return mark_safe(self.formset.render(self.template_name, {"table": self, "formset": self.formset}))  # noqa: S308


class RowRenderMixin:
    """Add ``as_row()`` to a form: render it as one table ``<tbody>``."""

    template_name_row = ROW_TEMPLATE

    if TYPE_CHECKING:
        prefix: str | None
        instance: Any
        add_prefix: Any
        render: Any
        hidden_fields: Any

    def as_row(self, save_url: str = "") -> SafeString:
        row = TableRow.for_form(self, save_url=save_url)
        return mark_safe(self.render(self.template_name_row, {"form": self, "row": row}))  # noqa: S308

    @property
    def row_hidden_inputs(self) -> SafeString:
        """Prefix + hidden inputs for hand-authored autosave rows.

        Emits the pk explicitly, not via the formset's ``id`` field, so a row re-rendered from a
        standalone form (as the save view does) still round-trips its pk.
        """
        parts: list[str] = [
            format_html('<input type="hidden" name="{}" value="{}">', PREFIX_INPUT_NAME, self.prefix or ""),
        ]
        instance = getattr(self, "instance", None)
        pk_name = None
        if instance is not None:
            pk_name = instance._meta.pk.name  # noqa: SLF001
            pk = "" if instance.pk is None else instance.pk
            parts.append(format_html('<input type="hidden" name="{}" value="{}">', self.add_prefix(pk_name), pk))
        parts.extend(str(bf) for bf in self.hidden_fields() if bf.name != pk_name)
        return mark_safe("".join(parts))  # noqa: S308 (parts are escaped / widget-safe)

    @property
    def row_id(self) -> str:
        return f"formwork-row-{self.prefix or 'form'}"


class TableRenderMixin:
    """Add ``as_rows()`` to a formset: render it as one editable ``<table>``."""

    template_name_table = TABLE_TEMPLATE
    #: Add another appends a row. A model formset with ``edit_only=True`` has none either way.
    can_add = True

    def as_rows(self, save_url: str = "", *, flush: bool = False) -> SafeString:
        return Table.for_formset(self, save_url=save_url, flush=flush).render()

    @property
    def media(self) -> Media:
        from django_formwork.widgets._base import _ModuleScript

        return super().media + Media(js=[_ModuleScript("formwork/tables.js")])  # type: ignore[misc]  # ty: ignore[unresolved-attribute]


class FormworkRowSaveMixin:
    """View mixin: save one row's changes (keyed on the posted pk) and re-render it.

    ``queryset`` (or ``get_queryset()``) holds the rows a post can change; a pk
    outside it gets a 404.
    """

    form_class: type[Any]
    queryset: QuerySet[Any] | None = None

    def get_save_url(self, request: HttpRequest) -> str:
        """URL the re-rendered row keeps posting to (the save endpoint itself)."""
        return request.path

    def get_prefix(self, request: HttpRequest) -> str | None:
        return request.POST.get(PREFIX_INPUT_NAME) or None

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:  # noqa: ARG002
        """The rows this endpoint can change, e.g. ``Task.objects.filter(owner=request.user)``."""
        if self.queryset is None:
            model_name = self.form_class._meta.model.__name__  # noqa: SLF001
            msg = (
                f"{type(self).__name__} needs a queryset (or get_queryset()) of the rows a user can "
                f"change, e.g. {model_name}.objects.filter(owner=request.user), or "
                f"{model_name}.objects.all() for every row."
            )
            raise ImproperlyConfigured(msg)
        return self.queryset.all()

    def get_object(self, request: HttpRequest, prefix: str | None) -> Any:  # noqa: ANN401
        from django.core.exceptions import ValidationError
        from django.http import Http404

        queryset = self.get_queryset(request)
        pk_name = queryset.model._meta.pk.name  # noqa: SLF001
        field = f"{prefix}-{pk_name}" if prefix else pk_name
        pk = request.POST.get(field)
        if pk is None:
            raise Http404("Row primary key missing from the request")
        try:
            return queryset.get(pk=pk)
        except queryset.model.DoesNotExist as exc:
            # Row deleted between render and autosave, or outside the queryset: a clean 404 beats a 500.
            raise Http404("Row no longer exists") from exc
        except (ValueError, ValidationError) as exc:
            # A malformed pk (wrong type for the key field) is a bad request,
            # not a server error; 404 it like a missing row.
            raise Http404("Row primary key is malformed") from exc

    def get_form_kwargs(self) -> dict[str, Any]:
        """Extra kwargs for the row form's constructor."""
        return {}

    def get_form(self, request: HttpRequest, instance: Any, prefix: str | None) -> Any:  # noqa: ANN401
        return self.form_class(request.POST, request.FILES, instance=instance, prefix=prefix, **self.get_form_kwargs())

    def render_row(self, request: HttpRequest, form: Any) -> str:  # noqa: ANN401
        """HTML for the re-rendered row. Override to render a hand-authored row partial."""
        return form.as_row(self.get_save_url(request))

    def post(self, request: HttpRequest, *_args: Any, **_kwargs: Any) -> HttpResponse:
        from django.http import HttpResponse

        prefix = self.get_prefix(request)
        instance = self.get_object(request, prefix)
        form = self.get_form(request, instance, prefix)
        if form.is_valid():
            form.save()
            # The saved row starts over from what it saved, without the marks of changed fields.
            form = self.form_class(instance=instance, prefix=prefix, **self.get_form_kwargs())
        return HttpResponse(self.render_row(request, form))
