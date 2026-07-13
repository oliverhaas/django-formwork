"""Enriched choice fields for django-formwork.

``ChoiceLabel`` wraps a choice label with optional ``icon`` and
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

__all__ = [
    "ChoiceLabel",
    "FormworkModelChoiceField",
    "FormworkModelMultipleChoiceField",
]


class ChoiceLabel:
    """A string-like choice label that carries optional icon and description.

    Any code expecting a plain string (Django admin, built-in widgets,
    templates) sees the label text via ``__str__``.  Widgets that understand
    ``ChoiceLabel`` can read ``.icon``, ``.description`` and
    ``.selected_toggle_class``.

    ``selected_toggle_class`` is a free-form CSS class the ``SearchSelect``
    widget moves onto its trigger while this option is selected (e.g. a
    DaisyUI ``select-error`` to recolor the closed box).  It is relayed
    verbatim: the library never interprets or validates it, and the consuming
    app is responsible for making the class exist in its compiled CSS.

    Usage::

        choices = [
            ("nyc", ChoiceLabel("New York", icon="building")),
            ("ldn", ChoiceLabel("London", icon="landmark")),
            ("high", ChoiceLabel("High", selected_toggle_class="select-error")),
        ]
    """

    __slots__ = ("description", "icon", "label", "selected_toggle_class")

    def __init__(
        self,
        label: str,
        *,
        icon: str = "",
        description: str = "",
        selected_toggle_class: str = "",
    ) -> None:
        self.label = label
        self.icon = icon
        self.description = description
        self.selected_toggle_class = selected_toggle_class

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        parts = [repr(self.label)]
        if self.icon:
            parts.append(f"icon={self.icon!r}")
        if self.description:
            parts.append(f"description={self.description!r}")
        if self.selected_toggle_class:
            parts.append(f"selected_toggle_class={self.selected_toggle_class!r}")
        return f"ChoiceLabel({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.label == other
        if isinstance(other, ChoiceLabel):
            return (
                self.label == other.label
                and self.icon == other.icon
                and self.description == other.description
                and self.selected_toggle_class == other.selected_toggle_class
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.label)


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
