"""Tests for ``validate_dirty_only`` on FormworkForm and FormworkModelForm.

When the flag is on, fields whose value did not change (per
``BoundField.has_changed()`` or, for model fields, ``get_dirty_fields()``)
skip every validator that could fail on legacy data: field validators,
``clean_<name>``, model.clean_fields, validate_unique, validate_constraints.
"""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from e2e.models import BasicFormData, DirtyTrackedData

from django_formwork.forms import FormworkForm, FormworkModelForm

pytestmark = pytest.mark.django_db


def _reject_legacy(value: str) -> None:
    if value == "LEGACY_BAD":
        raise ValidationError("Legacy bad value not allowed.")


# ---------------------------------------------------------------------------
# Form-only (no model)
# ---------------------------------------------------------------------------


class FormOnlyForm(FormworkForm):
    """Plain form with a validator that fails on a legacy-bad initial value."""

    name = forms.CharField(validators=[_reject_legacy])
    note = forms.CharField(required=False)


class FormOnlyMetaOn(FormworkForm):
    name = forms.CharField(validators=[_reject_legacy])
    note = forms.CharField(required=False)

    class Meta:
        validate_dirty_only = True


class TestFormOnly:
    def test_default_validates_unchanged_legacy_value(self):
        form = FormOnlyForm(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
        )
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_kwarg_skips_unchanged_legacy_value(self):
        form = FormOnlyForm(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
            validate_dirty_only=True,
        )
        assert form.is_valid() is True
        assert form.cleaned_data["name"] == "LEGACY_BAD"
        assert form.cleaned_data["note"] == "new"

    def test_meta_default_skips_unchanged_legacy_value(self):
        form = FormOnlyMetaOn(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
        )
        assert form.is_valid() is True

    def test_kwarg_overrides_meta(self):
        form = FormOnlyMetaOn(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
            validate_dirty_only=False,
        )
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_changed_field_still_validated(self):
        form = FormOnlyForm(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "ok", "note": ""},
            validate_dirty_only=True,
        )
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_clean_method_skipped_for_unchanged(self):
        calls: list[str] = []

        class _Form(FormworkForm):
            name = forms.CharField()
            note = forms.CharField(required=False)

            def clean_name(self):
                calls.append("clean_name")
                return self.cleaned_data["name"].upper()

        form = _Form(
            data={"name": "alice", "note": "new"},
            initial={"name": "alice", "note": ""},
            validate_dirty_only=True,
        )
        assert form.is_valid() is True
        # clean_name() never ran, so the value carries through as-is.
        assert calls == []
        assert form.cleaned_data["name"] == "alice"

    def test_clean_method_runs_for_changed(self):
        class _Form(FormworkForm):
            name = forms.CharField()

            def clean_name(self):
                return self.cleaned_data["name"].upper()

        form = _Form(
            data={"name": "alice"},
            initial={"name": "bob"},
            validate_dirty_only=True,
        )
        assert form.is_valid() is True
        assert form.cleaned_data["name"] == "ALICE"


# ---------------------------------------------------------------------------
# ModelForm
# ---------------------------------------------------------------------------


class DirtyTrackedForm(FormworkModelForm):
    class Meta:
        model = DirtyTrackedData
        fields = ["name", "email", "note"]


class DirtyTrackedFormOn(FormworkModelForm):
    class Meta:
        model = DirtyTrackedData
        fields = ["name", "email", "note"]
        validate_dirty_only = True


def _seed_legacy() -> DirtyTrackedData:
    """Insert a legacy-bad row, bypassing validation."""
    obj = DirtyTrackedData(name="LEGACY_BAD", email="a@b.com", note="")
    # save() bypasses full_clean(), so the bad value lands in the DB.
    obj.save()
    return obj


class TestModelFormUpdate:
    def test_default_validates_legacy_field_on_untouched_submission(self):
        obj = _seed_legacy()
        # Reload so dirty-tracking baseline is the DB row.
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedForm(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed"},
            instance=obj,
        )
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_dirty_only_skips_legacy_field(self):
        obj = _seed_legacy()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedFormOn(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed"},
            instance=obj,
        )
        assert form.is_valid() is True
        form.save()
        obj.refresh_from_db()
        assert obj.note == "changed"
        assert obj.name == "LEGACY_BAD"  # legacy stayed put

    def test_dirty_only_kwarg_overrides_meta(self):
        obj = _seed_legacy()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedFormOn(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed"},
            instance=obj,
            validate_dirty_only=False,
        )
        assert form.is_valid() is False

    def test_changed_field_still_validated(self):
        obj = DirtyTrackedData(name="ok", email="a@b.com", note="")
        obj.save()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedFormOn(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": ""},
            instance=obj,
        )
        # name changed to LEGACY_BAD, so the validator must run and fail.
        assert form.is_valid() is False
        assert "name" in form.errors


class TestModelFormCreate:
    def test_dirty_only_does_not_skip_on_create(self):
        # _state.adding=True -> validate everything regardless of flag.
        form = DirtyTrackedFormOn(data={"name": "LEGACY_BAD", "email": "a@b.com", "note": ""})
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_dirty_only_create_valid(self):
        form = DirtyTrackedFormOn(data={"name": "ok", "email": "a@b.com", "note": "hi"})
        assert form.is_valid() is True
        obj = form.save()
        assert obj.pk is not None


