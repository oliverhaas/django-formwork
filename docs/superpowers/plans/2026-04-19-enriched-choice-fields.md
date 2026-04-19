# Enriched Choice Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move icon/description/label callbacks from widgets to fields via `FormworkChoiceLabel`, `FormworkModelChoiceField`, and a custom metaclass.

**Architecture:** New `FormworkChoiceLabel` wraps choice labels with optional `icon`/`description`, backward-compatible via `__str__`. `FormworkModelChoiceField` overrides the choice iterator to yield `FormworkChoiceLabel`. `FormworkModelFormMetaclass` auto-swaps auto-generated `ModelChoiceField` instances. Widgets read enriched data from labels instead of maintaining their own dicts.

**Tech Stack:** Django 5.2+, Python 3.12+, pytest-django, BeautifulSoup

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `django_formwork/fields.py` | **Create** | `FormworkChoiceLabel`, `FormworkModelChoiceField`, `FormworkModelMultipleChoiceField`, custom `ModelChoiceIterator` |
| `django_formwork/forms.py` | **Modify** | `FormworkModelFormMetaclass`, update `_AutoSearchMixin._register_model_search` to read callbacks from field |
| `django_formwork/widgets/search_select.py` | **Modify** | Remove `icons`, `descriptions`, `icon_from_instance`, `description_from_instance`; read from `FormworkChoiceLabel` |
| `django_formwork/widgets/multi_select.py` | **Modify** | Remove `icons`, `icon_from_instance`, `description_from_instance`; read from `FormworkChoiceLabel` |
| `django_formwork/__init__.py` | **Modify** | Export new public API |
| `tests/test_fields.py` | **Create** | Tests for `FormworkChoiceLabel`, `FormworkModelChoiceField`, `FormworkModelMultipleChoiceField` |
| `tests/test_auto_search.py` | **Modify** | Update tests that pass `icon_from_instance` on widget to use field instead |
| `tests/widgets/test_search_select.py` | **Modify** | Update tests using `icons`/`descriptions` dicts to use `FormworkChoiceLabel` |
| `tests/widgets/test_multi_select.py` | **Modify** | Update tests using `icons` dict to use `FormworkChoiceLabel` |
| `tests/e2e/views.py` | **Modify** | Update e2e form definitions to use new API |

---

### Task 1: FormworkChoiceLabel

**Files:**
- Create: `django_formwork/fields.py`
- Create: `tests/test_fields.py`

- [ ] **Step 1: Write failing tests for FormworkChoiceLabel**

```python
# tests/test_fields.py
"""Tests for FormworkChoiceLabel, FormworkModelChoiceField, and FormworkModelMultipleChoiceField."""

from __future__ import annotations

import pytest

from django_formwork.fields import FormworkChoiceLabel


class TestFormworkChoiceLabel:
    def test_str_returns_label(self):
        label = FormworkChoiceLabel("New York", icon="building", description="East Coast")
        assert str(label) == "New York"

    def test_icon_attribute(self):
        label = FormworkChoiceLabel("New York", icon="building")
        assert label.icon == "building"

    def test_description_attribute(self):
        label = FormworkChoiceLabel("New York", description="East Coast")
        assert label.description == "East Coast"

    def test_defaults_empty_strings(self):
        label = FormworkChoiceLabel("New York")
        assert label.icon == ""
        assert label.description == ""

    def test_equality_by_str(self):
        """FormworkChoiceLabel compares equal to its string representation."""
        label = FormworkChoiceLabel("New York", icon="building")
        assert label == "New York"

    def test_repr(self):
        label = FormworkChoiceLabel("NYC", icon="building", description="East Coast")
        assert "NYC" in repr(label)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fields.py -v`
Expected: FAIL — `django_formwork/fields.py` does not exist

- [ ] **Step 3: Implement FormworkChoiceLabel**

