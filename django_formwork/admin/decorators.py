"""``@register``, ``@display`` and ``@action``, as ``django.contrib.admin`` spells them."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db import models
    from django_stubs_ext import StrPromise

    from django_formwork.admin.options import ModelAdmin
    from django_formwork.admin.sites import AdminSite

__all__ = ["action", "display", "register"]


def register(
    *models: type[models.Model], site: AdminSite | None = None
) -> Callable[[type[ModelAdmin]], type[ModelAdmin]]:
    """Register the decorated ``ModelAdmin`` for ``models`` on ``site``, the default site unless given."""
    from django_formwork.admin.options import ModelAdmin
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
    icon: str | None = None,
    danger: bool = False,
) -> Any:
    """``django.contrib.admin.action``, plus the ``icon`` and ``danger`` the action bar draws."""

    def decorator(func: F) -> F:
        if permissions is not None:
            func.allowed_permissions = permissions  # type: ignore[attr-defined]
        if description is not None:
            func.short_description = description  # type: ignore[attr-defined]
        if icon is not None:
            func.icon = icon  # type: ignore[attr-defined]
        if danger:
            func.danger = True  # type: ignore[attr-defined]
        return func

    return decorator if function is None else decorator(function)
