"""Rating widget."""

from __future__ import annotations

from typing import Any

from django import forms


class Rating(forms.RadioSelect):
    """Star-rating widget using DaisyUI's rating component.

    Renders a ``<div class="rating">`` containing radio inputs styled as
    stars.  The existing ``mask`` and ``rating-hidden`` classes on the radios
    exclude them from the default ``radio`` CSS rule.

    Usage::

        rating = forms.TypedChoiceField(
            choices=Rating.make_choices(5),
            coerce=int,
            widget=Rating,
        )
    """

    template_name = "formwork/widgets/rating.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        star_class: str = "mask-star-2",
        allow_clear: bool = False,
    ) -> None:
        super().__init__(attrs)
        self.star_class = star_class
        self.allow_clear = allow_clear

    @staticmethod
    def make_choices(max_stars: int = 5) -> list[tuple[str, str]]:
        """Return a choices list for 1..max_stars."""
        return [(str(i), f"{i} star{'s' if i != 1 else ''}") for i in range(1, max_stars + 1)]

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["star_class"] = self.star_class
        context["widget"]["allow_clear"] = self.allow_clear
        return context