```python
# django_formwork/fields.py
"""Enriched choice fields for django-formwork.

``FormworkChoiceLabel`` wraps a choice label with optional ``icon`` and
``description``.  ``FormworkModelChoiceField`` uses it to produce enriched
choices from a queryset via ``icon_from_instance`` and
``description_from_instance`` callbacks.
"""

from __future__ import annotations


class FormworkChoiceLabel:
    """A string-like choice label that carries optional icon and description.

    Any code expecting a plain string (Django admin, built-in widgets,
    templates) sees the label text via ``__str__``.  Widgets that understand
    ``FormworkChoiceLabel`` can read ``.icon`` and ``.description``.

    Usage::

        choices = [
            ("nyc", FormworkChoiceLabel("New York", icon="building")),
            ("ldn", FormworkChoiceLabel("London", icon="landmark")),
        ]
    """

    __slots__ = ("label", "icon", "description")

    def __init__(self, label: str, *, icon: str = "", description: str = "") -> None:
        self.label = label
        self.icon = icon
        self.description = description

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        parts = [repr(self.label)]
        if self.icon:
            parts.append(f"icon={self.icon!r}")
        if self.description:
            parts.append(f"description={self.description!r}")
        return f"FormworkChoiceLabel({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.label == other
        if isinstance(other, FormworkChoiceLabel):
            return self.label == other.label and self.icon == other.icon and self.description == other.description
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.label)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fields.py::TestFormworkChoiceLabel -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/fields.py tests/test_fields.py
git commit -m "feat: add FormworkChoiceLabel with icon and description support"
```

---

### Task 2: FormworkModelChoiceField

**Files:**
- Modify: `django_formwork/fields.py`
- Modify: `tests/test_fields.py`

- [ ] **Step 1: Write failing tests for FormworkModelChoiceField**

Append to `tests/test_fields.py`:

```python
import pytest
from django.contrib.auth.models import User

from django_formwork.fields import FormworkChoiceLabel, FormworkModelChoiceField


@pytest.mark.django_db
class TestFormworkModelChoiceField:
    @pytest.fixture(autouse=True)
    def _create_users(self):
        User.objects.create_user("alice", "alice@example.com", first_name="Alice")
        User.objects.create_user("bob", "bob@example.com", first_name="Bob")

    def test_default_label_from_instance_is_str(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        # First is empty label
        _, label = choices[1]
        assert str(label) == str(User.objects.first())

    def test_label_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            label_from_instance=lambda u: u.first_name,
        )
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "Alice" in labels
        assert "Bob" in labels

    def test_label_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def label_from_instance(self, obj):
                return f"User: {obj.username}"

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "User: alice" in labels

    def test_kwarg_overrides_method(self):
        """Kwarg takes precedence over the default method."""
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            label_from_instance=lambda u: u.first_name,
        )
        choices = list(field.choices)
        labels = [str(lbl) for _, lbl in choices if str(lbl)]
        assert "Alice" in labels

    def test_choices_yield_formwork_choice_label(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert isinstance(label, FormworkChoiceLabel)

    def test_icon_from_instance_default_empty(self):
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon == ""

    def test_icon_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            icon_from_instance=lambda u: f"avatar-{u.username}",
        )
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon.startswith("avatar-")

    def test_description_from_instance_kwarg(self):
        field = FormworkModelChoiceField(
            queryset=User.objects.all(),
            description_from_instance=lambda u: u.email,
        )
        choices = list(field.choices)
        _, label = choices[1]
        assert "@example.com" in label.description

    def test_icon_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def icon_from_instance(self, obj):
                return f"icon-{obj.pk}"

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert label.icon.startswith("icon-")

    def test_description_from_instance_method_override(self):
        class MyField(FormworkModelChoiceField):
            def description_from_instance(self, obj):
                return obj.email

        field = MyField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[1]
        assert "@example.com" in label.description

    def test_empty_label_is_plain_string(self):
        """The empty label (first choice) is a regular string, not FormworkChoiceLabel."""
        field = FormworkModelChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        val, label = choices[0]
        assert val == ""
        assert not isinstance(label, FormworkChoiceLabel)

    def test_from_field_copies_standard_field(self):
        """from_field creates a FormworkModelChoiceField from a standard ModelChoiceField."""
        from django.forms import ModelChoiceField

        original = ModelChoiceField(queryset=User.objects.all(), required=False, empty_label="Pick one")
        converted = FormworkModelChoiceField.from_field(original)
        assert isinstance(converted, FormworkModelChoiceField)
        assert converted.queryset.model is User
        assert converted.required is False
        assert converted.empty_label == "Pick one"
        assert converted.widget.__class__ == original.widget.__class__
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fields.py::TestFormworkModelChoiceField -v`
Expected: FAIL — `FormworkModelChoiceField` not defined

