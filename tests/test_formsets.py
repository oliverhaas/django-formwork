"""Tests for the Formwork formset family.

The headline feature is batched uniqueness: a stock ``BaseModelFormSet`` runs
one ``.exists()`` query per unique check *per form* (N forms x M checks = N*M
round trips), because each child ``ModelForm._post_clean`` calls
``instance.validate_unique()``.  ``FormworkBaseModelFormSet`` collapses that into
one query per distinct unique check, regardless of form count, while producing
*byte-for-byte the same* validation result as stock Django.

The parity tests pin that promise: for the same model, DB state and POST data, a
Formwork formset and a stock ``modelformset_factory`` formset must report the
same per-form errors and the same non-form errors.  The query-count tests pin
the efficiency win.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.forms import inlineformset_factory, modelformset_factory
from django.test.utils import CaptureQueriesContext
from e2e.models import ConstraintPair, DatedCode, Membership, Region, UniqueCode, UniquePair

from django_formwork.formsets import (
    formwork_inlineformset_factory,
    formwork_modelformset_factory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _management(prefix: str, total: int, initial: int) -> dict[str, str]:
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def _data(rows: list[dict[str, str]], *, prefix: str = "form", initial: int = 0) -> dict[str, str]:
    """Build a bound-formset payload from a list of per-form field dicts."""
    payload = _management(prefix, total=len(rows), initial=initial)
    for i, row in enumerate(rows):
        for key, value in row.items():
            payload[f"{prefix}-{i}-{key}"] = value
    return payload


def _errors_repr(formset: Any) -> tuple[list[dict[str, list[str]]], list[str]]:
    """Normalize a formset's errors to plain strings for parity comparison."""
    per_form = [
        {field: [str(m) for m in errs] for field, errs in form_errors.items()} for form_errors in formset.errors
    ]
    return per_form, [str(m) for m in formset.non_form_errors()]


def _assert_parity(model: type, fields: list[str], data: dict[str, str], **factory_kw: Any) -> None:
    """A Formwork formset must report exactly what stock Django reports."""
    stock_cls = modelformset_factory(model, fields=fields, extra=0, **factory_kw)
    our_cls = formwork_modelformset_factory(model, fields=fields, extra=0, **factory_kw)

    stock = stock_cls(data, queryset=model.objects.all())
    ours = our_cls(data, queryset=model.objects.all())

    assert stock.is_valid() == ours.is_valid()
    assert _errors_repr(stock) == _errors_repr(ours)


# ---------------------------------------------------------------------------
# Parity: single unique=True field
# ---------------------------------------------------------------------------


class TestSingleUniqueParity:
    def test_add_without_collision_is_valid(self):
        _assert_parity(
            UniqueCode,
            ["code", "label"],
            _data([{"code": "AAA", "label": "a"}, {"code": "BBB", "label": "b"}]),
        )

    def test_add_collides_with_existing_row(self):
        UniqueCode.objects.create(code="TAKEN", label="seed")
        _assert_parity(
            UniqueCode,
            ["code", "label"],
            _data([{"code": "TAKEN", "label": "x"}, {"code": "FREE", "label": "y"}]),
        )

    def test_collision_error_lands_on_the_unique_field(self):
        UniqueCode.objects.create(code="TAKEN", label="seed")
        our_cls = formwork_modelformset_factory(UniqueCode, fields=["code", "label"], extra=0)
        formset = our_cls(
            _data([{"code": "TAKEN", "label": "x"}]),
            queryset=UniqueCode.objects.all(),
        )
        assert formset.is_valid() is False
        # Single-field uniqueness errors attach to the field, not NON_FIELD_ERRORS.
        assert "code" in formset.forms[0].errors


# ---------------------------------------------------------------------------
# Parity: classic unique_together
# ---------------------------------------------------------------------------


