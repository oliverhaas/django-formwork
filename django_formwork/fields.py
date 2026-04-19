"""Enriched choice fields for django-formwork.

``FormworkChoiceLabel`` wraps a choice label with optional ``icon`` and
``description``.  ``FormworkModelChoiceField`` uses it to produce enriched
choices from a queryset via ``icon_from_instance`` and
``description_from_instance`` callbacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.forms.models import ModelChoiceIterator, ModelChoiceIteratorValue

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import Model


class FormworkChoiceLabel:
    """A string-like choice label that carries optional icon and description.

    Any code expecting a plain string (Django admin, built-in widgets,
    templates) sees the label text via ``__str__``.  Widgets that understand
    ``FormworkChoiceLabel`` can read ``.icon`` and ``.description``.

    Usage::

        choices = [
            ("nyc", FormworkChoiceLabel("New York", icon="building")),
            ("ldn", FormworkChoiceLabel("London", icon="landmark")),
        ]
    """

    __slots__ = ("description", "icon", "label")

    def __init__(self, label: str, *, icon: str = "", description: str = "") -> None:
        self.label = label
        self.icon = icon
        self.description = description

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        parts = [repr(self.label)]
        if self.icon:
            parts.append(f"icon={self.icon!r}")
        if self.description:
            parts.append(f"description={self.description!r}")
        return f"FormworkChoiceLabel({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.label == other
        if isinstance(other, FormworkChoiceLabel):
            return self.label == other.label and self.icon == other.icon and self.description == other.description
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.label)


class FormworkModelChoiceIterator(ModelChoiceIterator):
    """Choice iterator that yields ``FormworkChoiceLabel`` instead of plain strings."""

    def choice(self, obj: Model) -> tuple:
        value = self.field.prepare_value(obj)
        label = FormworkChoiceLabel(
            self.field.label_from_instance(obj),
            icon=self.field.icon_from_instance(obj),
            description=self.field.description_from_instance(obj),
        )
        return (ModelChoiceIteratorValue(value, obj), label)


class FormworkModelChoiceField(ModelChoiceField):
    """ModelChoiceField with ``icon_from_instance`` and ``description_from_instance``.

    All three callbacks (``label_from_instance``, ``icon_from_instance``,
    ``description_from_instance``) work as both constructor kwargs and
    overridable methods.
    """

    iterator = FormworkModelChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[assignment]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[assignment]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[assignment]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:
        return ""

    def description_from_instance(self, obj: Model) -> str:
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
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        return new_field


class FormworkModelMultipleChoiceField(ModelMultipleChoiceField):
    """ModelMultipleChoiceField with enriched choice labels."""

    iterator = FormworkModelChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[assignment]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[assignment]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[assignment]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:
        return ""

    def description_from_instance(self, obj: Model) -> str:
        return ""

    @classmethod
    def from_field(cls, field: ModelMultipleChoiceField) -> FormworkModelMultipleChoiceField:
        """Create a FormworkModelMultipleChoiceField from an existing ModelMultipleChoiceField."""
        new_field = cls(
            queryset=field.queryset,
            required=field.required,
            widget=field.widget,
            label=field.label,
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        return new_field


__all__ = [
    "FormworkChoiceLabel",
    "FormworkModelChoiceField",
    "FormworkModelChoiceIterator",
    "FormworkModelMultipleChoiceField",
]
