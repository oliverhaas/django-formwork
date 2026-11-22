"""``@register``, ``@display`` and ``@action``, as ``django.contrib.admin`` spells them, and ``@slot``."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from django_formwork.admin.options import ActionLocation, ModelAdmin
from django_formwork.widgets.display import check_max_lines

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django.db.models.expressions import BaseExpression, Combinable
    from django_stubs_ext import StrPromise

    from django_formwork.admin.sites import AdminSite

__all__ = ["action", "display", "register", "slot"]


def register(
    *models: type[models.Model], site: AdminSite | None = None
) -> Callable[[type[ModelAdmin]], type[ModelAdmin]]:
    """Register the decorated ``ModelAdmin`` for ``models`` on ``site``, the default site unless given."""
    from django_formwork.admin.sites import site as default_site

    def wrapper(admin_class: type[ModelAdmin]) -> type[ModelAdmin]:
        if not models:
            msg = "At least one model must be passed to register."
            raise ValueError(msg)
        if not issubclass(admin_class, ModelAdmin):
            msg = "Wrapped class must subclass django_formwork.admin.ModelAdmin."
            raise TypeError(msg)
        (site or default_site).register(models, admin_class=admin_class)
        return admin_class

    return wrapper


def display[F: Callable[..., Any]](
    function: F | None = None,
    *,
    boolean: bool | None = None,
    ordering: str | BaseExpression | Combinable | None = None,
    description: str | StrPromise | None = None,
    empty_value: str | None = None,
    annotate: Mapping[str, BaseExpression | Combinable] | None = None,
    max_lines: int | None = None,
) -> Any:
    """``django.contrib.admin.display``, with the same attributes.

    ``annotate`` names expressions that the admin computes for the rows it shows, as ``QuerySet.annotate()`` does.
    ``max_lines`` cuts the value to that many lines, with a [more] toggle for the rest, in the list and the form.
    """

    def decorator(func: F) -> F:
        if boolean is not None and empty_value is not None:
            msg = f"The boolean and empty_value arguments to the @display decorator are mutually exclusive on {func!r}."
            raise ValueError(msg)
        if boolean is not None:
            func.boolean = boolean  # type: ignore[attr-defined]
        if ordering is not None:
            func.admin_order_field = ordering  # type: ignore[attr-defined]
        if description is not None:
            func.short_description = description  # type: ignore[attr-defined]
        if empty_value is not None:
            func.empty_value_display = empty_value  # type: ignore[attr-defined]
        if annotate is not None:
            func.admin_annotations = dict(annotate)  # type: ignore[attr-defined]
        if max_lines is not None:
            check_max_lines(max_lines)
            func.max_lines = max_lines  # type: ignore[attr-defined]
        return func

    return decorator if function is None else decorator(function)


def action[F: Callable[..., Any]](
    function: F | None = None,
    *,
    permissions: list[str] | tuple[str, ...] | None = None,
    description: str | StrPromise | None = None,
    description_plural: str | StrPromise | None = None,
    location: ActionLocation | Sequence[ActionLocation] = ActionLocation.CHANGE_LIST,
    icon: str | None = None,
    danger: bool = False,
    help_text: str | StrPromise | None = None,
    button: bool = False,
    confirm: bool | str | StrPromise = False,
    form: type[forms.Form] | None = None,
) -> Any:
    """``django.contrib.admin.action`` of Django 6.1, plus what the formwork admin draws and asks.

    The admin reference describes the arguments under Actions.
    """

    def decorator(func: F) -> F:
        if permissions is not None:
            func.allowed_permissions = permissions  # type: ignore[attr-defined]
        if description is not None:
            func.short_description = description  # type: ignore[attr-defined]
        if description_plural is not None:
            func.plural_description = description_plural  # type: ignore[attr-defined]
        elif description is not None:
            func.plural_description = description  # type: ignore[attr-defined]
        func.locations = [location] if isinstance(location, ActionLocation) else list(location)  # type: ignore[attr-defined]
        if icon is not None:
            func.icon = icon  # type: ignore[attr-defined]
        if danger:
            func.danger = True  # type: ignore[attr-defined]
        if help_text is not None:
            func.help_text = help_text  # type: ignore[attr-defined]
        if button:
            func.button = True  # type: ignore[attr-defined]
        if confirm:
            func.confirm = confirm  # type: ignore[attr-defined]
        if form is not None:
            func.form = form  # type: ignore[attr-defined]
        return func

    return decorator if function is None else decorator(function)


def slot[F: Callable[..., Any]](function: F | None = None, *, lazy: bool = False, skeleton: str | None = None) -> Any:
    """Options of a slot method of a ``ModelAdmin``, such as ``list_top``, ``change_bottom`` or ``row_details``.

    A lazy slot loads from a URL of its own, after its page or as its row opens, and shows ``skeleton`` until then.
    """

    def decorator(func: F) -> F:
        if skeleton is not None and not lazy:
            msg = f"The skeleton argument to the @slot decorator needs lazy=True on {func!r}."
            raise ValueError(msg)
        func.slot_lazy = lazy  # type: ignore[attr-defined]
        func.slot_skeleton = skeleton  # type: ignore[attr-defined]
        return func

    return decorator if function is None else decorator(function)