class TestUniqueTogetherParity:
    def test_add_without_collision_is_valid(self):
        _assert_parity(
            UniquePair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "a", "right": "2"}]),
        )

    def test_add_collides_with_existing_row(self):
        UniquePair.objects.create(left="a", right="1")
        _assert_parity(
            UniquePair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "b", "right": "1"}]),
        )

    def test_in_post_duplicate_is_deduped(self):
        # Two submitted rows collide with each other (not the DB). This is the
        # in-memory cross-form dedup that stock BaseModelFormSet already does;
        # the Formwork formset must preserve it.
        _assert_parity(
            UniquePair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "a", "right": "1"}]),
        )


# ---------------------------------------------------------------------------
# Parity: editing existing rows excludes self
# ---------------------------------------------------------------------------


class TestEditParity:
    def test_edit_label_only_does_not_self_collide(self):
        row = UniqueCode.objects.create(code="AAA", label="old")
        _assert_parity(
            UniqueCode,
            ["code", "label"],
            _data([{"id": str(row.pk), "code": "AAA", "label": "new"}], initial=1),
        )

    def test_edit_into_another_rows_code_collides(self):
        row = UniqueCode.objects.create(code="AAA", label="a")
        UniqueCode.objects.create(code="BBB", label="b")
        _assert_parity(
            UniqueCode,
            ["code", "label"],
            _data([{"id": str(row.pk), "code": "BBB", "label": "a"}], initial=1),
        )


# ---------------------------------------------------------------------------
# Parity: Meta UniqueConstraint stays on Django's per-form path
# ---------------------------------------------------------------------------


class TestMetaConstraintParity:
    """Meta ``UniqueConstraint`` is validated by ``validate_constraints``, which
    the Formwork formset leaves untouched (per-form). Parity must still hold."""

    def test_add_without_collision_is_valid(self):
        _assert_parity(
            ConstraintPair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "a", "right": "2"}]),
        )

    def test_add_collides_with_existing_row(self):
        ConstraintPair.objects.create(left="a", right="1")
        _assert_parity(
            ConstraintPair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "c", "right": "9"}]),
        )


# ---------------------------------------------------------------------------
# Parity: unique_for_date (batched date checks)
# ---------------------------------------------------------------------------


class TestUniqueForDateParity:
    def test_same_slug_different_date_is_valid(self):
        DatedCode.objects.create(slug="hello", published="2026-01-01")
        _assert_parity(
            DatedCode,
            ["slug", "published"],
            _data([{"slug": "hello", "published": "2026-02-02"}]),
        )

    def test_same_slug_same_date_collides(self):
        DatedCode.objects.create(slug="hello", published="2026-01-01")
        _assert_parity(
            DatedCode,
            ["slug", "published"],
            _data([{"slug": "hello", "published": "2026-01-01"}, {"slug": "other", "published": "2026-01-01"}]),
        )


# ---------------------------------------------------------------------------
# Parity: a row marked for deletion is excluded from uniqueness
# ---------------------------------------------------------------------------


class TestDeletionParity:
    def test_deleted_row_collision_is_ignored(self):
        UniqueCode.objects.create(code="TAKEN", label="seed")
        stock_cls = modelformset_factory(UniqueCode, fields=["code", "label"], extra=0, can_delete=True)
        our_cls = formwork_modelformset_factory(UniqueCode, fields=["code", "label"], extra=0, can_delete=True)
        # One submitted row collides with the DB but is flagged for deletion;
        # neither formset should surface a uniqueness error for it.
        payload = _data([{"code": "TAKEN", "label": "x", "DELETE": "on"}, {"code": "FREE", "label": "y"}])

        stock = stock_cls(payload, queryset=UniqueCode.objects.all())
        ours = our_cls(payload, queryset=UniqueCode.objects.all())
        assert stock.is_valid() == ours.is_valid()
        assert _errors_repr(stock) == _errors_repr(ours)


# ---------------------------------------------------------------------------
# Efficiency: query count
# ---------------------------------------------------------------------------


