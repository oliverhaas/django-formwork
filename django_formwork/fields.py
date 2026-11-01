"""Model choice fields whose choices carry ``ChoiceLabel`` extras.

``FormworkModelChoiceField`` builds each label from the ``icon_from_instance``,
``description_from_instance`` and ``selected_toggle_class_from_instance`` callbacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.forms.models import ModelChoiceIterator, ModelChoiceIteratorValue

from django_formwork.widgets.select import ChoiceLabel

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import Model

__all__ = [
    "FormworkModelChoiceField",
    "FormworkModelMultipleChoiceField",
]


class _ChoiceIterator(ModelChoiceIterator):
    """Choice iterator that yields ``ChoiceLabel`` instead of plain strings."""

    def choice(self, obj: Model) -> tuple:
        value = self.field.prepare_value(obj)
        field: Any = self.field
        label = ChoiceLabel(
            field.label_from_instance(obj),
            icon=field.icon_from_instance(obj),
            description=field.description_from_instance(obj),
            selected_toggle_class=field.selected_toggle_class_from_instance(obj),
        )
        return (ModelChoiceIteratorValue(value, obj), label)


class FormworkModelChoiceField(ModelChoiceField):
    """ModelChoiceField with ``icon_from_instance`` and ``description_from_instance``.

    All three callbacks (``label_from_instance``, ``icon_from_instance``,
    ``description_from_instance``) work as both constructor kwargs and
    overridable methods.
    """

    iterator = _ChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        selected_toggle_class_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[method-assign]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[method-assign]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[method-assign]
        if selected_toggle_class_from_instance is not None:
            self.selected_toggle_class_from_instance = selected_toggle_class_from_instance  # type: ignore[method-assign]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    def description_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    def selected_toggle_class_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    @classmethod
    def from_field(cls, field: ModelChoiceField) -> FormworkModelChoiceField:
        """Create a FormworkModelChoiceField from an existing ModelChoiceField."""
        new_field = cls(
            queryset=field.queryset,
            empty_label=field.empty_label,
            required=field.required,
            widget=field.widget,
            label=field.label,
            initial=field.initial,
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
            limit_choices_to=field.limit_choices_to,
            # ModelChoiceField consumes blank without storing it; the source
            # field's resolved empty_label is the only surviving signal.
            blank=field.empty_label is not None,
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        new_field.disabled = field.disabled
        new_field.localize = field.localize
        new_field.label_suffix = field.label_suffix
        new_field.show_hidden_initial = field.show_hidden_initial
        return new_field


class FormworkModelMultipleChoiceField(ModelMultipleChoiceField):
    """ModelMultipleChoiceField with enriched choice labels."""

    iterator = _ChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        selected_toggle_class_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[method-assign]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[method-assign]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[method-assign]
        if selected_toggle_class_from_instance is not None:
            self.selected_toggle_class_from_instance = selected_toggle_class_from_instance  # type: ignore[method-assign]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    def description_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    def selected_toggle_class_from_instance(self, obj: Model) -> str:  # noqa: ARG002
        return ""

    @classmethod
    def from_field(cls, field: ModelMultipleChoiceField) -> FormworkModelMultipleChoiceField:
        """Create a FormworkModelMultipleChoiceField from an existing ModelMultipleChoiceField."""
        new_field = cls(
            queryset=field.queryset,
            required=field.required,
            widget=field.widget,
            label=field.label,
            initial=field.initial,
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
            limit_choices_to=field.limit_choices_to,
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        new_field.disabled = field.disabled
        new_field.localize = field.localize
        new_field.label_suffix = field.label_suffix
        new_field.show_hidden_initial = field.show_hidden_initial
        return new_field
