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

from django.forms import Form, ModelForm

from django_formwork.async_forms import AsyncFormMixin, AsyncModelFormMixin
from django_formwork.renderers import FormworkRenderer

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms import Field

    from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect


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
        from django_formwork.registry import (
            SearchRegistration,
            make_choices_key,
            register,
        )
        from django_formwork.widgets import ComboBox, MultiSelect, SearchSelect

        for name, field in self.fields.items():
            widget = field.widget
            if not isinstance(widget, (SearchSelect, MultiSelect, ComboBox)):
                continue
            # Already has an explicit search_url — skip auto-registration.
            if widget.search_url:
                continue

            # Path 1: model-backed (search_fields on widget + queryset on field).
            search_fields = getattr(widget, "search_fields", None)
            queryset = getattr(field, "queryset", None)
            if search_fields and queryset is not None:
                self._register_model_search(widget, field, search_fields, queryset)
                continue

            # Path 2: choices-backed (search_choices_<name> method on form).
            method = getattr(self.__class__, f"search_choices_{name}", None)
            if method is not None:
                widget_type = self._widget_type_for(widget)
                key = make_choices_key(self.__class__, name)
                registration = SearchRegistration(
                    search_func=method,
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
        label_func = getattr(field, "label_from_instance", None)
        base_qs = queryset

        registration = SearchRegistration(
            queryset_factory=lambda qs=base_qs: qs.all(),  # type: ignore[misc]
            search_fields=tuple(search_fields),
            to_field_name=to_field_name,
            label_from_instance=label_func,
            icon_from_instance=getattr(widget, "icon_from_instance", None),
            description_from_instance=getattr(widget, "description_from_instance", None),
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


class FormworkModelForm(AsyncModelFormMixin, _AutoSearchMixin, ModelForm):
    """ModelForm base class with DaisyUI styling and async support."""

    default_renderer = FormworkRenderer
