"""Custom form widgets for django-formwork.

Provides widgets that require custom HTML structure beyond what
Django's built-in widget templates offer:

- :class:`Toggle` — checkbox rendered as a DaisyUI toggle switch
- :class:`Range` — HTML5 range slider
- :class:`Rating` — star-rating using radio inputs
- :class:`PasswordReveal` — password input with show/hide toggle
- :class:`MultiSelect` — dropdown with checkboxes
- :class:`SearchSelect` — single-select dropdown with text search
- :class:`ComboBox` — text input with autocomplete suggestions
- :class:`DataList` — text input with native ``<datalist>`` suggestions

All DaisyUI component classes (``input``, ``select``, etc.) are applied
via CSS selectors in ``formwork.css``, not in Python.  Custom widgets use
CSS classes or structural selectors so they can be styled independently
from standard Django widgets.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import forms

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------


class Toggle(forms.CheckboxInput):
    """Checkbox rendered as a DaisyUI toggle switch.

    Adds the ``toggle`` class so CSS applies the DaisyUI toggle styling
    instead of ``checkbox``.

    Usage::

        agree = forms.BooleanField(widget=Toggle)
    """

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        defaults: dict[str, Any] = {}
        if attrs:
            defaults.update(attrs)
        cls = defaults.get("class", "")
        defaults["class"] = f"toggle {cls}".strip()
        super().__init__(defaults)


class Range(forms.NumberInput):
    """HTML5 range slider styled with DaisyUI.

    CSS targets ``input[type="range"]`` directly — no extra attributes
    needed.

    Usage::

        volume = forms.IntegerField(widget=Range(attrs={"min": 0, "max": 100}))
    """

    input_type = "range"


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


class PasswordReveal(forms.PasswordInput):
    """Password input with a show/hide toggle button.

    Wraps the input in a ``<label class="password-reveal">`` container with
    a toggle button.  Uses Alpine.js for the reveal functionality.  DaisyUI's
    ``.input`` styling is applied via CSS ``@apply`` on the label, so the
    direct-child CSS selector for text inputs doesn't match it.

    Usage::

        password = forms.CharField(widget=PasswordReveal)
    """

    template_name = "formwork/widgets/password_reveal.html"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, render_value=False)


class MultiSelect(forms.SelectMultiple):
    """Multi-select dropdown with checkboxes.

    Renders a DaisyUI-styled dropdown button that opens a panel of checkboxes.
    Uses Alpine.js for open/close state and selected-count display.
    The template adds the ``multiselect`` class on checkboxes so
    CSS doesn't apply the default ``checkbox`` class.

    When ``search_url`` is provided, the search input uses htmx to fetch
    options from the server.  Selected values are tracked in Alpine state
    and submitted via hidden inputs (not the visible checkboxes).

    Usage::

        languages = forms.MultipleChoiceField(
            choices=[("py", "Python"), ("js", "JavaScript")],
            widget=MultiSelect,
        )

        # With server-side search:
        languages = forms.MultipleChoiceField(
            widget=MultiSelect(search_url=reverse_lazy("lang-search")),
        )

    ``icons`` values should be wrapped in ``mark_safe()`` — plain strings
    are auto-escaped by the template engine.
    """

    template_name = "formwork/widgets/multi_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        icons: dict[str, str] | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.icons = icons or {}
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.icon_from_instance = icon_from_instance
        self.description_from_instance = description_from_instance
        self._registry_key: str | None = None

    def get_context(self, name: str, value: list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        total = sum(len(options) for _, options, _ in context["widget"]["optgroups"])
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        else:
            context["widget"]["show_search"] = total >= self.search_threshold or bool(search_url)
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        context["widget"]["search_url"] = search_url
        # Inject icons into option data.
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                option["icon"] = self.icons.get(str(option["value"]), "")
        if search_url:
            # Build initial selected map for Alpine: [[value, [label, icon]], ...]
            selected_values = set(value or [])
            initial_selected = [
                [str(option["value"]), [str(option["label"]), option.get("icon", "")]]
                for _group, options, _index in context["widget"]["optgroups"]
                for option in options
                if str(option["value"]) in selected_values
            ]
            context["widget"]["initial_selected_json"] = json.dumps(initial_selected)
        return context


class SearchSelect(forms.Select):
    """Single-select dropdown with text search/filter.

    Renders a DaisyUI-styled dropdown with a text input for filtering
    options.  Submits a single key value via a hidden ``<input>`` element.
    Uses Alpine.js for filtering, keyboard navigation, and selection.

    This is a ``<select>`` replacement — the submitted value is a key
    from the choices list, not free text.

    When ``search_url`` is provided, the text input uses htmx to fetch
    matching options from the server instead of client-side filtering.

    Usage::

        city = forms.ChoiceField(
            choices=[("nyc", "New York"), ("ldn", "London"), ...],
            widget=SearchSelect,
        )

        # With server-side search:
        city = forms.ChoiceField(
            widget=SearchSelect(search_url=reverse_lazy("city-search")),
        )
    """

    template_name = "formwork/widgets/search_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        icons: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.icons = icons or {}
        self.descriptions = descriptions or {}
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.icon_from_instance = icon_from_instance
        self.description_from_instance = description_from_instance
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        # Select.format_value() wraps value in a list — unwrap for template.
        fmt_value = context["widget"]["value"]
        if isinstance(fmt_value, (list, tuple)):
            context["widget"]["value"] = fmt_value[0] if fmt_value else ""
        # Single pass: find selected label/icon AND inject icons/descriptions.
        selected_label = ""
        selected_icon = ""
        total = 0
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                val_str = str(option["value"])
                option["icon"] = self.icons.get(val_str, "")
                option["description"] = self.descriptions.get(val_str, "")
                if option["selected"]:
                    selected_label = str(option["label"])
                    selected_icon = option["icon"]
                total += 1
        context["widget"]["selected_label"] = selected_label
        context["widget"]["selected_icon"] = selected_icon
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        context["widget"]["search_threshold"] = self.search_threshold
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url:
            # Server-side search: start hidden, let OOB total-count swap decide.
            context["widget"]["show_search"] = False
        else:
            context["widget"]["show_search"] = total >= self.search_threshold
        return context


class ComboBox(forms.TextInput):
    """Text input with autocomplete suggestions.

    Renders a text input with a dropdown of suggestions that appear as the
    user types.  The submitted value is whatever the user typed (free text),
    not a key from a choices list.  Suggestions are just hints.

    In multiple mode (``multiple=True``), accepts comma-separated values.
    Suggestions appear for the segment currently being typed.

    Usage::

        tags = forms.CharField(
            widget=ComboBox(suggestions=["Python", "JavaScript", "Go"]),
        )

        # Multiple mode:
        tags = forms.CharField(
            widget=ComboBox(
                suggestions=["pizza", "pasta", "sushi"],
                multiple=True,
            ),
        )
    """

    template_name = "formwork/widgets/combo_box.html"

    def __init__(  # noqa: PLR0913
        self,
        *,
        suggestions: list[str] | None = None,
        multiple: bool = False,
        search_url: str | None = None,
        icons: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs)
        self.suggestions = suggestions or []
        self.multiple = multiple
        self.search_url = search_url
        self.icons = icons or {}
        self.descriptions = descriptions or {}
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["suggestions"] = [
            {"text": s, "icon": self.icons.get(s, ""), "description": self.descriptions.get(s, "")}
            for s in self.suggestions
        ]
        context["widget"]["multiple"] = self.multiple
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        # Resolve search URL: explicit > auto-registered > none.
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse

            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        # Build initial icon map from current value for unfocused display.
        context["widget"]["icons_json"] = json.dumps(
            {s: self.icons[s] for s in self.suggestions if s in self.icons},
            ensure_ascii=False,
        )
        return context


_KB = 1024
_MB = 1024 * 1024


def _format_size(size: int) -> str:
    """Format a byte count for human-readable display.

    Examples::

        >>> _format_size(500)
        '500 B'
        >>> _format_size(1024)
        '1 KB'
        >>> _format_size(5 * 1024 * 1024)
        '5 MB'
    """
    if size < _KB:
        return f"{size} B"
    if size < _MB:
        kb = size / _KB
        return f"{kb:.0f} KB" if kb == int(kb) else f"{kb:.1f} KB"
    mb = size / _MB
    return f"{mb:.0f} MB" if mb == int(mb) else f"{mb:.1f} MB"


def _format_accept(accept: str) -> str:
    """Format an HTML ``accept`` attribute value for human-readable display.

    Examples::

        >>> _format_accept("image/*")
        'Images'
        >>> _format_accept(".png,.jpg,.jpeg")
        'PNG, JPG, JPEG'
        >>> _format_accept("application/pdf")
        'PDF'
    """
    parts = [p.strip() for p in accept.split(",") if p.strip()]
    labels: list[str] = []
    for part in parts:
        if part.endswith("/*"):
            labels.append(part.split("/")[0].capitalize() + "s")
        elif part.startswith("."):
            labels.append(part[1:].upper())
        elif "/" in part:
            labels.append(part.split("/")[1].upper())
        else:
            labels.append(part.upper())
    return ", ".join(labels)


class FileDropZone(forms.FileInput):
    """Drag-and-drop file upload zone.

    Replaces the standard file input with a styled drop zone that accepts
    dragged files or click-to-browse.  Uses Alpine.js for drag state and
    file list display.

    Usage::

        attachment = forms.FileField(widget=FileDropZone)

        # Multiple files with type and size restrictions:
        docs = forms.FileField(
            widget=FileDropZone(
                attrs={"multiple": True, "accept": ".pdf,.doc,.docx"},
                max_size=10 * 1024 * 1024,  # 10 MB
            ),
        )
    """

    template_name = "formwork/widgets/drop_zone.html"
    allow_multiple_selected = True

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        super().__init__(attrs)
        self.max_size = max_size

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        accept = context["widget"]["attrs"].get("accept", "")
        if accept:
            context["widget"]["accept_display"] = _format_accept(accept)
        if self.max_size is not None:
            context["widget"]["max_size"] = self.max_size
            context["widget"]["max_size_display"] = _format_size(self.max_size)
        return context


class ImageDropZone(forms.FileInput):
    """Drag-and-drop image upload with preview.

    Like :class:`FileDropZone` but restricted to images and shows a
    thumbnail preview after selection.  Uses Alpine.js for drag state,
    preview via ``FileReader``, and a remove button.

    Usage::

        avatar = forms.ImageField(widget=ImageDropZone)
    """

    template_name = "formwork/widgets/image_upload.html"

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        *,
        max_size: int | None = None,
    ) -> None:
        defaults: dict[str, Any] = {"accept": "image/*"}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)
        self.max_size = max_size

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        accept = context["widget"]["attrs"].get("accept", "")
        if accept:
            context["widget"]["accept_display"] = _format_accept(accept)
        if self.max_size is not None:
            context["widget"]["max_size"] = self.max_size
            context["widget"]["max_size_display"] = _format_size(self.max_size)
        return context


class ValidatedTextarea(forms.Textarea):
    """Textarea with server-side validation and word highlighting.

    Renders a textarea with a highlight overlay.  When ``validate_url``
    is provided, htmx sends the text to the server after a debounce.
    The server returns highlighted HTML (with ``<mark>`` tags around
    errors) that displays beneath the transparent textarea, plus error
    messages via out-of-band swap.

    Without ``validate_url``, renders as a normal textarea.

    Usage::

        content = forms.CharField(
            widget=ValidatedTextarea(validate_url=reverse_lazy("validate-text")),
        )
    """

    template_name = "formwork/widgets/validated_textarea.html"

    def __init__(self, attrs: dict[str, Any] | None = None, *, validate_url: str | None = None) -> None:
        super().__init__(attrs)
        self.validate_url = validate_url

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"]["validate_url"] = self.validate_url
        return context


class DataList(forms.TextInput):
    """Text input with native ``<datalist>`` browser suggestions.

    Renders an ``<input>`` with a ``list`` attribute pointing to a
    ``<datalist>`` containing the provided suggestions.  No JavaScript
    required — the browser provides the autocomplete dropdown natively.

    Note: the submitted value is whatever the user typed (free text),
    not a key from a choices list.

    Usage::

        browser = forms.CharField(
            widget=DataList(datalist=["Chrome", "Firefox", "Safari"]),
        )
    """

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