- [ ] **Step 3: Implement FormworkModelChoiceField**

Append to `django_formwork/fields.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.forms.models import ModelChoiceIterator

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import Model


class FormworkModelChoiceIterator(ModelChoiceIterator):
    """Choice iterator that yields ``FormworkChoiceLabel`` instead of plain strings."""

    def choice(self, obj: Model) -> tuple:
        value = self.field.prepare_value(obj)
        label = FormworkChoiceLabel(
            self.field.label_from_instance(obj),
            icon=self.field.icon_from_instance(obj),
            description=self.field.description_from_instance(obj),
        )
        from django.forms.models import ModelChoiceIteratorValue

        return (ModelChoiceIteratorValue(value, obj), label)


class FormworkModelChoiceField(ModelChoiceField):
    """ModelChoiceField with ``icon_from_instance`` and ``description_from_instance``.

    All three callbacks (``label_from_instance``, ``icon_from_instance``,
    ``description_from_instance``) work as both constructor kwargs and
    overridable methods.
    """

    iterator = FormworkModelChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[assignment]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[assignment]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[assignment]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:
        return ""

    def description_from_instance(self, obj: Model) -> str:
        return ""

    @classmethod
    def from_field(cls, field: ModelChoiceField) -> FormworkModelChoiceField:
        """Create a FormworkModelChoiceField from an existing ModelChoiceField."""
        new_field = cls(
            queryset=field.queryset,
            empty_label=field.empty_label,
            required=field.required,
            widget=field.widget,
            label=field.label,
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        return new_field
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/fields.py tests/test_fields.py
git commit -m "feat: add FormworkModelChoiceField with enriched choice labels"
```

---

### Task 3: FormworkModelMultipleChoiceField

**Files:**
- Modify: `django_formwork/fields.py`
- Modify: `tests/test_fields.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_fields.py`:

```python
from django_formwork.fields import FormworkModelMultipleChoiceField


@pytest.mark.django_db
class TestFormworkModelMultipleChoiceField:
    @pytest.fixture(autouse=True)
    def _create_users(self):
        User.objects.create_user("alice", "alice@example.com", first_name="Alice")
        User.objects.create_user("bob", "bob@example.com", first_name="Bob")

    def test_choices_yield_formwork_choice_label(self):
        field = FormworkModelMultipleChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        _, label = choices[0]
        assert isinstance(label, FormworkChoiceLabel)

    def test_icon_from_instance_kwarg(self):
        field = FormworkModelMultipleChoiceField(
            queryset=User.objects.all(),
            icon_from_instance=lambda u: f"avatar-{u.username}",
        )
        choices = list(field.choices)
        _, label = choices[0]
        assert label.icon.startswith("avatar-")

    def test_no_empty_label(self):
        """Multiple choice fields have no empty label."""
        field = FormworkModelMultipleChoiceField(queryset=User.objects.all())
        choices = list(field.choices)
        assert len(choices) == 2  # No empty option

    def test_from_field_copies_standard_field(self):
        from django.forms import ModelMultipleChoiceField

        original = ModelMultipleChoiceField(queryset=User.objects.all(), required=False)
        converted = FormworkModelMultipleChoiceField.from_field(original)
        assert isinstance(converted, FormworkModelMultipleChoiceField)
        assert converted.queryset.model is User
        assert converted.required is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fields.py::TestFormworkModelMultipleChoiceField -v`
