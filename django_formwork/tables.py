"""Render a form as a table row (``as_row``) and a formset as an editable table (``as_rows``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import Media
from django.forms.formsets import DELETION_FIELD_NAME
from django.http import Http404, HttpResponse
from django.utils.choices import flatten_choices
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _

from django_formwork.fields import DisplayField
from django_formwork.renderers import formwork_renderer
from django_formwork.widgets._stub import formset_row, stub_formset, with_query
from django_formwork.widgets.select import share_choices

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from django.db.models import QuerySet
    from django.forms import BoundField
    from django.http import HttpRequest

    #: What a cell shows for a field that posts nothing.
    CellDisplay = Callable[[BoundField], Any]

__all__ = [
    "FormworkCellMixin",
    "FormworkRowSaveMixin",
    "RowRenderMixin",
    "Table",
    "TableCell",
    "TableRenderMixin",
    "TableRow",
]

#: Hidden input carrying the form prefix so the save endpoint can rebind the
#: same field namespace the row was rendered with.
PREFIX_INPUT_NAME = "_formwork_prefix"

ROW_TEMPLATE = "formwork/tables/row.html"
TABLE_TEMPLATE = "formwork/tables/table.html"


def _value_text(bound_field: BoundField) -> Any:  # noqa: ANN401
    """A field's value as a cell shows it: a ``DisplayField``'s value, or a disabled field's value as text."""
    form = bound_field.form
    instance = getattr(form, "instance", None)
    display_getter = getattr(instance, f"get_{bound_field.name}_display", None) if instance is not None else None
    if isinstance(bound_field.field, DisplayField):
        display = bound_field.value()
        if isinstance(display, list | tuple):
            display = format_html_join(", ", "{}", ((item,) for item in display))
    elif callable(display_getter):
        display = display_getter()
    elif instance is not None:
        value = getattr(instance, bound_field.name, None)
        related = getattr(value, "all", None)  # related manager (M2M / reverse FK)
        if related is not None:
            display = ", ".join(str(obj) for obj in related())
        else:
            display = value if value is None else str(value)
    else:
        choices: Iterator[tuple[Any, Any]] = flatten_choices(getattr(bound_field.field, "choices", ()))
        labels = {str(key): label for key, label in choices}
        value = bound_field.value()
        values = value if isinstance(value, (list, tuple)) else [value]
        display = ", ".join(str(labels.get(str(v), v)) for v in values if v is not None)
    return "" if display is None else display


