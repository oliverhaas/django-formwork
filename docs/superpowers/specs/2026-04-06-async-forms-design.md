# Async Form Support

## Problem

Django 6.0 has no async form methods. Async views must wrap `form.is_valid()` and `form.save()` with `sync_to_async`, and ORM queries in `clean()` methods raise `SynchronousOnlyOperation`.

## Solution

Two mixins in `django_formwork/async_forms.py`:

- `AsyncFormMixin` — async validation (`ais_valid`, `afull_clean`)
- `AsyncModelFormMixin(AsyncFormMixin)` — adds async save (`asave`)

Mixed into `FormworkForm` and `FormworkModelForm`. Also exported standalone for use with plain Django forms.

## API

### AsyncFormMixin

```python
class AsyncFormMixin:
    async def ais_valid(self) -> bool
    async def afull_clean(self) -> None
    async def _aclean_fields(self) -> None
    async def _aclean_form(self) -> None
```

- `ais_valid()`: checks `is_bound`, calls `await afull_clean()`, returns `not self.errors`. Does not trigger the `errors` property — sets `self._errors` directly via `afull_clean`.
- `afull_clean()`: mirrors `full_clean()` — initializes `_errors`/`cleaned_data`, checks `is_bound`/`empty_permitted`, then awaits `_aclean_fields()`, `_aclean_form()`, `_apost_clean()`.
- `_aclean_fields()`: for each field, calls `field._clean_bound_field(bf)` (sync — pure Python), then checks `clean_<name>` with `asyncio.iscoroutinefunction()` — awaits if async, calls directly if sync.
- `_aclean_form()`: same sync/async detection on `self.clean()`.
- `_apost_clean()`: no-op on base mixin (matches `BaseForm._post_clean()`).

### AsyncModelFormMixin

```python
class AsyncModelFormMixin(AsyncFormMixin):
    async def _apost_clean(self) -> None
    async def asave(self, commit: bool = True) -> Model
    async def _asave_m2m(self) -> None
    async def avalidate_unique(self) -> None
    async def avalidate_constraints(self) -> None
```

- `_apost_clean()`: calls `construct_instance()` (sync), wraps `instance.full_clean()` with `sync_to_async` (Django Model has no `afull_clean`), wraps `validate_unique()`/`validate_constraints()` similarly.
- `asave(commit=True)`: raises `ValueError` if errors exist. Calls `construct_instance()`, then `await instance.asave()` + `await _asave_m2m()` if commit, else defers `save_m2m = _asave_m2m`.
- `_asave_m2m()`: mirrors `_save_m2m()` — iterates `opts.many_to_many` and `opts.private_fields`. For M2M fields, `save_form_data` calls `manager.set()` which hits the DB — wrap each `f.save_form_data(instance, data)` call with `sync_to_async`.
- `avalidate_unique()` / `avalidate_constraints()`: wrap `instance.validate_unique()`/`validate_constraints()` with `sync_to_async`.

### FORMWORK_FORCE_ASYNC setting

A Django setting that makes sync entry points raise `RuntimeError`:

```python
# settings.py
FORMWORK_FORCE_ASYNC = True  # default: False
```

When enabled, these sync methods raise with a message pointing to the async alternative:
- `full_clean()` → "Use afull_clean()"
- `is_valid()` → "Use ais_valid()"
- `save()` (ModelForm) → "Use asave()"

The `errors` property is caught because it calls `full_clean()`.

This is a testing/CI tool: enable it to catch accidental sync form usage in async views. Can be toggled per-test with `@override_settings(FORMWORK_FORCE_ASYNC=True)`.

The guard is checked at runtime (reads from `django.conf.settings`), not at form init time — so it respects `override_settings` in tests.

### Form class changes

```python
# forms.py
class FormworkForm(AsyncFormMixin, _AutoSearchMixin, Form):
    default_renderer = FormworkRenderer

class FormworkModelForm(AsyncModelFormMixin, _AutoSearchMixin, ModelForm):
    default_renderer = FormworkRenderer
```

### Exports

Added to `django_formwork/__init__.py`:
- `AsyncFormMixin`
- `AsyncModelFormMixin`

## Design decisions

1. **Sync/async detection via `asyncio.iscoroutinefunction()`** — same pattern Django uses for middleware and views. Backward compatible: existing sync clean methods work unchanged.

2. **`Field.clean()` stays sync** — field validation is pure Python (regex, type coercion, min/max). No async variant needed.

3. **`sync_to_async` for Model validation** — Django 6.0 Model only has `asave()`, `adelete()`, `arefresh_from_db()`. No async `full_clean`, `validate_unique`, `validate_constraints`. We wrap rather than reimplement. When Django adds native async versions, we switch.

4. **Setting over constructor kwarg** — `FORMWORK_FORCE_ASYNC` is a Django setting rather than a per-form `_force_async` kwarg. Easier to toggle globally in tests with `@override_settings`, no need to change form instantiation code.

5. **`errors` property not duplicated** — no `aerrors()` method. Users call `await ais_valid()` or `await afull_clean()` first, then access `self.errors` normally. Matches Django's sync/async split pattern (`save()`/`asave()`, not `errors`/`aerrors`).

## Testing

Unit tests in `tests/test_async_forms.py` using pytest-asyncio:

- Sync `clean_<field>` methods work through async path
- Async `clean_<field>` methods are awaited
- Mixed sync/async clean methods on same form
- Async `clean()` (form-wide) is awaited
- `ais_valid()` returns correct bool, populates `errors` and `cleaned_data`
- `ValidationError` in async clean populates field errors
- `ValidationError` in async `clean()` populates non-field errors
- `asave()` persists model instance (requires test model)
- `asave(commit=False)` returns unsaved instance with `save_m2m`
- M2M saving through `_asave_m2m()`
- `FORMWORK_FORCE_ASYNC=True` makes `is_valid()` raise `RuntimeError`
- `FORMWORK_FORCE_ASYNC=True` makes `full_clean()` raise `RuntimeError`
- `FORMWORK_FORCE_ASYNC=True` makes `save()` raise `RuntimeError`
- `FORMWORK_FORCE_ASYNC=True` does NOT block async methods
- Standalone mixin usage with plain `Form` / `ModelForm`