Expected: FAIL — `FormworkModelMultipleChoiceField` not defined

- [ ] **Step 3: Implement FormworkModelMultipleChoiceField**

Append to `django_formwork/fields.py`:

```python
class FormworkModelMultipleChoiceField(ModelMultipleChoiceField):
    """ModelMultipleChoiceField with enriched choice labels."""

    iterator = FormworkModelChoiceIterator

    def __init__(
        self,
        *args: Any,
        label_from_instance: Callable[..., str] | None = None,
        icon_from_instance: Callable[..., str] | None = None,
        description_from_instance: Callable[..., str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if label_from_instance is not None:
            self.label_from_instance = label_from_instance  # type: ignore[assignment]
        if icon_from_instance is not None:
            self.icon_from_instance = icon_from_instance  # type: ignore[assignment]
        if description_from_instance is not None:
            self.description_from_instance = description_from_instance  # type: ignore[assignment]

    def label_from_instance(self, obj: Model) -> str:
        return str(obj)

    def icon_from_instance(self, obj: Model) -> str:
        return ""

    def description_from_instance(self, obj: Model) -> str:
        return ""

    @classmethod
    def from_field(cls, field: ModelMultipleChoiceField) -> FormworkModelMultipleChoiceField:
        """Create a FormworkModelMultipleChoiceField from an existing ModelMultipleChoiceField."""
        new_field = cls(
            queryset=field.queryset,
            required=field.required,
            widget=field.widget,
            label=field.label,
            help_text=field.help_text,
            to_field_name=getattr(field, "to_field_name", None),
        )
        new_field.error_messages = field.error_messages
        new_field.validators = field.validators
        return new_field
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/fields.py tests/test_fields.py
git commit -m "feat: add FormworkModelMultipleChoiceField"
```

---

### Task 4: FormworkModelFormMetaclass

**Files:**
- Modify: `django_formwork/forms.py`
- Modify: `tests/test_fields.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_fields.py`:

```python
from django.contrib.auth.models import Group


@pytest.mark.django_db
class TestFormworkModelFormMetaclass:
    def test_auto_swaps_model_choice_field(self):
        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)

    def test_preserves_explicit_formwork_field(self):
        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            groups = FormworkModelMultipleChoiceField(
                queryset=Group.objects.all(),
                icon_from_instance=lambda g: f"icon-{g.name}",
            )

            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)
        # Verify the custom icon callback survived
        Group.objects.create(name="editors")
        choices = list(field.choices)
        _, label = choices[0]
        assert label.icon == "icon-editors"

    def test_preserves_other_subclass(self):
        """A custom ModelChoiceField subclass (not ours) is left untouched."""
        from django.forms import ModelMultipleChoiceField

        from django_formwork.forms import FormworkModelForm

        class CustomField(ModelMultipleChoiceField):
            pass

        class F(FormworkModelForm):
            groups = CustomField(queryset=Group.objects.all())

            class Meta:
                model = User
                fields = ["groups"]

        field = F.base_fields["groups"]
        assert type(field) is CustomField

    def test_preserves_widget(self):
        """The original widget from Meta.widgets is preserved after the swap."""
        from django_formwork.forms import FormworkModelForm
        from django_formwork.widgets import MultiSelect

        class F(FormworkModelForm):
            class Meta:
                model = User
                fields = ["groups"]
                widgets = {"groups": MultiSelect()}

        field = F.base_fields["groups"]
        assert isinstance(field, FormworkModelMultipleChoiceField)
        assert isinstance(field.widget, MultiSelect)

    def test_non_model_fields_untouched(self):
        """Regular CharField, etc. are not affected by the metaclass."""
        from django import forms

        from django_formwork.forms import FormworkModelForm

        class F(FormworkModelForm):
            extra = forms.CharField()

            class Meta:
                model = User
                fields = ["groups"]

        assert type(F.base_fields["extra"]) is forms.CharField
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fields.py::TestFormworkModelFormMetaclass -v`
Expected: FAIL — no metaclass swap happening