@dataclass
class TableCell:
    """One cell of a row: a field's widget, or ``display`` content for a value the row does not post."""

    name: str
    field: BoundField | None = None
    display: Any = ""

    @property
    def boxed(self) -> bool:
        """Whether the widget draws a box, which sets the value in from the cell's edge."""
        if self.field is None:
            return False
        return getattr(self.field.field.widget, "input_type", None) not in {"checkbox", "radio"}

    @staticmethod
    def shows_value(bound_field: BoundField) -> bool:
        """The field posts nothing, a ``DisplayField`` or a disabled field, so its cell shows its value."""
        return isinstance(bound_field.field, DisplayField) or bound_field.field.disabled

    @classmethod
    def for_field(cls, bound_field: BoundField, display: CellDisplay | None = None) -> TableCell:
        """A widget cell, or for a field that posts nothing its value, as ``display`` shows it."""
        if not cls.shows_value(bound_field):
            return cls(bound_field.name, field=bound_field)
        return cls(bound_field.name, display=(display or _value_text)(bound_field))

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
    def for_form(  # noqa: PLR0913
        cls,
        form: Any,  # noqa: ANN401
        *,
        new: bool = False,
        can_delete: bool = False,
        save_url: str = "",
        actions: bool = False,
        fields: Sequence[str] | None = None,
        display: CellDisplay | None = None,
        link: str = "",
    ) -> TableRow:
        """The row of ``form``, a cell for each of ``fields`` that shows, by default each visible field."""
        hidden_inputs = getattr(form, "row_hidden_inputs", None) if save_url else None
        if hidden_inputs is None:
            hidden_inputs = mark_safe("".join(str(bound_field) for bound_field in form.hidden_fields()))  # noqa: S308
        deletion_field = None
        if can_delete and not new and DELETION_FIELD_NAME in form.fields:
            deletion_field = form[DELETION_FIELD_NAME]
        return cls(
            form=form,
            cells=[TableCell.for_field(bound_field, display) for bound_field in _columns(form, fields)],
            hidden=hidden_inputs,
            new=new,
            deletion_field=deletion_field,
            link=link,
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

    def render(self) -> SafeString:
        renderer = formwork_renderer(self.form.renderer)
        return mark_safe(self.form.render(self.template_name, {"form": self.form, "row": self}, renderer))  # noqa: S308


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
    #: Markup at the right end of the Add another row, such as a pager. The row shows while it has any.
    footer: Any = ""
    template_name: str = TABLE_TEMPLATE

    @classmethod
    def for_formset(  # noqa: PLR0913
        cls,
        formset: Any,  # noqa: ANN401
        *,
        save_url: str = "",
        flush: bool = False,
        cell_url: str = "",
        fields: Sequence[str] | None = None,
        display: CellDisplay | None = None,
        link: Callable[[Any], str] | None = None,
    ) -> Table:
        """The table of a Django formset, with rows to add unless it saves row by row.

        With ``cell_url``, the selects and date pickers of the saved rows render as stubs that load from it.
        ``fields`` names the columns, ``display`` shows a field that posts nothing, ``link`` gives a row's own page.
        """
        # The rows load the choices of a relation once, whether they render in full or as stubs.
        share_choices(formset)
        if cell_url:
            stub_formset(formset, lambda name: with_query(cell_url, field=name))
        can_add = not save_url and getattr(formset, "can_add", True) and not getattr(formset, "edit_only", False)
        can_delete = not save_url and formset.can_delete
        initial = formset.initial_form_count()
        links = [link(form) if link is not None else "" for form in formset.forms]
        new_rows = len(formset.forms) > initial
        actions = not save_url and (can_add or can_delete or new_rows or any(links))
        rows = [
            TableRow.for_form(
                form,
                new=index >= initial,
                can_delete=can_delete,
                save_url=save_url,
                actions=actions,
                fields=fields,
                display=display,
                link=links[index],
            )
            for index, form in enumerate(formset.forms)
        ]
        empty_row = None
        if can_add:
            empty_row = TableRow.for_form(formset.empty_form, new=True, actions=actions, fields=fields, display=display)
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
                    # A boxed widget sets its value in from the cell's edge, and the header lines up with the value.
                    "indent": not TableCell.shows_value(bound_field)
                    and TableCell(bound_field.name, field=bound_field).boxed,
                }
                for bound_field in _columns(formset.empty_form, fields)
            ],
            rows=rows,
            empty_row=empty_row,
            save_url=save_url,
            flush=flush,
            verbose_name=opts.verbose_name if opts is not None else _("row"),
            verbose_name_plural=opts.verbose_name_plural if opts is not None else _("rows"),
            template_name=getattr(formset, "template_name_table", TABLE_TEMPLATE),
        )

    @property
    def actions(self) -> bool:
        return any(row.actions for row in self.rows) or (self.empty_row is not None and self.empty_row.actions)

    # The texts with a name are built here, not in the template: makemessages finds no Jinja trans block.
    @property
    def empty_text(self) -> str:
        return _("No %(name)s yet.") % {"name": self.verbose_name_plural}

    @property
    def add_text(self) -> str:
        return _("Add another %(name)s") % {"name": self.verbose_name}

    def render(self) -> SafeString:
        renderer = formwork_renderer(self.formset.renderer)
        return mark_safe(self.formset.render(self.template_name, {"table": self, "formset": self.formset}, renderer))  # noqa: S308


