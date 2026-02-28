"""Custom form widgets for django-formwork.

Provides widgets that require custom HTML structure beyond what
Django's built-in widget templates offer:

- :class:`ToggleInput` — checkbox rendered as a DaisyUI toggle switch
- :class:`RangeInput` — HTML5 range slider
- :class:`RatingInput` — star-rating using radio inputs
- :class:`PasswordRevealInput` — password input with show/hide toggle
- :class:`MultiSelectInput` — dropdown with checkboxes

All DaisyUI component classes (``input``, ``select``, etc.) are applied
via CSS selectors in ``formwork.css``, not in Python.  Custom widgets use
``data-formwork`` attributes so CSS can distinguish them from standard
Django widgets.
"""

from __future__ import annotations

from typing import Any

from django import forms

# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------


class ToggleInput(forms.CheckboxInput):
    """Checkbox rendered as a DaisyUI toggle switch.

    Adds ``data-formwork="toggle"`` so CSS applies the ``toggle`` class
    instead of ``checkbox``.

    Usage::

        agree = forms.BooleanField(widget=ToggleInput)
    """

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        defaults: dict[str, Any] = {"data-formwork": "toggle"}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)


class RangeInput(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI.

    CSS targets ``input[type="range"]`` directly — no extra attributes
    needed.

    Usage::

        volume = forms.IntegerField(widget=RangeInput(attrs={"min": 0, "max": 100}))
    """

    input_type = "range"


class RatingInput(forms.RadioSelect):
    """Star-rating widget using DaisyUI's rating component.

    Renders a ``<div class="rating">`` containing radio inputs styled as
    stars.  The template adds ``data-formwork="rating"`` on each radio
    so CSS doesn't apply the default ``radio`` class.

    Usage::

        rating = forms.TypedChoiceField(
            choices=RatingInput.make_choices(5),
            coerce=int,
            widget=RatingInput,
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


class PasswordRevealInput(forms.PasswordInput):
    """Password input with a show/hide toggle button.

    Wraps the input in a DaisyUI ``<label class="input">`` container with a
    toggle button.  Uses Alpine.js for the reveal functionality.  The
    template adds ``data-formwork="password-reveal"`` so CSS doesn't
    double-apply the ``input`` class.

    Usage::

        password = forms.CharField(widget=PasswordRevealInput)
    """

    template_name = "formwork/widgets/password_reveal.html"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, render_value=False)


class MultiSelectInput(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes.

    Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes.
    Uses Alpine.js for open/close state and selected-count display.
    The template adds ``data-formwork="multiselect"`` on checkboxes so
    CSS doesn't apply the default ``checkbox`` class.

    Usage::

        languages = forms.MultipleChoiceField(
            choices=[("py", "Python"), ("js", "JavaScript")],
            widget=MultiSelectInput,
        )
    """

    template_name = "formwork/widgets/multi_select.html"
    option_inherits_attrs = False