- [ ] **Step 3: Implement FormworkModelFormMetaclass**

In `django_formwork/forms.py`, add the metaclass and update `FormworkModelForm`:

```python
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.forms.models import ModelFormMetaclass

from django_formwork.fields import FormworkModelChoiceField, FormworkModelMultipleChoiceField


class FormworkModelFormMetaclass(ModelFormMetaclass):
    """Metaclass that auto-upgrades ModelChoiceField to FormworkModelChoiceField."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if not hasattr(cls, "base_fields"):
            return cls
        for field_name, field in cls.base_fields.items():
            if type(field) is ModelChoiceField:
                cls.base_fields[field_name] = FormworkModelChoiceField.from_field(field)
            elif type(field) is ModelMultipleChoiceField:
                cls.base_fields[field_name] = FormworkModelMultipleChoiceField.from_field(field)
        return cls
```

Update `FormworkModelForm` and `FormworkJinja2ModelForm` to use the new metaclass:

```python
class FormworkModelForm(AsyncModelFormMixin, _AutoSearchMixin, ModelForm, metaclass=FormworkModelFormMetaclass):
    ...

class FormworkJinja2ModelForm(AsyncModelFormMixin, _AutoSearchMixin, ModelForm, metaclass=FormworkModelFormMetaclass):
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/forms.py tests/test_fields.py
git commit -m "feat: add FormworkModelFormMetaclass for auto-upgrading choice fields"
```

---

### Task 5: Update SearchSelect to read from FormworkChoiceLabel

**Files:**
- Modify: `django_formwork/widgets/search_select.py`
- Modify: `tests/widgets/test_search_select.py`

- [ ] **Step 1: Update tests that use `icons`/`descriptions` dicts**

In `tests/widgets/test_search_select.py`, update `test_search_select_get_context_optgroups_with_icons` to use `FormworkChoiceLabel`:

```python
from django_formwork.fields import FormworkChoiceLabel

@pytest.mark.unit
def test_search_select_get_context_optgroups_with_icons():
    """Icons from FormworkChoiceLabel are injected into optgroups."""
    widget = SearchSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>"))),
            ("b", "Beta"),
        ],
    )
    ctx = widget.get_context("test", "", {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["icon"] == "<svg>icon</svg>"
            else:
                assert option["icon"] == ""
```

Update `test_search_select_icons_default_empty` and `test_search_select_icons_stored` — these test the `icons` kwarg which is being removed. Replace with:

```python
@pytest.mark.unit
def test_search_select_no_icons_kwarg():
    """SearchSelect no longer accepts an icons kwarg."""
    with pytest.raises(TypeError):
        SearchSelect(choices=[("a", "Alpha")], icons={"a": "icon"})
```

Update `test_search_select_icon_rendered_in_option` and `test_search_select_no_icon_element_when_not_provided`:

```python
@pytest.mark.unit
def test_search_select_icon_rendered_in_option():
    """FormworkChoiceLabel icons appear in the rendered option buttons."""
    widget = SearchSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_search_select_no_icon_element_when_not_provided():
    """No <img> elements rendered when no icons in FormworkChoiceLabel."""
    widget = SearchSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/widgets/test_search_select.py -m unit -v`
Expected: FAIL — widget still expects `icons` kwarg

- [ ] **Step 3: Update SearchSelect widget**

In `django_formwork/widgets/search_select.py`, remove `icons`, `descriptions`, `icon_from_instance`, `description_from_instance` from `__init__` and update `get_context`:

