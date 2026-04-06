"""Async form mixins for Django forms.

Adds ``ais_valid()``, ``afull_clean()``, and ``asave()`` to Django forms,
allowing async ``clean_<field>()`` and ``clean()`` methods that can use
the async ORM without ``sync_to_async`` wrappers.

Usage with plain Django forms::

    class MyForm(AsyncFormMixin, forms.Form):
        async def clean_email(self):
            if await User.objects.filter(email=self.cleaned_data["email"]).aexists():
                raise ValidationError("Email taken")
            return self.cleaned_data["email"]

    # In an async view:
    form = MyForm(request.POST)
    if await form.ais_valid():
        ...

``FormworkForm`` and ``FormworkModelForm`` include these mixins
automatically.
"""

from __future__ import annotations

import inspect
from itertools import chain
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance

if TYPE_CHECKING:
    from django.db import models


def _force_async_enabled() -> bool:
    from django.conf import settings

    return getattr(settings, "FORMWORK_FORCE_ASYNC", False)


def _check_force_async(sync_name: str, async_name: str) -> None:
    if _force_async_enabled():
        msg = f"FORMWORK_FORCE_ASYNC is enabled. Use {async_name}() instead of {sync_name}()."
        raise RuntimeError(msg)


class AsyncFormMixin:
    """Mixin that adds async validation to Django forms.

    Detects whether ``clean_<field>()`` and ``clean()`` are sync or async
    via ``inspect.iscoroutinefunction()`` and calls them accordingly.
    """

    def full_clean(self) -> None:
        _check_force_async("full_clean", "afull_clean")
        super().full_clean()  # type: ignore[misc]

    def is_valid(self) -> bool:
        _check_force_async("is_valid", "ais_valid")
        return super().is_valid()  # type: ignore[misc]

    async def ais_valid(self) -> bool:
        """Async version of ``is_valid()``."""
        if not self.is_bound:  # type: ignore[attr-defined]
            return False
        await self.afull_clean()
        return not self.errors  # type: ignore[attr-defined]

    async def afull_clean(self) -> None:
        """Async version of ``full_clean()``."""
        from django.forms.utils import ErrorDict

        self._errors = ErrorDict(renderer=self.renderer)  # type: ignore[attr-defined]
        if not self.is_bound:  # type: ignore[attr-defined]
            return
        self.cleaned_data = {}  # type: ignore[attr-defined]
        if self.empty_permitted and not self.has_changed():  # type: ignore[attr-defined]
            return

        await self._aclean_fields()
        await self._aclean_form()
        await self._apost_clean()

    async def _aclean_fields(self) -> None:
        """Async version of ``_clean_fields()``."""
        for name, bf in self._bound_items():  # type: ignore[attr-defined]
            field = bf.field
            try:
                self.cleaned_data[name] = field._clean_bound_field(bf)  # type: ignore[attr-defined]  # noqa: SLF001
                method = getattr(self, f"clean_{name}", None)
                if method is not None:
                    if inspect.iscoroutinefunction(method):
                        value = await method()
                    else:
                        value = method()
                    self.cleaned_data[name] = value  # type: ignore[attr-defined]
            except ValidationError as e:
                self.add_error(name, e)  # type: ignore[attr-defined]

    async def _aclean_form(self) -> None:
        """Async version of ``_clean_form()``."""
        try:
            if inspect.iscoroutinefunction(self.clean):  # type: ignore[attr-defined]
                cleaned_data = await self.clean()  # type: ignore[attr-defined]
            else:
                cleaned_data = self.clean()  # type: ignore[attr-defined]
        except ValidationError as e:
            self.add_error(None, e)  # type: ignore[attr-defined]
        else:
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data  # type: ignore[attr-defined]

    async def _apost_clean(self) -> None:
        """Hook for subclasses. No-op on base forms."""


class AsyncModelFormMixin(AsyncFormMixin):
    """Extends :class:`AsyncFormMixin` with async model operations.

    Adds ``asave()``, async ``_post_clean`` (model validation), and
    async M2M saving.
    """

    def save(self, commit: bool = True) -> Any:  # noqa: FBT001, FBT002, ANN401
        _check_force_async("save", "asave")
        return super().save(commit=commit)  # type: ignore[misc]

    async def _apost_clean(self) -> None:
        """Async version of ``ModelForm._post_clean()``."""
        opts = self._meta  # type: ignore[attr-defined]
        exclude = self._get_validation_exclusions()  # type: ignore[attr-defined]

        from django.forms.models import InlineForeignKeyField

        for name, field in self.fields.items():  # type: ignore[attr-defined]
            if isinstance(field, InlineForeignKeyField):
                exclude.add(name)

        try:
            self.instance = construct_instance(  # type: ignore[attr-defined]
                self,
                self.instance,
                opts.fields,
                opts.exclude,  # type: ignore[attr-defined]
            )
        except ValidationError as e:
            self._update_errors(e)  # type: ignore[attr-defined]

        try:
            await sync_to_async(self.instance.full_clean)(  # type: ignore[attr-defined]
                exclude=exclude,
                validate_unique=False,
                validate_constraints=False,
            )
        except ValidationError as e:
            self._update_errors(e)  # type: ignore[attr-defined]

        if self._validate_unique:  # type: ignore[attr-defined]
            await self.avalidate_unique()
        if self._validate_constraints:  # type: ignore[attr-defined]
            await self.avalidate_constraints()

    async def avalidate_unique(self) -> None:
        """Async version of ``validate_unique()``."""
        exclude = self._get_validation_exclusions()  # type: ignore[attr-defined]
        try:
            await sync_to_async(self.instance.validate_unique)(exclude=exclude)  # type: ignore[attr-defined]
        except ValidationError as e:
            self._update_errors(e)  # type: ignore[attr-defined]

    async def avalidate_constraints(self) -> None:
        """Async version of ``validate_constraints()``."""
        exclude = self._get_validation_exclusions()  # type: ignore[attr-defined]
        try:
            await sync_to_async(self.instance.validate_constraints)(exclude=exclude)  # type: ignore[attr-defined]
        except ValidationError as e:
            self._update_errors(e)  # type: ignore[attr-defined]

    async def asave(self, commit: bool = True) -> models.Model:  # noqa: FBT001, FBT002
        """Async version of ``ModelForm.save()``."""
        if self.errors:  # type: ignore[attr-defined]
            raise ValueError(
                "The {} could not be {} because the data didn't validate.".format(
                    self.instance._meta.object_name,  # type: ignore[attr-defined]  # noqa: SLF001
                    "created" if self.instance._state.adding else "changed",  # type: ignore[attr-defined]  # noqa: SLF001
                ),
            )
        if commit:
            await self.instance.asave()  # type: ignore[attr-defined]
            await self._asave_m2m()
        else:
            self.save_m2m = self._asave_m2m  # type: ignore[attr-defined]
        return self.instance  # type: ignore[attr-defined]

    asave.alters_data = True  # type: ignore[attr-defined]

    async def _asave_m2m(self) -> None:
        """Async version of ``_save_m2m()``."""
        cleaned_data = self.cleaned_data  # type: ignore[attr-defined]
        exclude = self._meta.exclude  # type: ignore[attr-defined]
        fields = self._meta.fields  # type: ignore[attr-defined]
        opts = self.instance._meta  # type: ignore[attr-defined]  # noqa: SLF001
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
                    cleaned_data[f.name],  # type: ignore[attr-defined]
                )
