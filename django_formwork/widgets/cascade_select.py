"""CascadeSelect widget."""

from __future__ import annotations

from typing import Any

from django import forms


class CascadeSelect(forms.Select):
    """Dependent cascading dropdown.

    Renders a select that loads its options dynamically based on the
    value of a parent field.  Uses htmx to fetch options from the server
    when the parent changes.

    Usage::

        country = forms.ChoiceField(choices=COUNTRIES)
        city = forms.ChoiceField(
            widget=CascadeSelect(parent_field="country", search_url="/api/cities/"),
        )
    """

    template_name = "formwork/widgets/cascade_select.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        parent_field: str = "",
        search_url: str = "",
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.parent_field = parent_field
        self.search_url = search_url

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["parent_field"] = self.parent_field
        context["widget"]["search_url"] = self.search_url
        return context
