"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` use
:class:`~django_formwork.renderers.FormworkRenderer` so that both
``{{ form }}`` and ``{{ field.as_field_group }}`` produce DaisyUI-styled
markup.  All component styling is handled by the formwork CSS file via
``@apply`` — no widget attributes are mutated in Python.

Using ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in settings
is preferred over these base classes (it applies to *all* forms), but
these are useful when you want formwork styling on specific forms only.

Search endpoints are automatically registered so that a single
``include("django_formwork.urls")`` serves all search views:

- **Model-backed**: widget has ``search_fields`` and field provides a queryset.
- **Choices-backed**: form defines ``search_choices_<fieldname>(query, request)``.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import Form, ModelChoiceField, ModelForm, ModelMultipleChoiceField
from django.forms.models import InlineForeignKeyField, ModelFormMetaclass, construct_instance

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.fields import FormworkModelChoiceField, FormworkModelMultipleChoiceField
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms import Field

    from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect

__all__ = [
    "FormworkForm",
    "FormworkJinja2Form",
    "FormworkJinja2ModelForm",
    "FormworkModelForm",
    "FormworkModelFormMetaclass",
]


class FormworkModelFormMetaclass(ModelFormMetaclass):
    """Metaclass that auto-upgrades ``ModelChoiceField`` to ``FormworkModelChoiceField``.

    Auto-generated ``ModelChoiceField`` / ``ModelMultipleChoiceField`` instances
    (from ``Meta.model`` / ``Meta.fields``) are swapped for their Formwork
    equivalents so icon/description callbacks can be attached to the field.
    Explicit field declarations — including custom subclasses — are left alone.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if not hasattr(cls, "base_fields"):
            return cls
        for field_name, field in cls.base_fields.items():
            if type(field) is ModelChoiceField:
                cls.base_fields[field_name] = FormworkModelChoiceField.from_field(field)
            elif type(field) is ModelMultipleChoiceField:
                cls.base_fields[field_name] = FormworkModelMultipleChoiceField.from_field(field)
        return cls


class _AutoSearchMixin:
    """Mixin that auto-registers search endpoints.

    Two paths:

    1. **Model-backed** — widget has ``search_fields`` and the field
       provides a queryset (``ModelChoiceField``).
    2. **Choices-backed** — the form defines a
       ``search_choices_<fieldname>(query, request)`` method that returns
       results directly (list of dicts or ``(value, label)`` tuples).
    """

    if TYPE_CHECKING:
        fields: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._auto_register_search()

    def _auto_register_search(self) -> None:
        from django.core.exceptions import ImproperlyConfigured

        from django_formwork._registry import (
            SearchRegistration,
            make_choices_key,
            register,
        )
        from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect
        from django_formwork.widgets._base import _NOT_SET

        for name, field in self.fields.items():
            widget = field.widget
            if not isinstance(widget, (SearchSelect, MultiSelect, ComboBox)):
                continue

            # Check whether this widget would be auto-registered.
            search_fields = getattr(widget, "search_fields", None)
            queryset = getattr(field, "queryset", None)
            has_model_search = bool(search_fields) and queryset is not None
            has_choices_search = getattr(self.__class__, f"search_choices_{name}", None) is not None

            if not has_model_search and not has_choices_search:
                continue

            # Enforce search_decorator — developer must make a conscious
            # choice about auth for auto-registered search endpoints.
            raw_decorator = getattr(widget, "search_decorator", _NOT_SET)
            if raw_decorator is _NOT_SET:
                widget_cls = type(widget).__name__
                msg = (
                    f"Field '{name}' uses {widget_cls} with server-side search but no "
                    f"search_decorator was provided. Pass a decorator (e.g. login_required) "
                    f"or None for public access."
                )
                raise ImproperlyConfigured(msg)
            decorator = raw_decorator  # Validated: not _NOT_SET → Callable | None

            # Path 1: model-backed (search_fields on widget + queryset on field).
            if has_model_search and search_fields is not None and queryset is not None:
                self._register_model_search(name, widget, field, search_fields, queryset)
                continue

            # Path 2: choices-backed (search_choices_<name> method on form).
            method = getattr(self.__class__, f"search_choices_{name}", None)
            if method is not None:
                widget_type = self._widget_type_for(widget)
                key = make_choices_key(self.__class__, name)
                registration = SearchRegistration(
                    search_func=method,
                    search_decorator=decorator if callable(decorator) else None,
                    widget_type=widget_type,
                )
                register(key, registration)
                widget._registry_key = key  # noqa: SLF001

    def _register_model_search(
        self,
        field_name: str,
        widget: SearchSelect | MultiSelect | ComboBox,
        field: Field,
        search_fields: tuple[str, ...],
        queryset: QuerySet,
    ) -> None:
        from django_formwork._registry import SearchRegistration, make_key, register
        from django_formwork.widgets import MultiSelect

        model_label = queryset.model._meta.label_lower  # noqa: SLF001
        to_field_name = getattr(field, "to_field_name", None) or "pk"
        key = make_key(type(self), field_name, model_label, search_fields, to_field_name)

        widget_type = "multi_select" if isinstance(widget, MultiSelect) else "search_select"
        # Callbacks live on the field.  Formwork fields expose icon/description
        # callbacks; plain ModelChoiceField only exposes label_from_instance.
        label_func = getattr(field, "label_from_instance", None)
        icon_func = None
        desc_func = None
        if isinstance(field, (FormworkModelChoiceField, FormworkModelMultipleChoiceField)):
            icon_func = field.icon_from_instance
            desc_func = field.description_from_instance
        base_qs = queryset

        registration = SearchRegistration(
            queryset_factory=lambda qs=base_qs: qs.all(),  # type: ignore[misc]
            search_fields=tuple(search_fields),
            to_field_name=to_field_name,
            label_from_instance=label_func,
            icon_from_instance=icon_func,
            description_from_instance=desc_func,
            search_decorator=widget.search_decorator if callable(widget.search_decorator) else None,
            widget_type=widget_type,
        )
        register(key, registration)
        widget._registry_key = key  # noqa: SLF001

    @staticmethod
    def _widget_type_for(widget: SearchSelect | MultiSelect | ComboBox) -> str:
        from django_formwork.widgets import ComboBox, MultiSelect

        if isinstance(widget, MultiSelect):
            return "multi_select"
        if isinstance(widget, ComboBox):
            return "combo_box"
        return "search_select"


class _ErrorDisplayFormMixin:
    """Choose how field errors render: DaisyUI tooltip or inline (help-text style).

    ``error_display`` is ``"inline"`` (default) or ``"tooltip"``, set via
    ``Meta.error_display`` or the matching ``__init__`` kwarg.  Read by
    ``formwork_field.html`` as ``field.form.error_display``.
    """

    def __init__(self, *args: Any, error_display: str | None = None, **kwargs: Any) -> None:
        if error_display is None:
            meta = getattr(type(self), "Meta", None)
            error_display = getattr(meta, "error_display", "inline")
        self.error_display: str = error_display
        super().__init__(*args, **kwargs)


class _DirtyOnlyFormMixin:
    """Skip field-level validation for fields the user didn't change.

    When ``validate_dirty_only`` is on (via ``Meta.validate_dirty_only = True``
    or the ``__init__`` kwarg), ``_clean_fields`` / ``_aclean_fields`` skip
    fields where ``BoundField._has_changed()`` returns False (the per-field
    machinery behind ``Form.changed_data``) and carry the bound field's
    ``initial`` value through to ``cleaned_data``.  ``clean_<name>`` methods
    are skipped for those fields too.
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
        exclude: set[str] = super()._get_validation_exclusions()  # type: ignore[misc]
        if not self._validate_dirty_only or self.instance._state.adding:  # noqa: SLF001
            return exclude
        dirty = set(self.instance.get_dirty_fields())
        for f in self.instance._meta.fields:  # noqa: SLF001
            if not f.primary_key and f.name not in dirty:
                exclude.add(f.name)
        return exclude

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


