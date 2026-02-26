"""DaisyUI-aware form widgets for Django.

Provides:
- ``apply_daisy_classes()`` to auto-add DaisyUI CSS classes to standard widgets
- Custom widgets: ``ToggleInput``, ``RangeInput``, ``RatingInput``,
  ``PasswordRevealInput``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

if TYPE_CHECKING:
    from django.forms import BaseForm

# ---------------------------------------------------------------------------
# CSS class helpers
# ---------------------------------------------------------------------------


def _add_css_class(attrs: dict[str, Any], css_class: str) -> None:
    """Append *css_class* to ``attrs["class"]`` if not already present."""
    existing = attrs.get("class", "")
    if css_class not in existing.split():
        attrs["class"] = f"{existing} {css_class}".strip()


# ---------------------------------------------------------------------------
# DaisyUI class mappings
# ---------------------------------------------------------------------------

#: Map Django widget type → DaisyUI component class.
DAISY_CLASSES: dict[type[forms.Widget], str] = {
    forms.TextInput: "input",
    forms.EmailInput: "input",
    forms.URLInput: "input",
    forms.NumberInput: "input",
    forms.PasswordInput: "input",
    forms.DateInput: "input",
    forms.TimeInput: "input",
    forms.DateTimeInput: "input",
    forms.SearchInput: "input",
    forms.ColorInput: "input",
    forms.TelInput: "input",
    forms.Textarea: "textarea",
    forms.Select: "select",
    forms.SelectMultiple: "select",
    forms.CheckboxInput: "checkbox",
    forms.RadioSelect: "radio",
    forms.CheckboxSelectMultiple: "checkbox",
    forms.FileInput: "file-input",
    forms.ClearableFileInput: "file-input",
}

#: Map DaisyUI component class → error modifier class.
DAISY_ERROR_CLASSES: dict[str, str] = {
    "input": "input-error",
    "textarea": "textarea-error",
    "select": "select-error",
    "checkbox": "checkbox-error",
    "radio": "radio-error",
    "toggle": "toggle-error",
    "file-input": "file-input-error",
    "range": "range-error",
}


def _get_daisy_class(widget: forms.Widget) -> str | None:
    """Return the DaisyUI class for *widget*, or ``None``."""
    return DAISY_CLASSES.get(type(widget))


def _get_error_class(widget: forms.Widget) -> str | None:
    """Return the DaisyUI error class for *widget*, or ``None``."""
    daisy_class = _get_daisy_class(widget)
    if daisy_class is None:
        # Check custom widgets
        for attr_name in ("_daisy_class",):
            daisy_class = getattr(widget, attr_name, None)
            if daisy_class:
                break
    if daisy_class:
        return DAISY_ERROR_CLASSES.get(daisy_class)
    return None


#: Widgets that need custom formwork templates to avoid leaking
#: DaisyUI classes onto the wrapper ``<div>``.
_TEMPLATE_OVERRIDES: dict[type[forms.Widget], str] = {
    forms.RadioSelect: "formwork/widgets/radio.html",
    forms.CheckboxSelectMultiple: "formwork/widgets/checkbox_select.html",
}


def apply_daisy_classes(form: BaseForm) -> None:
    """Add DaisyUI CSS classes to all widgets in *form*.

    Called automatically by :class:`~django_formwork.forms.FormworkForm`.
    """
    for field in form.fields.values():
        widget = field.widget
        css_class = _get_daisy_class(widget)
        if css_class:
            _add_css_class(widget.attrs, css_class)
        # Override templates for multi-input widgets so the DaisyUI class
        # is only applied to individual <input> elements, not the wrapper div.
        template = _TEMPLATE_OVERRIDES.get(type(widget))
        if template:
            widget.template_name = template


# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------


class ToggleInput(forms.CheckboxInput):
    """Checkbox rendered as a DaisyUI toggle switch.

    Usage::

        agree = forms.BooleanField(widget=ToggleInput)
    """

    _daisy_class = "toggle"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs)
        _add_css_class(self.attrs, "toggle")


class RangeInput(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI.

    Usage::

        volume = forms.IntegerField(widget=RangeInput(attrs={"min": 0, "max": 100}))
    """

    input_type = "range"
    _daisy_class = "range"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs)
        _add_css_class(self.attrs, "range")


class RatingInput(forms.RadioSelect):
    """Star-rating widget using DaisyUI's rating component.

    Renders a ``<div class="rating">`` containing radio inputs styled as
    stars.  Works with :class:`~django.forms.ChoiceField` or
    :class:`~django.forms.TypedChoiceField`.

    Usage::

        rating = forms.TypedChoiceField(
            choices=RatingInput.make_choices(5),
            coerce=int,
            widget=RatingInput,
        )
    """

    template_name = "formwork/widgets/rating.html"
    _daisy_class = "rating"

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
    toggle button.  Uses Alpine.js for the reveal functionality.

    Usage::

        password = forms.CharField(widget=PasswordRevealInput)
    """

    template_name = "formwork/widgets/password_reveal.html"
    _daisy_class = "input"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, render_value=False)


class MultiSelectInput(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes.

    Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes.
    Uses Alpine.js for open/close state and selected-count display.

    Usage::

        languages = forms.MultipleChoiceField(
            choices=[("py", "Python"), ("js", "JavaScript")],
            widget=MultiSelectInput,
        )
    """

    template_name = "formwork/widgets/multi_select.html"
    _daisy_class = "select"
    option_inherits_attrs = False
