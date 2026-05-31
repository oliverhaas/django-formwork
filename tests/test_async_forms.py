"""Tests for async form support on FormworkForm and FormworkModelForm."""

from __future__ import annotations

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.test import override_settings
from e2e.models import BasicFormData

from django_formwork.forms import FormworkForm, FormworkModelForm

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Test forms
# ---------------------------------------------------------------------------


class SyncCleanForm(FormworkForm):
    """All clean methods are sync."""

    name = forms.CharField()
    email = forms.EmailField()

    def clean_name(self):
        val = self.cleaned_data["name"]
        if val == "bad":
            raise ValidationError("Bad name")
        return val.upper()


class AsyncCleanForm(FormworkForm):
    """Async clean_<field> method."""

    name = forms.CharField()
    email = forms.EmailField()

    async def clean_name(self):
        val = self.cleaned_data["name"]
        if val == "bad":
            raise ValidationError("Bad name")
        return val.upper()


class MixedCleanForm(FormworkForm):
    """Mix of sync and async clean methods."""

    name = forms.CharField()
    email = forms.EmailField()

    def clean_name(self):
        return self.cleaned_data["name"].upper()

    async def clean_email(self):
        val = self.cleaned_data["email"]
        if val == "taken@example.com":
            raise ValidationError("Email taken")
        return val


class AsyncFormCleanForm(FormworkForm):
    """Async form-wide clean()."""

    name = forms.CharField()
    email = forms.EmailField()

    async def clean(self):
        cleaned = super().clean()
        if self.cleaned_data.get("name") == self.cleaned_data.get("email"):
            raise ValidationError("Name and email must differ")
        return cleaned


class BasicModelForm(FormworkModelForm):
    class Meta:
        model = BasicFormData
        fields = ["name", "email", "message"]


class AsyncModelForm(FormworkModelForm):
    class Meta:
        model = BasicFormData
        fields = ["name", "email", "message"]

    async def clean_name(self):
        val = self.cleaned_data["name"]
        if val == "taken":
            raise ValidationError("Name taken")
        return val


