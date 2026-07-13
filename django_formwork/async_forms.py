"""Async-validation mixins for FormworkForm and FormworkModelForm.

Adds ``ais_valid()``, ``afull_clean()``, and ``asave()`` so async
``clean_<field>()`` and ``clean()`` methods can use the async ORM without
``sync_to_async`` wrappers.  Use ``FormworkForm`` or ``FormworkModelForm``
directly; they compose these mixins automatically.
"""

from __future__ import annotations

import inspect
from itertools import chain
from typing import TYPE_CHECKING, Any, NoReturn

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from django.db import models

__all__ = [
    "AsyncFormMixin",
    "AsyncModelFormMixin",
]


def _force_async_enabled() -> bool:
    from django.conf import settings

    return getattr(settings, "FORMWORK_FORCE_ASYNC", False)


def _check_force_async(sync_name: str, async_name: str) -> None:
    if _force_async_enabled():
        msg = f"FORMWORK_FORCE_ASYNC is enabled. Use {async_name}() instead of {sync_name}()."
        raise RuntimeError(msg)


class AsyncFormMixin:
    """Adds async validation to FormworkForm.

    Detects whether ``clean_<field>()`` and ``clean()`` are sync or async
    via ``inspect.iscoroutinefunction()`` and calls them accordingly.
    """

    def full_clean(self: Any) -> None:
        _check_force_async("full_clean", "afull_clean")
        super().full_clean()  # type: ignore[misc]

    def is_valid(self: Any) -> bool:
        _check_force_async("is_valid", "ais_valid")
        return super().is_valid()  # type: ignore[misc]

    async def ais_valid(self: Any) -> bool:
        """Async version of ``is_valid()``."""
        if not self.is_bound:
            return False
        if self._errors is None:
            await self.afull_clean()
        return not self._errors

    async def afull_clean(self: Any) -> None:
        """Async version of ``full_clean()``."""
        from django.forms.utils import ErrorDict

        self._errors = ErrorDict(renderer=self.renderer)
        if not self.is_bound:
            return
        self.cleaned_data: dict[str, Any] = {}
        if self.empty_permitted and not self.has_changed():
            return

        await self._aclean_fields()
        await self._aclean_form()
        await self._apost_clean()

    async def _aclean_fields(self: Any) -> None:
        """Async version of ``_clean_fields()``."""
        for name, bf in self._bound_items():
            field = bf.field
            try:
                self.cleaned_data[name] = field._clean_bound_field(bf)  # noqa: SLF001
                method = getattr(self, f"clean_{name}", None)
                if method is not None:
                    if inspect.iscoroutinefunction(method):
                        value = await method()
                    else:
                        value = method()
                    self.cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e)

    async def _aclean_form(self: Any) -> None:
        """Async version of ``_clean_form()``."""
        try:
            if inspect.iscoroutinefunction(self.clean):
                cleaned_data = await self.clean()
            else:
                cleaned_data = self.clean()
        except ValidationError as e:
            self.add_error(None, e)
        else:
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data

    async def _apost_clean(self: Any) -> None:
        """Hook for subclasses. No-op on base forms."""


class AsyncModelFormMixin(AsyncFormMixin):
    """Extends :class:`AsyncFormMixin` with async model operations.

    Adds ``asave()``, async unique/constraint validation, and async
    M2M saving.
    """

    def save(self: Any, commit: bool = True) -> Any:  # noqa: FBT001, FBT002, ANN401
        _check_force_async("save", "asave")
        return super().save(commit=commit)  # type: ignore[misc]

    # NOTE: the async ``_post_clean`` (model construction + validation) lives on
    # ``_DirtyOnlyModelFormMixin._apost_clean`` in django_formwork.forms, which
    # precedes this mixin in the MRO of both model form base classes.

    async def avalidate_unique(self: Any) -> None:
        """Async version of ``validate_unique()``."""
        exclude = self._get_validation_exclusions()
        try:
            await sync_to_async(self.instance.validate_unique)(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)

    async def avalidate_constraints(self: Any) -> None:
        """Async version of ``validate_constraints()``."""
        exclude = self._get_validation_exclusions()
        try:
            await sync_to_async(self.instance.validate_constraints)(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)

    async def asave(self: Any, commit: bool = True) -> models.Model:  # noqa: FBT001, FBT002
        """Async version of ``ModelForm.save()``."""
        if self._errors is None:
            await self.afull_clean()
        if self._errors:
            raise ValueError(
                "The {} could not be {} because the data didn't validate.".format(
                    self.instance._meta.object_name,  # noqa: SLF001
                    "created" if self.instance._state.adding else "changed",  # noqa: SLF001
                ),
            )
        if commit:
            await self.instance.asave()
            await self._asave_m2m()
        else:
            self.asave_m2m = self._asave_m2m
            self.save_m2m = self._reject_sync_save_m2m
        return self.instance

    asave.alters_data = True  # type: ignore[attr-defined]

    def _reject_sync_save_m2m(self: Any) -> NoReturn:
        """Raise on the sync ``save_m2m`` hook after ``asave(commit=False)``."""
        msg = "This form was saved with asave(commit=False). Await form.asave_m2m() instead of calling save_m2m()."
        raise RuntimeError(msg)

    async def _asave_m2m(self: Any) -> None:
        """Async version of ``_save_m2m()``."""
        cleaned_data = self.cleaned_data
        exclude = self._meta.exclude
        fields = self._meta.fields
        opts = self.instance._meta  # noqa: SLF001
        for f in chain(opts.many_to_many, opts.private_fields):
            if not hasattr(f, "save_form_data"):
                continue
            if fields and f.name not in fields:
                continue
            if exclude and f.name in exclude:
                continue
            if f.name in cleaned_data:
                await sync_to_async(f.save_form_data)(
                    self.instance,
                    cleaned_data[f.name],
                )
