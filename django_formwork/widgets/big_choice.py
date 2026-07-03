"""Big choice-card widgets."""

from __future__ import annotations

from typing import Any

from django import forms
from django.forms.widgets import ChoiceWidget


class _BigChoiceMixin(ChoiceWidget):
    """Shared rendering for the big choice-card widgets.

    Renders each choice as a large, full-width selectable card instead of a
    compact radio or checkbox row.  The whole card is clickable and lights up
    in the primary colour when selected.
    """

    template_name = "formwork/widgets/big_choice.html"

    def get_context(self, name: str, value: str | list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        # Django sets the hyphenated ``aria-invalid`` on errored widgets; the
        # key is awkward to read in a template, so surface it for the error border.
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        return context


class BigRadioSelect(_BigChoiceMixin, forms.RadioSelect):
    """Radio choices rendered as large, full-width selectable cards (single select).

    Usage::

        plan = forms.ChoiceField(
            choices=[("basic", "Basic"), ("pro", "Pro")],
            widget=BigRadioSelect,
        )
    """


class BigCheckboxSelect(_BigChoiceMixin, forms.CheckboxSelectMultiple):
    """Checkbox choices rendered as large, full-width selectable cards (multi select).

    Usage::

        addons = forms.MultipleChoiceField(
            choices=[("ssl", "SSL"), ("cdn", "CDN")],
            widget=BigCheckboxSelect,
        )
    """
