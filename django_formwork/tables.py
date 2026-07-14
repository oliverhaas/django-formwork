"""Render a form as a table row (``as_row``) and a formset as an editable table (``as_rows``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import HttpRequest, HttpResponse

__all__ = ["FormworkRowSaveMixin", "RowRenderMixin", "TableRenderMixin"]

#: Hidden input carrying the form prefix so the save endpoint can rebind the
#: same field namespace the row was rendered with.
PREFIX_INPUT_NAME = "_formwork_prefix"


class RowRenderMixin:
    """Add ``as_row()`` to a form: render it as one table ``<tbody>``."""

    template_name_row = "django_formwork/tables/row.html"

    #: Set per render (by :meth:`TableRenderMixin.as_rows` or the caller) so
    #: the row's htmx wiring knows where to post. Empty renders a static row.
    save_url: str = ""

    if TYPE_CHECKING:
        prefix: str | None
        instance: Any
        add_prefix: Any
        render: Any
        get_context: Any
        visible_fields: Any
        hidden_fields: Any

    def as_row(self, save_url: str | None = None) -> str:
        return self.render(self.template_name_row, self.get_row_context(save_url))

    @property
    def row_hidden(self) -> str:
        """Prefix + hidden inputs for hand-authored autosave rows.

        Emits the pk explicitly, not via the formset's ``id`` field, so a row re-rendered from a
        standalone form (as the save view does) still round-trips its pk.
        """
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe

        parts: list[str] = [format_html('<input type="hidden" name="{}" value="{}">', PREFIX_INPUT_NAME, self.prefix or "")]
        instance = getattr(self, "instance", None)
        pk_name = None
        if instance is not None:
            pk_name = instance._meta.pk.name  # noqa: SLF001
            pk = "" if instance.pk is None else instance.pk
            parts.append(format_html('<input type="hidden" name="{}" value="{}">', self.add_prefix(pk_name), pk))
        parts.extend(str(bf) for bf in self.hidden_fields() if bf.name != pk_name)
        return mark_safe("".join(parts))  # noqa: S308 (parts are escaped / widget-safe)

    def get_row_context(self, save_url: str | None = None) -> dict[str, Any]:
        context = self.get_context()
        context["save_url"] = self.save_url if save_url is None else save_url
        context["row_id"] = self.row_id
        context["cells"] = list(self.row_cells())
        return context

    @property
    def row_id(self) -> str:
        return f"formwork-row-{self.prefix or 'form'}"

    def row_cells(self) -> Iterator[dict[str, Any]]:
        """One entry per visible field: editable (widget) or read-only display text."""
        instance = getattr(self, "instance", None)
        for bf in self.visible_fields():
            if not bf.field.disabled:
                yield {"bound_field": bf, "editable": True, "display": None}
                continue
            display_getter = getattr(instance, f"get_{bf.name}_display", None) if instance is not None else None
            if callable(display_getter):
                display = display_getter()
            elif instance is not None:
                value = getattr(instance, bf.name, None)
                if value is None:
                    display = ""
                elif hasattr(value, "all"):  # related manager (M2M / reverse FK)
                    display = ", ".join(str(obj) for obj in value.all())
                else:
                    display = str(value)
            else:
                value = bf.value()
                choices = dict(getattr(bf.field, "choices", []) or [])
                display = choices.get(value, value) if choices else ("" if value is None else str(value))
            yield {"bound_field": bf, "editable": False, "display": display}


class TableRenderMixin:
    """Add ``as_rows()`` to a formset: render it as one editable ``<table>``."""

    template_name_table = "django_formwork/tables/table.html"

    if TYPE_CHECKING:
        forms: Any
        empty_form: Any
        render: Any
        get_context: Any

    def as_rows(self, save_url: str = "") -> str:
        for form in self.forms:
            form.save_url = save_url
        context = self.get_context()
        context["save_url"] = save_url
        context["header_fields"] = list(self.empty_form.visible_fields())
        return self.render(self.template_name_table, context)


class FormworkRowSaveMixin:
    """View mixin: save one row's changes (keyed on the posted pk) and re-render it."""

    form_class: type[Any]

    def get_save_url(self, request: HttpRequest) -> str:
        """URL the re-rendered row keeps posting to (the save endpoint itself)."""
        return request.path

    def get_prefix(self, request: HttpRequest) -> str | None:
        return request.POST.get(PREFIX_INPUT_NAME) or None

    def get_object(self, request: HttpRequest, prefix: str | None) -> Any:  # noqa: ANN401
        model = self.form_class._meta.model  # noqa: SLF001
        pk_name = model._meta.pk.name  # noqa: SLF001
        field = f"{prefix}-{pk_name}" if prefix else pk_name
        return model._default_manager.get(pk=request.POST[field])  # noqa: SLF001

    def get_form_kwargs(self) -> dict[str, Any]:
        """Extra kwargs for the row form (e.g. ``editable_fields`` to guard read-only columns)."""
        return {}

    def get_form(self, request: HttpRequest, instance: Any, prefix: str | None) -> Any:  # noqa: ANN401
        return self.form_class(request.POST, instance=instance, prefix=prefix, **self.get_form_kwargs())

    def render_row(self, request: HttpRequest, form: Any) -> str:  # noqa: ANN401
        """HTML for the re-rendered row. Override to render a hand-authored row partial."""
        return form.as_row(self.get_save_url(request))

    def post(self, request: HttpRequest, **_kwargs: Any) -> HttpResponse:
        from django.http import HttpResponse

        prefix = self.get_prefix(request)
        instance = self.get_object(request, prefix)
        form = self.get_form(request, instance, prefix)
        if form.is_valid():
            form.save()
        return HttpResponse(self.render_row(request, form))