def _columns(form: Any, fields: Sequence[str] | None) -> list[BoundField]:  # noqa: ANN401
    """The fields of ``form`` that take a column: each of ``fields`` the form has, shown and not the Delete toggle."""
    names = form.fields if fields is None else [name for name in fields if name in form.fields]
    return [form[name] for name in names if name != DELETION_FIELD_NAME and not form[name].is_hidden]


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
        return TableRow.for_form(self, save_url=save_url).render()

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

    def as_rows(self, save_url: str = "", *, flush: bool = False, cell_url: str = "") -> SafeString:
        return Table.for_formset(self, save_url=save_url, flush=flush, cell_url=cell_url).render()

    @property
    def media(self) -> Media:
        from django_formwork.widgets._base import _ModuleScript

        return super().media + Media(js=[_ModuleScript("formwork/tables.js")])  # type: ignore[misc]  # ty: ignore[unresolved-attribute]


class _RowsViewMixin:
    """The rows a view can reach: ``queryset`` or ``get_queryset()``."""

    queryset: QuerySet[Any] | None = None

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:  # noqa: ARG002
        """The rows this endpoint can change, e.g. ``Task.objects.filter(owner=request.user)``."""
        if self.queryset is None:
            msg = (
                f"{type(self).__name__} needs a queryset (or get_queryset()) of the rows a user can "
                "change, e.g. Task.objects.filter(owner=request.user), or Task.objects.all() for every row."
            )
            raise ImproperlyConfigured(msg)
        return self.queryset.all()


class FormworkRowSaveMixin(_RowsViewMixin):
    """View mixin: save one row's changes (keyed on the posted pk) and re-render it.

    ``queryset`` (or ``get_queryset()``) holds the rows a post can change; a pk
    outside it gets a 404.
    """

    form_class: type[Any]

    def get_save_url(self, request: HttpRequest) -> str:
        """URL the re-rendered row keeps posting to (the save endpoint itself)."""
        return request.path

    def get_prefix(self, request: HttpRequest) -> str | None:
        return request.POST.get(PREFIX_INPUT_NAME) or None

    def get_object(self, request: HttpRequest, prefix: str | None) -> Any:  # noqa: ANN401
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
        prefix = self.get_prefix(request)
        instance = self.get_object(request, prefix)
        form = self.get_form(request, instance, prefix)
        if form.is_valid():
            form.save()
            # The saved row starts over from what it saved, without the marks of changed fields.
            form = self.form_class(instance=instance, prefix=prefix, **self.get_form_kwargs())
        return HttpResponse(self.render_row(request, form))


class FormworkCellMixin(_RowsViewMixin):
    """View mixin: answer a stub of ``as_rows(cell_url=...)`` with its field's full widget.

    ``queryset`` (or ``get_queryset()``) holds the rows a user can change; a pk outside it gets a 404.
    """

    formset_class: type[Any]

    def get_formset_kwargs(self, request: HttpRequest) -> dict[str, Any]:  # noqa: ARG002
        """Extra kwargs for ``formset_class``, as the page passes them, such as ``form_kwargs``."""
        return {}

    def get(self, request: HttpRequest, *_args: Any, **_kwargs: Any) -> HttpResponse:
        queryset = self.get_queryset(request)
        try:
            pk = queryset.model._meta.pk.to_python(request.GET.get("pk"))  # noqa: SLF001
        except ValidationError as exc:
            raise Http404("Row primary key is malformed") from exc
        name = request.GET.get("field", "")
        # Built by the formset, so that a hook of the formset gives the row its choices.
        form = formset_row(
            self.formset_class,
            request.GET.get("prefix", ""),
            name,
            request.GET,
            **{**self.get_formset_kwargs(request), "queryset": queryset.filter(pk=pk)},
        )
        if form is None:
            raise Http404("Row no longer exists")
        if name not in form.fields or form.fields[name].disabled:
            raise Http404("No such field")
        return HttpResponse(TableCell(name, field=form[name]).widget)
