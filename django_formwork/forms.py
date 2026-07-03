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
from django.forms.forms import DeclarativeFieldsMetaclass
from django.forms.models import InlineForeignKeyField, ModelFormMetaclass, construct_instance

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.fields import FormworkModelChoiceField, FormworkModelMultipleChoiceField
from django_formwork.registry import SearchRegistration, make_key, register
from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import QuerySet
    from django.forms import Field
    from django.http import HttpRequest

    from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect

__all__ = [
    "FormworkForm",
    "FormworkFormMetaclass",
    "FormworkJinja2Form",
    "FormworkJinja2ModelForm",
    "FormworkModelForm",
    "FormworkModelFormMetaclass",
]


def _widget_type_for(widget: SearchSelect | MultiSelect | ComboBox) -> str:
    from django_formwork.widgets import ComboBox, MultiSelect

    if isinstance(widget, MultiSelect):
        return "multiselect"
    if isinstance(widget, ComboBox):
        return "combobox"
    return "search_select"


def _model_registration(
    widget: SearchSelect | MultiSelect | ComboBox,
    field: Field,
    search_fields: tuple[str, ...],
    queryset: QuerySet,
    decorator: Callable | None,
) -> SearchRegistration:
    """Build a model-backed :class:`SearchRegistration` for one searchable field."""
    to_field_name = getattr(field, "to_field_name", None) or "pk"
    # Callbacks live on the field.  Formwork fields expose icon/description
    # callbacks; a plain ModelChoiceField only exposes label_from_instance.
    label_func = getattr(field, "label_from_instance", None)
    icon_func = None
    desc_func = None
    if isinstance(field, (FormworkModelChoiceField, FormworkModelMultipleChoiceField)):
        icon_func = field.icon_from_instance
        desc_func = field.description_from_instance

    # Request-scoped queryset factory.  A widget may supply ``search_queryset``
    # (called with the current request, or None at render time) to scope
    # results per request; otherwise fall back to a fresh copy of the field's
    # bound queryset.
    search_queryset = getattr(widget, "search_queryset", None)
    if callable(search_queryset):
        factory = search_queryset
    else:

        def factory(_request: HttpRequest | None, qs: QuerySet = queryset) -> QuerySet:
            return qs.all()

    return SearchRegistration(
        queryset_factory=factory,
        search_fields=tuple(search_fields),
        to_field_name=to_field_name,
        label_from_instance=label_func,
        icon_from_instance=icon_func,
        description_from_instance=desc_func,
        search_decorator=decorator,
        widget_type=_widget_type_for(widget),
    )


def _register_search_widgets(form_cls: type) -> None:
    """Register server-side search endpoints for a form's searchable widgets.

    Called by the form metaclasses at class-definition time, so every endpoint
    exists in every worker process as soon as the form module is imported (see
    :mod:`django_formwork.registry`).  Walks ``base_fields`` and, for each
    ``SearchSelect`` / ``MultiSelect`` / ``ComboBox`` that resolves to a real
    search source, registers a :class:`~django_formwork.registry.SearchRegistration`
    and stamps the widget with its ``_registry_key`` (preserved through the
    per-instance deepcopy of the fields).

    Two paths:

    1. **Model-backed**: widget has ``search_fields`` and the field provides a
       queryset.
    2. **Choices-backed**: the form defines a
       ``search_choices_<fieldname>(query, request)`` static method returning
       results directly (list of dicts or ``(value, label)`` tuples).
    """
    from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect
    from django_formwork.widgets._base import _NOT_SET

    base_fields = getattr(form_cls, "base_fields", None)
    if not base_fields:
        return

    for name, field in base_fields.items():
        widget = field.widget
        if not isinstance(widget, (SearchSelect, MultiSelect, ComboBox)):
            continue

        search_fields = getattr(widget, "search_fields", None)
        queryset = getattr(field, "queryset", None)
        has_model_search = bool(search_fields) and queryset is not None
        method = getattr(form_cls, f"search_choices_{name}", None)

        if not has_model_search and method is None:
            continue

        # Enforce search_decorator: the developer must make a conscious auth
        # choice for every auto-registered search endpoint.
        raw_decorator = getattr(widget, "search_decorator", _NOT_SET)
        if raw_decorator is _NOT_SET:
            widget_cls = type(widget).__name__
            msg = (
                f"Field '{name}' uses {widget_cls} with server-side search but no "
                f"search_decorator was provided. Pass a decorator (e.g. login_required) "
                f"or None for public access."
            )
            raise ImproperlyConfigured(msg)
        decorator = raw_decorator if callable(raw_decorator) else None

        key = make_key(form_cls, name)
        # Model-backed wins when both are present (search_fields is explicit).
        if has_model_search and search_fields is not None and queryset is not None:
            registration = _model_registration(widget, field, search_fields, queryset, decorator)
        else:
            registration = SearchRegistration(
                search_func=method,
                search_decorator=decorator,
                widget_type=_widget_type_for(widget),
            )
        register(key, registration)
        widget._registry_key = key  # noqa: SLF001


class FormworkFormMetaclass(DeclarativeFieldsMetaclass):
    """Metaclass for plain formwork forms that registers search endpoints.

    Once the declarative fields are collected, walk them and register a search
    endpoint for every searchable widget (see :func:`_register_search_widgets`).
    Registering at class-definition time means the endpoints exist in every
    worker as soon as the form module is imported, independent of whether a
    given worker ever rendered the form.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        _register_search_widgets(cls)
        return cls


class FormworkModelFormMetaclass(ModelFormMetaclass):
    """Metaclass that upgrades model choice fields and registers search endpoints.

    Auto-generated ``ModelChoiceField`` / ``ModelMultipleChoiceField`` instances
    (from ``Meta.model`` / ``Meta.fields``) are swapped for their Formwork
    equivalents so icon/description callbacks can be attached to the field.
    Explicit field declarations, including custom subclasses, are left alone.
    After the swap, search endpoints are registered the same way as for plain
    forms (see :func:`_register_search_widgets`).
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
        _register_search_widgets(cls)
        return cls


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


class FormworkForm(_DirtyOnlyFormMixin, AsyncFormMixin, Form, metaclass=FormworkFormMetaclass):
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
    """

    default_renderer = FormworkRenderer


class FormworkModelForm(
    _DirtyOnlyModelFormMixin,
    AsyncModelFormMixin,
    ModelForm,
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling and async support.

    With ``Meta.validate_dirty_only = True`` (or the matching ``__init__``
    kwarg), field validation, model field validation, unique checks and
    constraint checks are all skipped for fields the user did not change.
    Requires the bound model to inherit :class:`~django_formwork.FormworkModel`.
    """

    default_renderer = FormworkRenderer


class FormworkJinja2Form(_DirtyOnlyFormMixin, AsyncFormMixin, Form, metaclass=FormworkFormMetaclass):
    """Form base class with DaisyUI styling (Jinja2 renderer) and async support.

    Use this when your project uses Jinja2 templates.  Equivalent to
    :class:`FormworkForm` but renders via
    :class:`~django_formwork.renderers.FormworkJinja2Renderer`.
    """

    default_renderer = FormworkJinja2Renderer


class FormworkJinja2ModelForm(
    _DirtyOnlyModelFormMixin,
    AsyncModelFormMixin,
    ModelForm,
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling (Jinja2 renderer) and async support."""

    default_renderer = FormworkJinja2Renderer