class TestImproperlyConfigured:
    def test_validate_dirty_only_requires_dirtyfieldsmixin(self):
        class _BadForm(FormworkModelForm):
            class Meta:
                model = BasicFormData  # plain models.Model, no get_dirty_fields()
                fields = ["name", "email"]
                validate_dirty_only = True

        with pytest.raises(ImproperlyConfigured, match="get_dirty_fields"):
            _BadForm()


class TestCrossFieldRuleGuard:
    """``model.clean()`` runs unconditionally; the rule body uses
    ``self.fields_dirty(...)`` to decide whether to fire on legacy data."""

    def test_rule_fires_when_relevant_field_changes(self):
        obj = DirtyTrackedData(name="alice", email="a@b.com", note="")
        obj.save()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        # Change name to equal email -> rule fires.
        form = DirtyTrackedFormOn(
            data={"name": "a@b.com", "email": "a@b.com", "note": ""},
            instance=obj,
        )
        assert form.is_valid() is False
        assert "name" in form.errors

    def test_rule_skipped_when_neither_field_changes(self):
        # Seed a row where name == email; rule would normally fire,
        # but with neither dirty the guarded body skips.
        obj = DirtyTrackedData(name="x@y.com", email="x@y.com", note="")
        obj.save()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedFormOn(
            data={"name": "x@y.com", "email": "x@y.com", "note": "changed"},
            instance=obj,
        )
        assert form.is_valid() is True


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncFormOnly:
    async def test_dirty_only_skips_unchanged_in_ais_valid(self):
        form = FormOnlyForm(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
            validate_dirty_only=True,
        )
        assert await form.ais_valid() is True
        assert form.cleaned_data["note"] == "new"

    async def test_dirty_only_off_validates_unchanged(self):
        form = FormOnlyForm(
            data={"name": "LEGACY_BAD", "note": "new"},
            initial={"name": "LEGACY_BAD", "note": ""},
        )
        assert await form.ais_valid() is False
        assert "name" in form.errors


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncModelForm:
    async def test_dirty_only_skips_legacy_field(self):
        from asgiref.sync import sync_to_async

        obj = await sync_to_async(_seed_legacy)()
        obj = await DirtyTrackedData.objects.aget(pk=obj.pk)
        form = DirtyTrackedFormOn(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed"},
            instance=obj,
        )
        assert await form.ais_valid() is True
        await form.asave()
        await sync_to_async(obj.refresh_from_db)()
        assert obj.note == "changed"

    async def test_dirty_only_does_not_skip_on_create(self):
        form = DirtyTrackedFormOn(data={"name": "LEGACY_BAD", "email": "a@b.com", "note": ""})
        assert await form.ais_valid() is False
        assert "name" in form.errors


# ---------------------------------------------------------------------------
# Relational field (ForeignKey) on the dirty-only edit path
# ---------------------------------------------------------------------------


class DirtyTrackedFKForm(FormworkModelForm):
    class Meta:
        model = DirtyTrackedData
        fields = ["name", "email", "note", "region"]
        validate_dirty_only = True


def _seed_with_region() -> DirtyTrackedData:
    from e2e.models import Region

    region = Region.objects.create(name="North")
    obj = DirtyTrackedData(name="LEGACY_BAD", email="a@b.com", note="", region=region)
    obj.save()  # bypasses full_clean so the legacy name persists
    return obj


class TestDirtyOnlyForeignKey:
    def test_unchanged_fk_edit_succeeds(self):
        # Regression: an unchanged FK left its raw pk in cleaned_data and
        # construct_instance rejected the int. Editing only ``note`` must work
        # and leave the relation (and the legacy name) untouched.
        obj = _seed_with_region()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        form = DirtyTrackedFKForm(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed", "region": str(obj.region_id)},
            instance=obj,
        )
        assert form.is_valid() is True
        form.save()
        obj.refresh_from_db()
        assert obj.note == "changed"
        assert obj.region_id is not None
        assert obj.name == "LEGACY_BAD"

    def test_changed_fk_still_validates_and_saves(self):
        from e2e.models import Region

        obj = _seed_with_region()
        obj = DirtyTrackedData.objects.get(pk=obj.pk)
        other = Region.objects.create(name="South")
        form = DirtyTrackedFKForm(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "", "region": str(other.pk)},
            instance=obj,
        )
        assert form.is_valid() is True
        form.save()
        obj.refresh_from_db()
        assert obj.region_id == other.pk


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncDirtyOnlyForeignKey:
    async def test_unchanged_fk_edit_succeeds(self):
        from asgiref.sync import sync_to_async

        obj = await sync_to_async(_seed_with_region)()
        obj = await DirtyTrackedData.objects.aget(pk=obj.pk)
        form = DirtyTrackedFKForm(
            data={"name": "LEGACY_BAD", "email": "a@b.com", "note": "changed", "region": str(obj.region_id)},
            instance=obj,
        )
        assert await form.ais_valid() is True
        await form.asave()
        await sync_to_async(obj.refresh_from_db)()
        assert obj.note == "changed"
        assert obj.region_id is not None
