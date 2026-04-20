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

from typing import TYPE_CHECKING, Any

from django.forms import Form, ModelChoiceField, ModelForm, ModelMultipleChoiceField
from django.forms.models import ModelFormMetaclass

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

        from django_formwork.registry import (
            SearchRegistration,
            make_choices_key,
            register,
        )
        from django_formwork.widgets import _NOT_SET, ComboBox, MultiSelect, SearchSelect

        for name, field in self.fields.items():
            widget = field.widget
            if not isinstance(widget, (SearchSelect, MultiSelect, ComboBox)):
                continue
            # Already has an explicit search_url — skip auto-registration.
            if widget.search_url:
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
                self._register_model_search(widget, field, search_fields, queryset)
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

    @staticmethod
    def _register_model_search(
        widget: SearchSelect | MultiSelect | ComboBox,
        field: Field,
        search_fields: tuple[str, ...],
        queryset: QuerySet,
    ) -> None:
        from django_formwork.registry import SearchRegistration, make_key, register
        from django_formwork.widgets import MultiSelect

        model_label = queryset.model._meta.label_lower  # noqa: SLF001
        to_field_name = getattr(field, "to_field_name", None) or "pk"
        key = make_key(model_label, search_fields, to_field_name)

        widget_type = "multiselect" if isinstance(widget, MultiSelect) else "search_select"
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
            return "multiselect"
        if isinstance(widget, ComboBox):
            return "combobox"
        return "search_select"


class FormworkForm(AsyncFormMixin, _AutoSearchMixin, Form):
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
    """

    default_renderer = FormworkRenderer


class FormworkModelForm(AsyncModelFormMixin, _AutoSearchMixin, ModelForm, metaclass=FormworkModelFormMetaclass):
    """ModelForm base class with DaisyUI styling and async support."""

    default_renderer = FormworkRenderer


class FormworkJinja2Form(AsyncFormMixin, _AutoSearchMixin, Form):
    """Form base class with DaisyUI styling (Jinja2 renderer) and async support.

    Use this when your project uses Jinja2 templates.  Equivalent to
    :class:`FormworkForm` but renders via
    :class:`~django_formwork.renderers.FormworkJinja2Renderer`.
    """

    default_renderer = FormworkJinja2Renderer


class FormworkJinja2ModelForm(
    AsyncModelFormMixin,
    _AutoSearchMixin,
    ModelForm,
    metaclass=FormworkModelFormMetaclass,
):
    """ModelForm base class with DaisyUI styling (Jinja2 renderer) and async support."""

    default_renderer = FormworkJinja2Renderer