# ---------------------------------------------------------------------------
# Async form tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="class")
class TestAisValid:
    async def test_unbound_form_is_not_valid(self):
        form = SyncCleanForm()
        assert await form.ais_valid() is False

    async def test_valid_form(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert await form.ais_valid() is True
        assert form.cleaned_data["name"] == "ALICE"

    async def test_invalid_form(self):
        form = SyncCleanForm(data={"name": "", "email": "a@b.com"})
        assert await form.ais_valid() is False
        assert "name" in form.errors

    async def test_populates_errors_and_cleaned_data(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        await form.ais_valid()
        assert form.errors == {}
        assert form.cleaned_data == {"name": "ALICE", "email": "a@b.com"}


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncCleanFields:
    async def test_async_clean_field_called(self):
        form = AsyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert await form.ais_valid() is True
        assert form.cleaned_data["name"] == "ALICE"

    async def test_async_clean_field_validation_error(self):
        form = AsyncCleanForm(data={"name": "bad", "email": "a@b.com"})
        assert await form.ais_valid() is False
        assert "name" in form.errors
        assert "Bad name" in form.errors["name"][0]

    async def test_mixed_sync_async_clean_methods(self):
        form = MixedCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert await form.ais_valid() is True
        assert form.cleaned_data["name"] == "ALICE"
        assert form.cleaned_data["email"] == "a@b.com"

    async def test_mixed_async_validation_error(self):
        form = MixedCleanForm(
            data={"name": "alice", "email": "taken@example.com"},
        )
        assert await form.ais_valid() is False
        assert "email" in form.errors
        assert "Email taken" in form.errors["email"][0]


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncFormClean:
    async def test_async_clean_called(self):
        form = AsyncFormCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert await form.ais_valid() is True

    async def test_async_clean_validation_error(self):
        form = AsyncFormCleanForm(data={"name": "match", "email": "match"})
        await form.ais_valid()
        # "match" fails EmailField validation, so clean() never runs.
        # Use matching valid values instead:
        form2 = AsyncFormCleanForm(data={"name": "x@y.com", "email": "x@y.com"})
        assert await form2.ais_valid() is False
        assert "__all__" in form2.errors
        assert "Name and email must differ" in form2.errors["__all__"][0]


@pytest.mark.asyncio(loop_scope="class")
class TestAfullClean:
    async def test_sets_errors_and_cleaned_data(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        await form.afull_clean()
        assert form.errors == {}
        assert form.cleaned_data == {"name": "ALICE", "email": "a@b.com"}

    async def test_unbound_form(self):
        form = SyncCleanForm()
        await form.afull_clean()
        assert form.errors == {}
        assert not hasattr(form, "cleaned_data")


# ---------------------------------------------------------------------------
# Async model form tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="class")
class TestAsave:
    async def test_save_creates_instance(self):
        form = BasicModelForm(data={"name": "alice", "email": "a@b.com", "message": "hi"})
        assert await form.ais_valid() is True
        instance = await form.asave()
        assert instance.pk is not None
        assert instance.name == "alice"

    async def test_save_updates_instance(self):
        form = BasicModelForm(data={"name": "alice", "email": "a@b.com", "message": "hi"})
        await form.ais_valid()
        instance = await form.asave()

        form2 = BasicModelForm(
            data={"name": "bob", "email": "b@c.com", "message": "bye"},
            instance=instance,
        )
        await form2.ais_valid()
        updated = await form2.asave()
        assert updated.pk == instance.pk
        assert updated.name == "bob"

    async def test_save_commit_false(self):
        form = BasicModelForm(data={"name": "alice", "email": "a@b.com", "message": "hi"})
        await form.ais_valid()
        instance = await form.asave(commit=False)
        assert instance.pk is None
        assert instance.name == "alice"

    async def test_save_raises_on_errors(self):
        form = BasicModelForm(data={"name": "", "email": "bad", "message": ""})
        await form.ais_valid()
        with pytest.raises(ValueError, match="could not be created"):
            await form.asave()


@pytest.mark.asyncio(loop_scope="class")
class TestAsyncModelFormClean:
    async def test_async_clean_on_model_form(self):
        form = AsyncModelForm(data={"name": "alice", "email": "a@b.com", "message": "hi"})
        assert await form.ais_valid() is True
        assert form.cleaned_data["name"] == "alice"

    async def test_async_clean_validation_error_on_model_form(self):
        form = AsyncModelForm(data={"name": "taken", "email": "a@b.com", "message": "hi"})
        assert await form.ais_valid() is False
        assert "name" in form.errors


# ---------------------------------------------------------------------------
# FORMWORK_FORCE_ASYNC tests
# ---------------------------------------------------------------------------


class TestForceAsync:
    @override_settings(FORMWORK_FORCE_ASYNC=True)
    def test_is_valid_raises(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        with pytest.raises(RuntimeError, match="ais_valid"):
            form.is_valid()

    @override_settings(FORMWORK_FORCE_ASYNC=True)
    def test_full_clean_raises(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        with pytest.raises(RuntimeError, match="afull_clean"):
            form.full_clean()

    @override_settings(FORMWORK_FORCE_ASYNC=True)
    def test_errors_property_raises(self):
        """errors triggers full_clean(), which should raise."""
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        with pytest.raises(RuntimeError, match="afull_clean"):
            _ = form.errors

    @override_settings(FORMWORK_FORCE_ASYNC=True)
    def test_save_raises(self):
        form = BasicModelForm(data={"name": "alice", "email": "a@b.com", "message": "hi"})
        with pytest.raises(RuntimeError, match="asave"):
            form.save()

    @pytest.mark.asyncio
    @override_settings(FORMWORK_FORCE_ASYNC=True)
    async def test_async_methods_still_work(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert await form.ais_valid() is True

    @override_settings(FORMWORK_FORCE_ASYNC=False)
    def test_disabled_allows_sync(self):
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert form.is_valid() is True

    def test_default_allows_sync(self):
        """Without the setting, sync methods work normally."""
        form = SyncCleanForm(data={"name": "alice", "email": "a@b.com"})
        assert form.is_valid() is True
