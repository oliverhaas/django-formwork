"""Simple widgets: Toggle, Range, Rating, PasswordReveal, DataList."""

from __future__ import annotations

from typing import Any

from django import forms


class Toggle(forms.CheckboxInput):
    """Checkbox rendered as a DaisyUI toggle switch."""

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        defaults: dict[str, Any] = {}
        if attrs:
            defaults.update(attrs)
        cls = defaults.get("class", "")
        defaults["class"] = f"toggle {cls}".strip()
        super().__init__(defaults)


class Range(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI."""

    input_type = "range"


class Rating(forms.RadioSelect):
    """Star-rating widget using DaisyUI's rating component."""

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


class PasswordReveal(forms.PasswordInput):
    """Password input with a show/hide toggle button."""

    template_name = "formwork/widgets/password_reveal.html"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, render_value=False)


class DataList(forms.TextInput):
    """Text input with native ``<datalist>`` browser suggestions."""

    template_name = "formwork/widgets/datalist.html"

    def __init__(self, *, datalist: list[str] | None = None, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs)
        self.datalist = datalist or []

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget_id = context["widget"]["attrs"].get("id")
        if widget_id:
            context["widget"]["attrs"]["list"] = f"{widget_id}_list"
        context["widget"]["datalist"] = self.datalist
        return context