```python
class SearchSelect(forms.Select):
    template_name = "formwork/widgets/search_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | object = _NOT_SET,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self._registry_key: str | None = None

    def get_context(self, name: str, value: str | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        from django_formwork.fields import FormworkChoiceLabel

        context = super().get_context(name, value, attrs)
        fmt_value = context["widget"]["value"]
        if isinstance(fmt_value, (list, tuple)):
            context["widget"]["value"] = fmt_value[0] if fmt_value else ""
        selected_label = ""
        selected_icon = ""
        total = 0
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                label = option["label"]
                if isinstance(label, FormworkChoiceLabel):
                    option["icon"] = label.icon
                    option["description"] = label.description
                else:
                    option["icon"] = ""
                    option["description"] = ""
                if option["selected"]:
                    selected_label = str(option["label"])
                    selected_icon = option["icon"]
                total += 1
        context["widget"]["selected_label"] = selected_label
        context["widget"]["selected_icon"] = selected_icon
        context["widget"]["aria_invalid"] = context["widget"]["attrs"].get("aria-invalid")
        search_url = self.search_url
        if not search_url and self._registry_key:
            from django.urls import reverse
            search_url = reverse("formwork:search", kwargs={"key": self._registry_key})
        context["widget"]["search_url"] = search_url
        context["widget"]["search_threshold"] = self.search_threshold
        if self.show_search is not None:
            context["widget"]["show_search"] = self.show_search
        elif search_url:
            context["widget"]["show_search"] = False
        else:
            context["widget"]["show_search"] = total >= self.search_threshold
        return context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/widgets/test_search_select.py -m unit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/widgets/search_select.py tests/widgets/test_search_select.py
git commit -m "refactor: SearchSelect reads icons/descriptions from FormworkChoiceLabel"
```

---

### Task 6: Update MultiSelect to read from FormworkChoiceLabel

**Files:**
- Modify: `django_formwork/widgets/multi_select.py`
- Modify: `tests/widgets/test_multi_select.py`

- [ ] **Step 1: Update tests that use `icons` dict**

In `tests/widgets/test_multi_select.py`, update `test_multi_select_get_context_icon_populated`:

```python
from django_formwork.fields import FormworkChoiceLabel

@pytest.mark.unit
def test_multi_select_get_context_icon_populated():
    """FormworkChoiceLabel icons are reflected in option['icon']."""
    widget = MultiSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe("<svg>icon</svg>"))),
            ("b", "Beta"),
        ],
    )
    ctx = widget.get_context("test", [], {})
    for _group, options, _index in ctx["widget"]["optgroups"]:
        for option in options:
            if option["value"] == "a":
                assert option["icon"] == "<svg>icon</svg>"
            else:
                assert option["icon"] == ""
```

Update `test_multi_select_icons_rendered` and `test_multi_select_no_icon_when_not_provided`:

```python
@pytest.mark.unit
def test_multi_select_icons_rendered():
    """FormworkChoiceLabel icons appear in the rendered HTML."""
    widget = MultiSelect(
        choices=[
            ("a", FormworkChoiceLabel("Alpha", icon=mark_safe('<img src="a.svg">'))),
            ("b", "Beta"),
        ],
    )
    soup = render_widget(widget, name="test")
    icon = soup.find("img", {"src": "a.svg"})
    assert icon is not None


@pytest.mark.unit
def test_multi_select_no_icon_when_not_provided():
    """No <img> elements rendered when no FormworkChoiceLabel icons."""
    widget = MultiSelect(choices=[("a", "Alpha")])
    soup = render_widget(widget, name="test")
    icons = soup.find_all("img")
    assert len(icons) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/widgets/test_multi_select.py -m unit -v`
Expected: FAIL — widget still uses `icons` dict

- [ ] **Step 3: Update MultiSelect widget**

In `django_formwork/widgets/multi_select.py`, remove `icons`, `icon_from_instance`, `description_from_instance` from `__init__` and update `get_context`:

