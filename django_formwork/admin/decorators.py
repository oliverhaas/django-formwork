"""``@register``, ``@display`` and ``@action``, as ``django.contrib.admin`` spells them."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from django_formwork.admin.options import ActionLocation, ModelAdmin

if TYPE_CHECKING:
    from django.db import models
    from django_stubs_ext import StrPromise

    from django_formwork.admin.sites import AdminSite

__all__ = ["action", "display", "register"]


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
    ordering: str | None = None,
    description: str | StrPromise | None = None,
    empty_value: str | None = None,
) -> Any:
    """``django.contrib.admin.display``, with the same attributes."""

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
) -> Any:
    """``django.contrib.admin.action`` of Django 6.1, plus the ``icon`` and ``danger`` the page draws.

    ``location`` puts the action in the list, on the change form or both. The list labels it with
    ``description_plural`` when given.
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
        return func

    return decorator if function is None else decorator(function)
