"""Single-select dropdown widget, the shared select mixin and ``ChoiceLabel``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, Literal
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms.models import ModelChoiceIterator
from django.utils.choices import flatten_choices
from django.utils.formats import number_format

from django_formwork.search import SEARCH_PAGE_SIZE, check_search_params, search_url

from ._base import _ModuleScript

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

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

# Attrs the select templates place themselves.
_TEMPLATE_ATTRS = frozenset(
    {
        "id",
        "class",
        "placeholder",
        "disabled",
        "aria-invalid",
        "aria-required",
        "aria-labelledby",
        "aria-label",
        "aria-describedby",
    }
)

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

    def use_required_attribute(self, initial: object) -> bool:  # noqa: ARG002
        # No control renders `required` (the trigger gets aria-required), and
        # forms.Select would read the first choice for it: a query on a model field.
        return False

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
        search_ranked: bool = False,
        allow_clear: bool = False,
        floating: bool = False,
        counts: Mapping[Any, int] | None = None,
    ) -> None:
        if search_key is not None and search_fields:
            msg = "Pass either search_key or search_fields, not both."
            raise ImproperlyConfigured(msg)
        super().__init__(attrs=attrs, choices=choices)
        self.show_search = show_search
        self.show_spinner = show_spinner
        self.search_key = search_key
        self.search_params = dict(search_params or {})
        # A wrong key or param set fails where the widget is built, not on first render.
        if search_key is not None:
            check_search_params(search_key, self.search_params)
        self.search_fields: tuple[str, ...] = tuple(search_fields) if search_fields else ()
        self.search_queryset = search_queryset
        self.search_decorator = search_decorator
        self.search_ranked = search_ranked
        self.allow_clear = allow_clear
        self.floating = floating
        self.counts = counts
        # Set per render by optgroups().
        self.truncated = False
        self.selected_past_page: list[str] = []

    def get_context(self, name: str, value: object, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget = context["widget"]

        # One pass: annotate each option from its ChoiceLabel and collect the
        # options to render and the selected ones for the closed toggle.
        options: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        total = 0
        # The server's pages of a long list carry no counts, so the first page shows none either.
        counts = None
        if self.counts is not None and not self.truncated:
            counts = {str(key): count for key, count in self.counts.items()}
        for group, group_options, _index in widget["optgroups"]:
            for option in group_options:
                option.update(label_extras(option["label"]))
                if counts is not None and str(option["value"]) != "":
                    count = counts.get(str(option["value"]), 0)
                    option["count"] = number_format(count, force_grouping=True)
                    option["count_zero"] = not count
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
        # The hidden input holds the value and fires `change` on a pick. Data and
        # htmx attrs go there, the rest go on the trigger, which takes focus.
        rest = {key: val for key, val in widget["attrs"].items() if key not in _TEMPLATE_ATTRS}
        if widget["disabled"]:
            rest.pop("tabindex", None)
        widget["input_attrs"] = {key: val for key, val in rest.items() if key.startswith(("data-", "hx-"))}
        widget["trigger_attrs"] = {key: val for key, val in rest.items() if key not in widget["input_attrs"]}
        # A list that fits one page filters in the browser.
        widget["search_url"] = None
        widget["shown"] = None
        widget["more_url"] = None
        if self.truncated and self.search_key is not None:
            widget["search_url"] = search_url(
                self.search_key,
                self.search_params,
                widget=self.search_variant,
                allow_clear=self.allow_clear,
            )
            widget["shown"] = SEARCH_PAGE_SIZE
            more = {"offset": SEARCH_PAGE_SIZE, "exclude": self.selected_past_page}
            widget["more_url"] = f"{widget['search_url']}&{urlencode(more, doseq=True)}"
        widget["truncated"] = self.truncated
        widget["show_spinner"] = self.show_spinner
        widget["show_search"] = (
            self.show_search if self.show_search is not None else total > self.search_threshold or self.truncated
        )
        self._floating_context(widget)
        return context

    def optgroups(
        self, name: str, value: list[str], attrs: dict[str, Any] | None = None
    ) -> list[tuple[str | None, list[dict[str, Any]], int | None]]:
        """Every choice without a server search, else one page plus the selected ones."""
        if self.search_key is None:
            return super().optgroups(name, value, attrs)
        chosen = {str(subvalue) for subvalue in value if subvalue}
        limit = SEARCH_PAGE_SIZE
        choices = self.choices
        blank: list[tuple[Any, Any]] = []
        if isinstance(choices, ModelChoiceIterator):
            if choices.field.empty_label is not None:
                blank.append(("", choices.field.empty_label))
            key = choices.field.to_field_name or "pk"
            # One extra row tells whether more exist, so no COUNT runs.
            page = list(choices.queryset[: limit + 1])
            shown = {str(getattr(obj, key)) for obj in page[:limit]}
            # One value the key column cannot hold must not drop the others.
            # filter() converts it without a query, as ModelMultipleChoiceField checks.
            wanted = []
            for subvalue in chosen - shown:
                try:
                    choices.queryset.filter(**{key: subvalue})
                except ValueError, TypeError, ValidationError:
                    continue
                wanted.append(subvalue)
            rest = list(choices.queryset.filter(**{f"{key}__in": wanted}))
            self.selected_past_page = [str(getattr(obj, key)) for obj in rest]
            pairs = [*blank, *(choices.choice(obj) for obj in [*page[:limit], *rest])]
        else:
            flat: Iterator[tuple[Any, Any]] = flatten_choices(choices)
            every: list[tuple[Any, Any]] = []
            for pair in flat:
                (every if str(pair[0]) else blank).append(pair)
            page = every[: limit + 1]
            beyond = [pair for pair in every[limit:] if str(pair[0]) in chosen]
            self.selected_past_page = [str(pair[0]) for pair in beyond]
            pairs = [*blank, *every[:limit], *beyond]
        # The endpoint caps its rows the same way, so the hint reads the same.
        self.truncated = len(page) > limit
        options = [
            self.create_option(name, choice, label, str(choice) in chosen, index, attrs=attrs)
            for index, (choice, label) in enumerate(pairs)
        ]
        return [(None, options, 0)] if options else []

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
        # The placeholder text is the label, so an empty trigger shows the default text.
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
        # A value no option holds (a deleted row, an edited post) shows the
        # placeholder, so it must not post again. Empty choices can't tell.
        if not first and (widget["options"] or isinstance(self.choices, ModelChoiceIterator)):
            widget["value"] = ""
        widget["selected_label"] = first.get("label", "")
        widget["selected_icon"] = first.get("icon", "")
        widget["selected_label_html"] = first.get("label_html", "")
        widget["selected_toggle_class"] = first.get("selected_toggle_class", "")
        return context
