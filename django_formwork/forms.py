"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` use
:class:`~django_formwork.renderers.FormworkRenderer` so that both
``{{ form }}`` and ``{{ field.as_field_group }}`` produce DaisyUI-styled
markup.  All component styling is handled by the formwork CSS file via
``@apply``.  No widget attributes are mutated in Python.

Using ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in settings
is preferred over these base classes (it applies to *all* forms), but
these are useful when you want formwork styling on specific forms only.

Both classes register the server search of each field whose widget takes a
``search_queryset`` when the class is created, so a single
``include("django_formwork.urls")`` serves every search.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Self, TypeVar

from asgiref.sync import sync_to_async
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Model, UniqueConstraint
from django.forms import Form, ModelForm
from django.forms.forms import DeclarativeFieldsMetaclass
from django.forms.models import InlineForeignKeyField, ModelFormMetaclass, construct_instance

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.boundfield import FormworkBoundField
from django_formwork.renderers import FormworkRenderer
from django_formwork.search import register_form_searches
from django_formwork.tables import RowRenderMixin

__all__ = [
    "FormworkForm",
    "FormworkFormMetaclass",
    "FormworkModelForm",
    "FormworkModelFormMetaclass",
]

_M = TypeVar("_M", bound=Model)

_ERROR_DISPLAY_CHOICES = ("auto", "inline", "tooltip")


class FormworkFormMetaclass(DeclarativeFieldsMetaclass):
    """Registers each field's server search at class creation."""

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type:
        cls = super().__new__(mcs, name, bases, attrs, **kwargs)
        register_form_searches(cls)
        return cls


class FormworkModelFormMetaclass(ModelFormMetaclass):
    """Registers each field's server search at class creation."""

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type:
        cls = super().__new__(mcs, name, bases, attrs, **kwargs)
        register_form_searches(cls)
        return cls


class _ErrorDisplayFormMixin:
    """Form-level choice of how field errors render: ``auto``, ``inline`` or ``tooltip``.

    ``auto`` resolves per field in ``formwork/forms/field.html``: inline when
    the field has help text, a tooltip when it does not.
    """

    def __init__(self, *args: Any, error_display: str | None = None, **kwargs: Any) -> None:
        if error_display is None:
            meta = getattr(type(self), "Meta", None)
            error_display = getattr(meta, "error_display", "auto")
        if error_display not in _ERROR_DISPLAY_CHOICES:
            msg = f"error_display must be one of {_ERROR_DISPLAY_CHOICES}, got {error_display!r}"
            raise ImproperlyConfigured(msg)
        self.error_display: str = error_display
        super().__init__(*args, **kwargs)


