"""Convenience form base classes with DaisyUI integration.

:class:`FormworkForm` and :class:`FormworkModelForm` use
:class:`~django_formwork.renderers.FormworkRenderer` so that both
``{{ form }}`` and ``{{ field.as_field_group }}`` produce DaisyUI-styled
markup.  All component styling is handled by the formwork CSS file via
``@apply`` — no widget attributes are mutated in Python.

Using ``FORM_RENDERER = "django_formwork.FormworkRenderer"`` in settings
is preferred over these base classes (it applies to *all* forms), but
these are useful when you want formwork styling on specific forms only.

When a field's widget has ``search_fields`` set and the field provides a
queryset (e.g. ``ModelChoiceField``), the search endpoint is
automatically registered so that a single ``include("django_formwork.urls")``
serves all search views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import Form, ModelForm

from django_formwork.renderers import FormworkRenderer


class _AutoSearchMixin:
    """Mixin that auto-registers search endpoints for widgets with ``search_fields``."""

    if TYPE_CHECKING:
        fields: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._auto_register_search()

    def _auto_register_search(self) -> None:
        from django_formwork.registry import SearchRegistration, make_key, register
        from django_formwork.widgets import MultiSelect, SearchSelect

        for field in self.fields.values():
            widget = field.widget
            if not isinstance(widget, (SearchSelect, MultiSelect)):
                continue
            search_fields = getattr(widget, "search_fields", None)
            if not search_fields:
                continue
            # Already has an explicit search_url — skip auto-registration.
            if widget.search_url:
                continue
            queryset = getattr(field, "queryset", None)
            if queryset is None:
                continue

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


class FormworkForm(_AutoSearchMixin, Form):
    """Form base class with DaisyUI styling.

    Usage::

        class ContactForm(FormworkForm):
            name = forms.CharField()
            email = forms.EmailField()
            message = forms.CharField(widget=forms.Textarea)
    """

    default_renderer = FormworkRenderer


class FormworkModelForm(_AutoSearchMixin, ModelForm):
    """ModelForm base class with DaisyUI styling."""

    default_renderer = FormworkRenderer
