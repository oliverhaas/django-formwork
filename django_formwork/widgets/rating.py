"""Rating widget."""

from __future__ import annotations

from typing import Any

from django import forms
from django.utils.functional import lazy
from django.utils.translation import ngettext


def _star_label(count: int) -> str:
    return ngettext("%(count)d star", "%(count)d stars", count) % {"count": count}


# Choices are built at import time, before a language is active.
_lazy_star_label = lazy(_star_label, str)


class Rating(forms.RadioSelect):
    """Star-rating widget using DaisyUI's rating component.

    Renders a ``<div class="rating">`` containing radio inputs styled as
    stars.  The existing ``mask`` and ``rating-hidden`` classes on the radios
    exclude them from the default ``radio`` CSS rule.

    Usage::

        from django_formwork.widgets import Rating

        rating = forms.TypedChoiceField(
            choices=Rating.make_choices(5),
            coerce=int,
            widget=Rating(),
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
        """The star labels translate when rendered, so the choices can sit on a form class."""
        return [(str(i), _lazy_star_label(i)) for i in range(1, max_stars + 1)]

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["star_class"] = self.star_class
        context["widget"]["allow_clear"] = self.allow_clear
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                # The template owns the class list; attrs.html would render a second class.
                option["css_class"] = option["attrs"].pop("class", "")
        return context