```python
class MultiSelect(forms.SelectMultiple):
    template_name = "formwork/widgets/multi_select.html"
    option_inherits_attrs = False
    search_threshold = 20

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        choices: tuple = (),
        *,
        search_url: str | None = None,
        show_search: bool | None = None,
        search_fields: Sequence[str] | None = None,
        search_decorator: Callable | object = _NOT_SET,
    ) -> None:
        super().__init__(attrs=attrs, choices=choices)
        self.search_url = search_url
        self.show_search = show_search
        self.search_fields = tuple(search_fields) if search_fields else None
        self.search_decorator = search_decorator
        self._registry_key: str | None = None

    def get_context(self, name: str, value: list[str] | None, attrs: dict[str, Any] | None) -> dict[str, Any]:
        from django_formwork.fields import FormworkChoiceLabel

        context = super().get_context(name, value, attrs)
        total = sum(len(options) for _, options, _ in context["widget"]["optgroups"])
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
        # Read icon from FormworkChoiceLabel.
        for _group, options, _index in context["widget"]["optgroups"]:
            for option in options:
                label = option["label"]
                if isinstance(label, FormworkChoiceLabel):
                    option["icon"] = label.icon
                else:
                    option["icon"] = ""
        if search_url:
            selected_values = set(value or [])
            initial_selected = [
                [str(option["value"]), [str(option["label"]), option.get("icon", "")]]
                for _group, options, _index in context["widget"]["optgroups"]
                for option in options
                if str(option["value"]) in selected_values
            ]
            context["widget"]["initial_selected_json"] = json.dumps(initial_selected)
        return context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/widgets/test_multi_select.py -m unit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/widgets/multi_select.py tests/widgets/test_multi_select.py
git commit -m "refactor: MultiSelect reads icons from FormworkChoiceLabel"
```

---

### Task 7: Update _AutoSearchMixin to read callbacks from field

**Files:**
- Modify: `django_formwork/forms.py`
- Modify: `tests/test_auto_search.py`

- [ ] **Step 1: Update tests**

In `tests/test_auto_search.py`, update `test_captures_icon_from_instance` to put the callback on the field instead of the widget:

```python
def test_captures_icon_from_instance(self):
    from django import forms

    from django_formwork.fields import FormworkModelChoiceField
    from django_formwork.forms import FormworkForm
    from django_formwork.widgets import SearchSelect

    def my_icon(obj):
        return f"<img src='{obj.pk}.png'>"

    class F(FormworkForm):
        user = FormworkModelChoiceField(
            queryset=User.objects.all(),
            icon_from_instance=my_icon,
            widget=SearchSelect(search_fields=["username"], search_decorator=None),
        )

    F()
    reg = get_registration(make_key("auth.user", ["username"]))
    assert reg.icon_from_instance is not None
```

Also update `test_captures_label_from_instance` to use kwarg:

```python
def test_captures_label_from_instance(self):
    from django import forms

    from django_formwork.fields import FormworkModelChoiceField
    from django_formwork.forms import FormworkForm
    from django_formwork.widgets import SearchSelect

    class F(FormworkForm):
        user = FormworkModelChoiceField(
            queryset=User.objects.all(),
            label_from_instance=lambda obj: f"User: {obj.username}",
            widget=SearchSelect(search_fields=["username"], search_decorator=None),
        )

    F()
    reg = get_registration(make_key("auth.user", ["username"]))
    assert reg.label_from_instance is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auto_search.py -v`
Expected: FAIL — `_register_model_search` still reads from widget

- [ ] **Step 3: Update `_register_model_search` in forms.py**

In `django_formwork/forms.py`, update `_register_model_search` to read callbacks from the field:

