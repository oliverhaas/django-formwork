"""CountryInput widget."""

from __future__ import annotations

from typing import Any

from .search_select import SearchSelect


class CountryInput(SearchSelect):
    """Searchable country selector with flag emojis.

    Pre-loaded with all ISO 3166-1 countries.  Submits the two-letter
    country code (e.g. ``"US"``, ``"DE"``).

    Usage::

        country = forms.ChoiceField(widget=CountryInput())
    """

    def __init__(self, attrs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        from django_formwork.data import country_choices

        super().__init__(attrs=attrs, choices=tuple(country_choices()), **kwargs)
        self._country_choices = self.choices

    @property
    def choices(self):  # noqa: ANN201
        return self._country_choices

    @choices.setter
    def choices(self, value: Any) -> None:  # noqa: ANN401
        # Ignore empty choices from ChoiceField.__init__ — keep countries.
        if value:
            self._country_choices = value