class TestInlineParity:
    """``FormworkBaseInlineFormSet`` must match stock ``inlineformset_factory``.

    The child is unique per ``(region, slug)``.  The foreign key is set on each
    child instance before validation, so ``region_id`` is part of the batched
    lookup just as it is part of stock's per-form ``.exists()`` filter.
    """

    def _assert_parity(self, parent: Region, rows: list[dict[str, str]], *, initial: int = 0) -> None:
        stock_cls = inlineformset_factory(Region, Membership, fields=["slug"], extra=0)
        our_cls = formwork_inlineformset_factory(Region, Membership, fields=["slug"], extra=0)
        prefix = our_cls.get_default_prefix()
        data = _data(rows, prefix=prefix, initial=initial)

        stock = stock_cls(data, instance=parent)
        ours = our_cls(data, instance=parent)

        assert stock.is_valid() == ours.is_valid()
        assert _errors_repr(stock) == _errors_repr(ours)

    def test_add_without_collision_is_valid(self):
        region = Region.objects.create(name="North")
        self._assert_parity(region, [{"slug": "a"}, {"slug": "b"}])

    def test_add_collides_with_existing_child(self):
        region = Region.objects.create(name="North")
        Membership.objects.create(region=region, slug="a")
        self._assert_parity(region, [{"slug": "a"}, {"slug": "c"}])

    def test_same_slug_under_a_different_parent_is_valid(self):
        north = Region.objects.create(name="North")
        south = Region.objects.create(name="South")
        Membership.objects.create(region=south, slug="a")
        # "a" is taken under South, but this formset is bound to North.
        self._assert_parity(north, [{"slug": "a"}])

    def test_in_post_duplicate_is_deduped(self):
        region = Region.objects.create(name="North")
        self._assert_parity(region, [{"slug": "a"}, {"slug": "a"}])


class TestInlineQueryCount:
    def _formset(self, region: Region, rows: list[dict[str, str]]):
        cls = formwork_inlineformset_factory(Region, Membership, fields=["slug"], extra=0)
        return cls(_data(rows, prefix=cls.get_default_prefix()), instance=region)

    def test_uniqueness_queries_are_constant_in_form_count(self):
        region = Region.objects.create(name="North")
        small = [{"slug": f"s{i}"} for i in range(3)]
        big = [{"slug": f"s{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_small:
            assert self._formset(region, small).is_valid()
        with CaptureQueriesContext(connection) as q_big:
            assert self._formset(region, big).is_valid()

        assert len(q_small.captured_queries) == len(q_big.captured_queries)


class TestQueryCount:
    def _our_formset(self, rows: list[dict[str, str]]):
        cls = formwork_modelformset_factory(UniqueCode, fields=["code", "label"], extra=0)
        return cls(_data(rows), queryset=UniqueCode.objects.none())

    def _stock_formset(self, rows: list[dict[str, str]]):
        cls = modelformset_factory(UniqueCode, fields=["code", "label"], extra=0)
        return cls(_data(rows), queryset=UniqueCode.objects.none())

    def test_uniqueness_queries_are_constant_in_form_count(self):
        small = [{"code": f"C{i}", "label": ""} for i in range(3)]
        big = [{"code": f"C{i}", "label": ""} for i in range(12)]

        with CaptureQueriesContext(connection) as q_small:
            assert self._our_formset(small).is_valid()
        with CaptureQueriesContext(connection) as q_big:
            assert self._our_formset(big).is_valid()

        # Batched: the query count does not grow with the number of forms.
        assert len(q_small.captured_queries) == len(q_big.captured_queries)

    def test_uses_fewer_queries_than_stock(self):
        rows = [{"code": f"C{i}", "label": ""} for i in range(12)]

        with CaptureQueriesContext(connection) as q_ours:
            assert self._our_formset(rows).is_valid()
        with CaptureQueriesContext(connection) as q_stock:
            assert self._stock_formset(rows).is_valid()

        assert len(q_ours.captured_queries) < len(q_stock.captured_queries)