class _MandatoryFormMixin:
    """Fields a later step such as publish needs, though a save takes them empty.

    ``Meta.mandatory`` seeds ``self.mandatory`` before ``Form.__init__``, so a
    subclass adds data-dependent names after its own ``super().__init__()``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        meta = getattr(type(self), "Meta", None)
        self.mandatory: set[str] = set(getattr(meta, "mandatory", ()))
        super().__init__(*args, **kwargs)


class _DirtyOnlyFormMixin:
    """Skip field-level validation for fields the user didn't change.

    When ``validate_dirty_only`` is on (via ``Meta.validate_dirty_only = True``
    or the ``__init__`` kwarg), ``_clean_fields`` / ``_aclean_fields`` skip
    fields where ``BoundField._has_changed()`` returns False (the per-field
    machinery behind ``Form.changed_data``) and carry the bound field's
    ``initial`` value through to ``cleaned_data``.  ``clean_<name>`` methods
    are skipped for those fields too.

    One consequence to know about: for an unchanged field, ``cleaned_data``
    holds ``BoundField.initial`` rather than the field's cleaned Python value.
    For a relational field on a model form that difference shows: ``initial``
    is the raw pk (from ``model_to_dict``), whereas a normal clean would put
    the related instance there.  This does not affect saving.  The model-form
    mixin excludes unchanged fields from ``construct_instance`` (see
    ``_dirty_construct_exclude``), so the stored relation is left untouched
    and the pk never reaches the FK descriptor.  It only matters if your own
    code reads ``cleaned_data[<relation>]`` for a field the user left alone;
    expect a pk there, not an instance.
    """

    if TYPE_CHECKING:
        _bound_items: Any
        cleaned_data: dict[str, Any]
        add_error: Any

    def __init__(self, *args: Any, validate_dirty_only: bool | None = None, **kwargs: Any) -> None:
        if validate_dirty_only is None:
            meta = getattr(type(self), "Meta", None)
            validate_dirty_only = bool(getattr(meta, "validate_dirty_only", False))
        self._validate_dirty_only: bool = validate_dirty_only
        super().__init__(*args, **kwargs)

    def _clean_fields(self) -> None:
        if not self._validate_dirty_only:
            super()._clean_fields()  # type: ignore[misc]
            return
        for name, bf in self._bound_items():
            field = bf.field
            if not bf._has_changed():  # noqa: SLF001
                self.cleaned_data[name] = bf.initial
                continue
            try:
                self.cleaned_data[name] = field._clean_bound_field(bf)  # noqa: SLF001
                method = getattr(self, f"clean_{name}", None)
                if method is not None:
                    self.cleaned_data[name] = method()
            except ValidationError as e:
                self.add_error(name, e)

    async def _aclean_fields(self) -> None:
        if not self._validate_dirty_only:
            await super()._aclean_fields()  # type: ignore[misc]
            return
        for name, bf in self._bound_items():
            field = bf.field
            if not bf._has_changed():  # noqa: SLF001
                self.cleaned_data[name] = bf.initial
                continue
            try:
                # A field's clean() may hit the ORM (e.g. ModelChoiceField
                # resolving a FK), so run it off the event loop.
                self.cleaned_data[name] = await sync_to_async(field._clean_bound_field)(bf)  # noqa: SLF001
                method = getattr(self, f"clean_{name}", None)
                if method is not None:
                    if inspect.iscoroutinefunction(method):
                        value = await method()
                    else:
                        value = method()
                    self.cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e)


class _DirtyOnlyModelFormMixin(_DirtyOnlyFormMixin):
    """Extend dirty-only to ``_post_clean`` / ``_apost_clean``.

    Requires the bound instance to provide ``get_dirty_fields()`` when
    ``validate_dirty_only`` is on (via :class:`~django_formwork.FormworkModel`
    or any direct mix of ``filthyfields.DirtyFieldsMixin``).
    """

    if TYPE_CHECKING:
        instance: Any
        fields: Any
        _meta: Any
        _validate_unique: bool
        _validate_constraints: bool
        _uniqueness_deferred: bool
        _update_errors: Any
        validate_unique: Any
        validate_constraints: Any
        avalidate_unique: Any
        avalidate_constraints: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self._validate_dirty_only and not hasattr(self.instance, "get_dirty_fields"):
            msg = (
                f"{type(self).__name__} has validate_dirty_only=True but "
                f"{type(self.instance).__name__} does not provide get_dirty_fields(). "
                f"Inherit from django_formwork.FormworkModel (or mix in "
                f"filthyfields.DirtyFieldsMixin) on the model."
            )
            raise ImproperlyConfigured(msg)

    def _get_validation_exclusions(self) -> set[str]:
        """Django's exclusions plus every unchanged field.

        Unchanged members of a compound uniqueness check that a dirty field
        participates in are kept validatable: Django drops such a check
        entirely when any member is excluded, and the collision would then
        surface as a database IntegrityError instead of a form error.
        """
        exclude: set[str] = super()._get_validation_exclusions()  # type: ignore[misc]
        if not self._validate_dirty_only or self.instance._state.adding:  # noqa: SLF001
            return exclude
        dirty = set(self.instance.get_dirty_fields(check_relationship=True))
        keep = self._compound_check_members(dirty)
        for f in self.instance._meta.fields:  # noqa: SLF001
            if not f.primary_key and f.name not in dirty and f.name not in keep:
                exclude.add(f.name)
        return exclude

    def _compound_check_members(self, dirty: set[str]) -> set[str]:
        """Fields sharing a multi-field uniqueness check with a dirty field."""
        opts = self.instance._meta  # noqa: SLF001
        groups: list[tuple[str, ...]] = [tuple(group) for group in opts.unique_together]
        groups += [
            tuple(constraint.fields)
            for constraint in opts.constraints
            if isinstance(constraint, UniqueConstraint) and len(constraint.fields) > 1
        ]
        for f in opts.fields:
            for date_kind in ("unique_for_date", "unique_for_month", "unique_for_year"):
                paired = getattr(f, date_kind, None)
                if paired:
                    groups.append((f.name, paired))
        members: set[str] = set()
        for group in groups:
            if len(group) > 1 and dirty.intersection(group):
                members.update(group)
        return members

    def _dirty_construct_exclude(self) -> set[str]:
        """Fields ``construct_instance()`` should leave at their stored value.

        Under ``validate_dirty_only`` on an existing instance, unchanged fields
        keep what the DB loaded.  This stops an unchanged relation from being
        re-assigned out of its raw pk, which the FK descriptor rejects.
        """
        exclude: set[str] = set(self._meta.exclude or ())
        if self._validate_dirty_only and not self.instance._state.adding:  # noqa: SLF001
            for name, bf in self._bound_items():
                if not bf._has_changed():  # noqa: SLF001
                    exclude.add(name)
        return exclude

    def _post_clean(self) -> None:
        # Reordered copy of Django's ModelForm._post_clean(): construct_instance()
        # runs BEFORE _get_validation_exclusions() so the latter can consult
        # instance.get_dirty_fields() on the post-form state.
        opts = self._meta
        try:
            self.instance = construct_instance(self, self.instance, opts.fields, self._dirty_construct_exclude())  # type: ignore[arg-type]
        except ValidationError as e:
            self._update_errors(e)

        exclude = self._get_validation_exclusions()
        for name, field in self.fields.items():
            if isinstance(field, InlineForeignKeyField):
                exclude.add(name)

        try:
            self.instance.full_clean(exclude=exclude, validate_unique=False, validate_constraints=False)
        except ValidationError as e:
            self._update_errors(e)

        # A FormworkBaseModelFormSet runs every child's against-the-database
        # uniqueness and constraint checks once, in a batched pass on the formset
        # (see django_formwork.formsets). When so instructed, skip both here and
        # record that we deferred so the formset knows to cover this form.
        if getattr(self, "_defer_unique_to_formset", False):
            self._uniqueness_deferred = True
        else:
            if self._validate_unique:
                self.validate_unique()
            if self._validate_constraints:
                self.validate_constraints()

    async def _apost_clean(self) -> None:
        # Same reorder as _post_clean(), async variant.
        opts = self._meta
        try:
            self.instance = construct_instance(self, self.instance, opts.fields, self._dirty_construct_exclude())  # type: ignore[arg-type]
        except ValidationError as e:
            self._update_errors(e)

        exclude = self._get_validation_exclusions()
        for name, field in self.fields.items():
            if isinstance(field, InlineForeignKeyField):
                exclude.add(name)

        try:
            await sync_to_async(self.instance.full_clean)(
                exclude=exclude,
                validate_unique=False,
                validate_constraints=False,
            )
        except ValidationError as e:
            self._update_errors(e)

        # See _post_clean(): the formset batches the uniqueness and constraint
        # checks; skip both here and record that we deferred when instructed.
        if getattr(self, "_defer_unique_to_formset", False):
            self._uniqueness_deferred = True
        else:
            if self._validate_unique:
                await self.avalidate_unique()
            if self._validate_constraints:
                await self.avalidate_constraints()


if TYPE_CHECKING:
    from django.forms import ModelForm as _GenericModelForm
else:

    class _GenericModelForm:
        """``ModelForm[_M]`` for the type checker, plain ``ModelForm`` at runtime."""

        def __class_getitem__(cls, item: object) -> type[ModelForm]:
            return ModelForm


class FormworkForm(
    RowRenderMixin,
    _MandatoryFormMixin,
    _ErrorDisplayFormMixin,
    _DirtyOnlyFormMixin,
    AsyncFormMixin,
    Form,
    metaclass=FormworkFormMetaclass,
):
    """Form base class with DaisyUI styling and async support.

    Usage::

        class ContactForm(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            message = forms.CharField(widget=forms.Textarea)

    Async clean methods are supported::

        class ContactForm(FormworkForm):
            async def clean_email(self):
                if await is_email_blocked(self.cleaned_data["email"]):
                    raise ValidationError("Blocked")
                return self.cleaned_data["email"]

        # In async view:
        if await form.ais_valid():
            ...

    Pass ``validate_dirty_only=True`` (or set ``Meta.validate_dirty_only = True``)
    to skip field validators on fields the user did not change.

    ``Meta.error_display`` (or the ``error_display`` kwarg) picks where field
    errors render: ``"auto"`` (default) puts them inline when the field has
    help text and in a DaisyUI tooltip when it does not; ``"inline"`` and
    ``"tooltip"`` force one placement.

    Optional fields carry an "optional" badge.  ``Meta.mandatory`` names
    fields that a save accepts empty but a later step needs: they get no badge
    and announce ``aria-required``.
    """

    default_renderer = FormworkRenderer
    bound_field_class = FormworkBoundField


class FormworkModelForm(
    RowRenderMixin,
    _MandatoryFormMixin,
    _ErrorDisplayFormMixin,
    _DirtyOnlyModelFormMixin,
    AsyncModelFormMixin,
    _GenericModelForm[_M],
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling and async support.

    Subscript it with the model for typed ``instance`` and ``save()``:
    ``class BookForm(FormworkModelForm[Book])``.

    With ``Meta.validate_dirty_only = True`` (or the matching ``__init__``
    kwarg), field validation, model field validation, unique checks and
    constraint checks are all skipped for fields the user did not change.
    Exception: an unchanged field that shares a multi-field uniqueness check
    (``unique_together``, multi-field ``UniqueConstraint``, ``unique_for_*``)
    with a changed field stays validated, so the compound check still runs.
    Requires the bound model to inherit :class:`~django_formwork.FormworkModel`.

    ``Meta.error_display`` and ``Meta.mandatory`` work as on
    :class:`FormworkForm`.
    """

    default_renderer = FormworkRenderer
    bound_field_class = FormworkBoundField

    if TYPE_CHECKING:
        # The mixins above declare these as Any, which hides ModelForm[_M]'s types.
        instance: _M

        def save(self, commit: bool = True) -> _M: ...  # noqa: FBT001, FBT002

    def __class_getitem__(cls, item: object) -> type[Self]:
        return cls
