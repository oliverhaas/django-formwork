# Enriched Choice Fields

## Context

SearchSelect, MultiSelect, and ComboBox support icons and descriptions alongside choice labels. Currently this data is passed as dicts on the **widget** (`icons={"val": "icon"}`, `descriptions={"val": "desc"}`), and `icon_from_instance` / `description_from_instance` callbacks also live on the widget — but only work in the server-side search view, not the initial render.

This creates two problems:

1. **Layer violation** — "what icon does this City have?" is a data concern (field), not a rendering concern (widget).
2. **Broken initial render** — `_from_instance` callbacks on the widget are never called during `get_context()` because Django's `ModelChoiceField` has already flattened instances to `(value, label)` tuples. They only work server-side.

Additionally, Django's `ModelChoiceField.label_from_instance` requires subclassing the field to override — there's no kwarg shortcut.

## Design

### FormworkChoiceLabel

A string-like object that carries optional `icon` and `description` alongside the display text.

```python
class FormworkChoiceLabel:
    def __init__(self, label: str, *, icon: str = "", description: str = ""):
        self.label = label
        self.icon = icon
        self.description = description

    def __str__(self) -> str:
        return self.label
```

`__str__` returns the plain label, so any code expecting a string (Django's built-in widgets, admin, templates) works unchanged. Widgets that understand `FormworkChoiceLabel` can access `.icon` and `.description`.

### FormworkModelChoiceField

Subclass of `ModelChoiceField`. Adds `icon_from_instance` and `description_from_instance` as both overridable methods and constructor kwargs (kwargs take precedence, matching how Django's own `label_from_instance` works as a method).

```python
class FormworkModelChoiceField(ModelChoiceField):
    def __init__(self, *args,
                 label_from_instance=None,
                 icon_from_instance=None,
                 description_from_instance=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        if label_from_instance:
            self.label_from_instance = label_from_instance
        if icon_from_instance:
            self.icon_from_instance = icon_from_instance
        if description_from_instance:
            self.description_from_instance = description_from_instance

    def label_from_instance(self, obj):
        return str(obj)

    def icon_from_instance(self, obj):
        return ""

    def description_from_instance(self, obj):
        return ""
```

The choice iterator yields `(value, FormworkChoiceLabel(...))` instead of `(value, str)`. This is the single integration point — widgets read the enriched label from the normal choices flow.

### FormworkModelMultipleChoiceField

Same pattern, subclassing `ModelMultipleChoiceField`. Shares the same `FormworkChoiceLabel` mechanism and `_from_instance` callbacks.

### FormworkModelFormMetaclass

Subclass of `ModelFormMetaclass`. After the parent metaclass generates fields, it swaps auto-generated `ModelChoiceField` → `FormworkModelChoiceField` (and `ModelMultipleChoiceField` → `FormworkModelMultipleChoiceField`).

Uses exact type check (`type(field) is ModelChoiceField`), so explicitly declared subclasses (including `FormworkModelChoiceField` itself) are not touched.

```python
class FormworkModelFormMetaclass(ModelFormMetaclass):
    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        for field_name, field in cls.base_fields.items():
            if type(field) is ModelChoiceField:
                cls.base_fields[field_name] = FormworkModelChoiceField.from_field(field)
            elif type(field) is ModelMultipleChoiceField:
                cls.base_fields[field_name] = FormworkModelMultipleChoiceField.from_field(field)
        return cls
```

`FormworkModelForm` uses this metaclass.

### Widget changes

SearchSelect and MultiSelect read `icon` and `description` from `FormworkChoiceLabel` in `get_context()`:

```python
# In get_context(), when iterating optgroups:
for _group, options, _index in context["widget"]["optgroups"]:
    for option in options:
        label = option["label"]
        if isinstance(label, FormworkChoiceLabel):
            option["icon"] = label.icon
            option["description"] = label.description
        else:
            option["icon"] = ""
            option["description"] = ""
```

Remove from SearchSelect and MultiSelect widget constructors:
- `icons` dict
- `descriptions` dict (SearchSelect only — MultiSelect doesn't have it)
- `icon_from_instance` callback
- `description_from_instance` callback

These are now field concerns, not widget concerns.

ComboBox is unaffected — it extends `TextInput`, uses `suggestions` (plain strings), and is not backed by `ModelChoiceField`. Its `icons` and `descriptions` dicts remain on the widget.

### Server-side search

`_AutoSearchMixin._register_model_search` currently reads `icon_from_instance` / `description_from_instance` from the widget and passes them to `SearchRegistration`. After this change, it reads them from the **field** instead (since `FormworkModelChoiceField` has these methods).

The search view (`FormworkAutoSearchView`) continues to call the callbacks the same way — the only change is where `SearchRegistration` gets them from.

### Usage

**Simple — auto-generated field, no customization:**
```python
class TaskForm(FormworkModelForm):
    class Meta:
        model = Task
        fields = ["assignee"]
        widgets = {"assignee": SearchSelect()}
```

**Customized — explicit field with kwargs:**
```python
class TaskForm(FormworkModelForm):
    assignee = FormworkModelChoiceField(
        queryset=User.objects.all(),
        label_from_instance=lambda u: u.get_full_name(),
        icon_from_instance=lambda u: u.avatar_icon,
        description_from_instance=lambda u: u.department,
        widget=SearchSelect(),
    )
```

**Customized — subclass for complex logic:**
```python
class UserChoiceField(FormworkModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name()

    def icon_from_instance(self, obj):
        return f"flag-{obj.country_code}"

    def description_from_instance(self, obj):
        return f"{obj.department} — {obj.title}"
```

## Breaking changes

This is an alpha API change. The following widget kwargs are removed:
- `SearchSelect`: `icons`, `descriptions`, `icon_from_instance`, `description_from_instance`
- `MultiSelect`: `icons`, `icon_from_instance`, `description_from_instance`

ComboBox is not affected (it uses `suggestions`, not model-backed choices).

Users currently passing these kwargs need to move the data to `FormworkModelChoiceField` (for model-backed fields) or build `FormworkChoiceLabel` objects in their choices (for static choices).

Static choices with icons/descriptions:
```python
# Before:
city = forms.ChoiceField(
    choices=[("nyc", "New York"), ("ldn", "London")],
    widget=SearchSelect(icons={"nyc": "building", "ldn": "landmark"}),
)

# After:
city = forms.ChoiceField(
    choices=[
        ("nyc", FormworkChoiceLabel("New York", icon="building")),
        ("ldn", FormworkChoiceLabel("London", icon="landmark")),
    ],
    widget=SearchSelect(),
)
```

## Testing

- Unit tests for `FormworkChoiceLabel.__str__`, attribute access
- Unit tests for `FormworkModelChoiceField` with all three callbacks (kwargs and method override)
- Unit tests for `FormworkModelFormMetaclass` auto-swapping
- Unit tests for widget `get_context()` reading `FormworkChoiceLabel` data
- Existing e2e tests updated to use new API
- Verify admin is unaffected (admin uses `ModelChoiceField` directly, never `FormworkModelChoiceField`)