class FormworkForm(_ErrorDisplayFormMixin, _DirtyOnlyFormMixin, AsyncFormMixin, _AutoSearchMixin, Form):
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

    Field errors render inline (below the widget, help-text style) by default.
    Pass ``error_display="tooltip"`` (or set ``Meta.error_display = "tooltip"``)
    to render them in a DaisyUI tooltip instead.
    """

    default_renderer = FormworkRenderer


class FormworkModelForm(
    _ErrorDisplayFormMixin,
    _DirtyOnlyModelFormMixin,
    AsyncModelFormMixin,
    _AutoSearchMixin,
    ModelForm,
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling and async support.

    With ``Meta.validate_dirty_only = True`` (or the matching ``__init__``
    kwarg), field validation, model field validation, unique checks and
    constraint checks are all skipped for fields the user did not change.
    Requires the bound model to inherit :class:`~django_formwork.FormworkModel`.

    Field errors render inline (below the widget, help-text style) by default.
    Pass ``error_display="tooltip"`` (or set ``Meta.error_display = "tooltip"``)
    to render them in a DaisyUI tooltip instead.
    """

    default_renderer = FormworkRenderer


class FormworkJinja2Form(_ErrorDisplayFormMixin, _DirtyOnlyFormMixin, AsyncFormMixin, _AutoSearchMixin, Form):
    """Form base class with DaisyUI styling (Jinja2 renderer) and async support.

    Use this when your project uses Jinja2 templates.  Equivalent to
    :class:`FormworkForm` but renders via
    :class:`~django_formwork.renderers.FormworkJinja2Renderer`.
    """

    default_renderer = FormworkJinja2Renderer


class FormworkJinja2ModelForm(
    _ErrorDisplayFormMixin,
    _DirtyOnlyModelFormMixin,
    AsyncModelFormMixin,
    _AutoSearchMixin,
    ModelForm,
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling (Jinja2 renderer) and async support."""

    default_renderer = FormworkJinja2Renderer