```python
@staticmethod
def _register_model_search(
    widget: SearchSelect | MultiSelect | ComboBox,
    field: Field,
    search_fields: tuple[str, ...],
    queryset: QuerySet,
) -> None:
    from django_formwork.fields import FormworkModelChoiceField, FormworkModelMultipleChoiceField
    from django_formwork.registry import SearchRegistration, make_key, register
    from django_formwork.widgets import MultiSelect

    model_label = queryset.model._meta.label_lower  # noqa: SLF001
    to_field_name = getattr(field, "to_field_name", None) or "pk"
    key = make_key(model_label, search_fields, to_field_name)

    widget_type = "multiselect" if isinstance(widget, MultiSelect) else "search_select"

    # Read callbacks from field (FormworkModelChoiceField) if available,
    # fall back to field's label_from_instance for label.
    label_func = getattr(field, "label_from_instance", None)
    icon_func = None
    desc_func = None
    if isinstance(field, (FormworkModelChoiceField, FormworkModelMultipleChoiceField)):
        icon_func = field.icon_from_instance
        desc_func = field.description_from_instance

    base_qs = queryset

    registration = SearchRegistration(
        queryset_factory=lambda qs=base_qs: qs.all(),  # type: ignore[misc]
        search_fields=tuple(search_fields),
        to_field_name=to_field_name,
        label_from_instance=label_func,
        icon_from_instance=icon_func,
        description_from_instance=desc_func,
        search_decorator=widget.search_decorator if callable(widget.search_decorator) else None,
        widget_type=widget_type,
    )
    register(key, registration)
    widget._registry_key = key  # noqa: SLF001
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auto_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add django_formwork/forms.py tests/test_auto_search.py
git commit -m "refactor: _AutoSearchMixin reads callbacks from field instead of widget"
```

---

### Task 8: Update exports and public API

**Files:**
- Modify: `django_formwork/__init__.py`

- [ ] **Step 1: Add exports to `__init__.py`**

```python
from django_formwork.fields import (
    FormworkChoiceLabel,
    FormworkModelChoiceField,
    FormworkModelMultipleChoiceField,
)
```

Add to `__all__`:

```python
__all__ = [
    ...,
    "FormworkChoiceLabel",
    "FormworkModelChoiceField",
    "FormworkModelMultipleChoiceField",
]
```

- [ ] **Step 2: Verify imports work**

Run: `uv run python -c "from django_formwork import FormworkChoiceLabel, FormworkModelChoiceField, FormworkModelMultipleChoiceField; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add django_formwork/__init__.py
git commit -m "feat: export FormworkChoiceLabel and enriched choice fields"
```

---

### Task 9: Update e2e views to use new API

**Files:**
- Modify: `tests/e2e/views.py`

- [ ] **Step 1: Update e2e form definitions**

In `tests/e2e/views.py`, update forms that use `icons`/`descriptions` dicts on SearchSelect and MultiSelect to use `FormworkChoiceLabel` in their choices instead. For example, `SearchSelectForm.city_icons`:

```python
from django_formwork.fields import FormworkChoiceLabel

# Before:
city_icons = forms.ChoiceField(
    choices=[("nyc", "New York"), ...],
    widget=SearchSelect(
        icons={"nyc": mark_safe("🏙️"), ...},
        descriptions={"nyc": "USA", ...},
    ),
)

# After:
city_icons = forms.ChoiceField(
    choices=[
        ("nyc", FormworkChoiceLabel("New York", icon=mark_safe("🏙️"), description="USA")),
        ...
    ],
    widget=SearchSelect(),
)
```

Apply the same pattern to all SearchSelect and MultiSelect instances in the e2e views that use `icons`/`descriptions`/`icon_from_instance`/`description_from_instance` kwargs. Leave ComboBox instances unchanged.

- [ ] **Step 2: Run unit tests**

Run: `uv run pytest tests/ -m "not e2e and not screenshot" -v`
Expected: PASS

- [ ] **Step 3: Run e2e tests**

Run: `uv run pytest tests/ -m e2e -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/views.py
git commit -m "refactor: e2e views use FormworkChoiceLabel instead of widget icon dicts"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `uv run ruff check django_formwork/ tests/`
Expected: No errors

- [ ] **Step 3: Run type checking**

Run: `uv run mypy django_formwork/`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 4: Manual verification**

Start the e2e dev server and verify SearchSelect/MultiSelect with icons still render correctly:

```bash
PYTHONPATH=tests uv run django-admin runserver --settings=e2e.settings
```

Visit `/search-select/` and `/multi-select/` pages. Verify:
- Icons render in dropdown options
- Descriptions render in SearchSelect options
- Search filtering works
- Selecting an option shows the label in the summary

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -u
git commit -m "fix: address review findings from enriched choice fields"
```
