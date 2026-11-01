"""Single-select dropdown widget, the shared select mixin and ``ChoiceLabel``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, Literal

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from ._base import _ModuleScript, _resolve_initial_results

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from django.db.models import QuerySet
    from django.http import HttpRequest
    from django.utils.choices import _Choices

    # Typed base so mypy resolves the cooperative super() calls. At runtime the
    # mixin inherits object and is placed in front of a concrete select widget.
    _SelectBase = forms.Select
else:
    _SelectBase = object

__all__ = ["BadgeColor", "ChoiceLabel", "SearchableSelectMixin", "Select", "label_extras"]


class _UnsetDecorator:
    """Sentinel for `search_decorator` not being passed."""


_UNSET_DECORATOR = _UnsetDecorator()


BadgeColor = Literal["neutral", "primary", "secondary", "accent", "info", "success", "warning", "error"]


class ChoiceLabel:
    """Choice label whose ``__str__`` is its text; the extras are presentation only.

    ``icon``, ``description`` and ``label_html`` can hold HTML marked safe by the caller.
    ``Select`` puts ``selected_toggle_class`` on its trigger while the option is selected.
    """

    __slots__ = ("color", "description", "icon", "label", "label_html", "selected_toggle_class")

    def __init__(  # noqa: PLR0913
        self,
        label: str,
        *,
        icon: str = "",
        description: str = "",
        label_html: str = "",
        color: BadgeColor = "neutral",
        selected_toggle_class: str = "",
    ) -> None:
        self.label = label
        self.icon = icon
        self.description = description
        self.label_html = label_html
        self.color = color
        self.selected_toggle_class = selected_toggle_class

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        extras = ("icon", "description", "label_html", "selected_toggle_class")
        parts = [repr(self.label)]
        parts.extend(f"{name}={value!r}" for name in extras if (value := getattr(self, name)))
        if self.color != "neutral":
            parts.append(f"color={self.color!r}")
        return f"ChoiceLabel({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.label == other
        if isinstance(other, ChoiceLabel):
            return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.label)


def label_extras(label: object) -> dict[str, str]:
    """What an option row shows beside its text, blank for a plain label."""
    return {
        "icon": getattr(label, "icon", ""),
        "description": getattr(label, "description", ""),
        "label_html": getattr(label, "label_html", ""),
        "selected_toggle_class": getattr(label, "selected_toggle_class", ""),
    }


class SearchableSelectMixin(_SelectBase):
    """Search and dropdown behavior shared by ``Select`` and ``SelectMultiple``."""

    option_inherits_attrs = False
    search_threshold = 10
    # Names the option markup the dispatch view renders for this widget.
    search_variant: ClassVar[str]

    def id_for_label(self, id_: str, index: str = "0") -> str:  # noqa: ARG002
        # The trigger is a <summary>, which `<label for>` cannot target.
        return ""

    def __init__(  # noqa: PLR0913
        self,
        attrs: dict[str, Any] | None = None,
        choices: _Choices = (),
        *,
        show_search: bool | None = None,
        show_spinner: bool = True,
        search_key: str | None = None,
        search_params: Mapping[str, int | str] | None = None,
        search_fields: Sequence[str] | None = None,
        search_queryset: Callable[Concatenate[HttpRequest, ...], QuerySet[Any]] | None = None,
        search_decorator: Callable[..., Any] | _UnsetDecorator | None = _UNSET_DECORATOR,
        allow_clear: bool = False,
        floating: bool = False,
    ) -> None:
        if search_key is not None and search_fields:
            msg = "Pass either search_key or search_fields, not both."
            raise ImproperlyConfigured(msg)
        super().__init__(attrs=attrs, choices=choices)
        self.show_search = show_search
        self.show_spinner = show_spinner
        self.search_key = search_key
        self.search_params = dict(search_params or {})
        self.search_fields: tuple[str, ...] = tuple(search_fields) if search_fields else ()
        self.search_queryset = search_queryset
        self.search_decorator = search_decorator
        self.allow_clear = allow_clear
        self.floating = floating
        # Set per render by optgroups().
        self.truncated = False
        self.selected_past_page: list[str] = []
        # Set by FormworkForm when it registers a search for this widget.
        self._registry_key: str | None = None

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]

        # One pass: annotate each option from its ChoiceLabel and collect the
        # options to render and the selected ones for the closed toggle.
        options: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        total = 0
        for group, group_options, _index in widget["optgroups"]:
            for option in group_options:
                option.update(label_extras(option["label"]))
                # A heading row precedes the first option of each named group.
                option["group"] = group or ""
                # The empty choice (e.g. ModelChoiceField's "---------") is a row
                # only when it clears; the placeholder covers it otherwise.
                if str(option["value"]) == "":
                    if self.allow_clear:
                        options.append(option)
                    continue
                options.append(option)
                total += 1
                if option["selected"]:
                    selected.append({**option, "label": str(option["label"])})
        widget["options"] = options
        widget["selected_options"] = selected

        widget["aria_invalid"] = widget["attrs"].get("aria-invalid")
        widget["aria_required"] = widget["attrs"].get("aria-required")
        # `<label for>` cannot target the <summary>, so the label and the
        # help/error rows are associated by id instead (see boundfield.py, field.html).
        widget["aria_labelledby"] = widget["attrs"].get("aria-labelledby")
        widget["aria_label"] = widget["attrs"].get("aria-label")
        widget["aria_describedby"] = widget["attrs"].get("aria-describedby")
        widget["disabled"] = bool(widget["attrs"].get("disabled"))
        # A list that fits one page filters in the browser.
        widget["search_url"] = None
        widget["shown"] = None
        widget["more_url"] = None
        widget["truncated"] = self.truncated
        widget["show_spinner"] = self.show_spinner
        widget["show_search"] = (
            self.show_search if self.show_search is not None else total > self.search_threshold or self.truncated
        )
        if self._registry_key is not None:
            self._registered_search_context(widget, selected)
        self._floating_context(widget)
        return context

    def _registered_search_context(self, widget: dict[str, Any], selected: list[dict[str, Any]]) -> None:
        """Render the registered search's first page; the endpoint filters the rest."""
        assert self._registry_key is not None  # caller checked  # noqa: S101
        total, rows = _resolve_initial_results(self._registry_key)
        chosen = {str(option["value"]) for option in selected}
        widget["options"] = [{**row, "label_html": "", "selected": row["value"] in chosen} for row in rows]
        widget["search_url"] = reverse("formwork:search", kwargs={"key": self._registry_key})
        if self.show_search is None:
            widget["show_search"] = total is None or total > self.search_threshold

    def _floating_context(self, widget: dict[str, Any]) -> None:
        """The floating label's id, the trigger's name and its empty text."""
        widget["floating"] = self.floating
        placeholder = widget["attrs"].get("placeholder", "")
        widget["floating_label_id"] = ""
        if not self.floating:
            widget["trigger_placeholder"] = placeholder
            return
        if not placeholder:
            msg = f"{type(self).__name__}(floating=True) needs a placeholder: it is the label text."
            raise ImproperlyConfigured(msg)
        # The placeholder is the label now, so the empty trigger shows the default text.
        widget["trigger_placeholder"] = ""
        id_ = widget["attrs"].get("id")
        if id_:
            widget["floating_label_id"] = f"{id_}_floating_label"
            # `<label for>` cannot target the <summary>: name it by the floating
            # label, then by its value.
            if not widget["aria_labelledby"]:
                widget["aria_labelledby"] = f"{id_}_floating_label {id_}"


class Select(SearchableSelectMixin, forms.Select):
    """Single-select Alpine dropdown with text filtering; posts via a hidden input.

    Drop-in for a native ``<select>``: validation is unchanged.
    """

    template_name = "formwork/widgets/select.html"
    search_variant = "select"

    class Media:
        js = (_ModuleScript("formwork/widgets/select.js"),)

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        # forms.Select.format_value() wraps the value in a list; unwrap for the template.
        fmt_value = widget["value"]
        if isinstance(fmt_value, (list, tuple)):
            widget["value"] = fmt_value[0] if fmt_value else ""
        first = widget["selected_options"][0] if widget["selected_options"] else {}
        widget["selected_label"] = first.get("label", "")
        widget["selected_icon"] = first.get("icon", "")
        widget["selected_label_html"] = first.get("label_html", "")
        widget["selected_toggle_class"] = first.get("selected_toggle_class", "")
        return context
