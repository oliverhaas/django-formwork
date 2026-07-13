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
from django.db import DatabaseError, connection, models
from django.db.models import QuerySet
from django.db.models.functions import Upper
from django.forms import inlineformset_factory, modelformset_factory
from django.test.utils import CaptureQueriesContext
from e2e.models import (
    CheckThenUnique,
    ConditionalUnique,
    ConstraintPair,
    CustomMessageUnique,
    DatedCode,
    Membership,
    MultiCheck,
    Region,
    UniqueAndCheckPair,
    UniqueCode,
    UniquePair,
)

from django_formwork.formsets import (
    FormworkBaseModelFormSet,
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


# ---------------------------------------------------------------------------
# Parity: batchable Meta UniqueConstraint alongside a CheckConstraint
# ---------------------------------------------------------------------------


class TestUniqueAndCheckParity:
    """A field-based ``UniqueConstraint`` is batched; the ``CheckConstraint``
    next to it stays on Django's per-form path. Both must match stock."""

    def test_add_without_collision_is_valid(self):
        _assert_parity(
            UniqueAndCheckPair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "a", "right": "2"}]),
        )

    def test_unique_collision_matches_stock(self):
        UniqueAndCheckPair.objects.create(left="a", right="1")
        _assert_parity(
            UniqueAndCheckPair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "b", "right": "2"}]),
        )

    def test_check_violation_matches_stock(self):
        # left="BAD" trips the CheckConstraint, which is never batched.
        _assert_parity(
            UniqueAndCheckPair,
            ["left", "right"],
            _data([{"left": "BAD", "right": "1"}, {"left": "ok", "right": "2"}]),
        )

    def test_unique_and_check_violations_together_match_stock(self):
        UniqueAndCheckPair.objects.create(left="a", right="1")
        _assert_parity(
            UniqueAndCheckPair,
            ["left", "right"],
            _data([{"left": "a", "right": "1"}, {"left": "BAD", "right": "9"}]),
        )


class TestMultiCheckParity:
    """Two ``CheckConstraint`` s evaluated in one batched round trip must
    surface byte-for-byte what stock per-form validation does: each message,
    each code, ``__all__`` placement, and ``Meta`` declaration order."""

    def test_no_violation_is_valid(self):
        _assert_parity(
            MultiCheck,
            ["left", "right"],
            _data([{"left": "ok", "right": "ok"}, {"left": "fine", "right": "fine"}]),
        )

    def test_first_check_violation_matches_stock(self):
        _assert_parity(
            MultiCheck,
            ["left", "right"],
            _data([{"left": "BAD", "right": "ok"}, {"left": "ok", "right": "ok"}]),
        )

    def test_second_check_custom_message_matches_stock(self):
        _assert_parity(
            MultiCheck,
            ["left", "right"],
            _data([{"left": "ok", "right": "BAD"}]),
        )

    def test_both_checks_violation_order_matches_stock(self):
        # One row trips both checks; the two messages must land in __all__ in
        # Meta declaration order (left check, then right check).
        _assert_parity(
            MultiCheck,
            ["left", "right"],
            _data([{"left": "BAD", "right": "BAD"}]),
        )

    def test_mixed_rows_match_stock(self):
        _assert_parity(
            MultiCheck,
            ["left", "right"],
            _data(
                [
                    {"left": "BAD", "right": "ok"},
                    {"left": "ok", "right": "ok"},
                    {"left": "ok", "right": "BAD"},
                    {"left": "BAD", "right": "BAD"},
                ],
            ),
        )


class TestConstraintOrderParity:
    """``Meta.constraints`` declaration order must survive batching.

    A check batched in one pass and a unique batched in another must still
    interleave their ``__all__`` messages in the order stock Django emits them.
    """

    def test_check_before_unique_order_matches_stock(self):
        # note=BAD trips the check (declared first); (a, 1) trips the unique
        # (declared second). Stock lists check then unique in __all__.
        CheckThenUnique.objects.create(left="a", right="1", note="ok")
        _assert_parity(
            CheckThenUnique,
            ["left", "right", "note"],
            _data([{"left": "a", "right": "1", "note": "BAD"}]),
        )


# ---------------------------------------------------------------------------
# Parity: non-batchable UniqueConstraints stay on Django's per-form path
# ---------------------------------------------------------------------------


class TestConditionalUniqueParity:
    """A conditional (partial) ``UniqueConstraint`` is not batchable."""

    def test_two_active_rows_collide_like_stock(self):
        ConditionalUnique.objects.create(slug="x", active=True)
        _assert_parity(
            ConditionalUnique,
            ["slug", "active"],
            _data([{"slug": "x", "active": "on"}]),
        )

    def test_inactive_row_does_not_collide_like_stock(self):
        ConditionalUnique.objects.create(slug="x", active=True)
        # The condition is active=True, so an inactive duplicate is allowed.
        _assert_parity(
            ConditionalUnique,
            ["slug", "active"],
            _data([{"slug": "x"}]),  # active unchecked -> False
        )


class TestCustomMessageUniqueParity:
    """A custom ``violation_error_message`` means Django uses
    ``get_violation_error_message`` (not ``unique_error_message``), so the
    constraint is not batchable and the custom text must survive."""

    def test_custom_message_is_preserved_like_stock(self):
        CustomMessageUnique.objects.create(code="taken")
        _assert_parity(
            CustomMessageUnique,
            ["code"],
            _data([{"code": "taken"}]),
        )


# ---------------------------------------------------------------------------
# Efficiency: Meta UniqueConstraint is batched too
# ---------------------------------------------------------------------------


class TestMetaConstraintEfficiency:
    def _our(self, model, fields, rows):
        cls = formwork_modelformset_factory(model, fields=fields, extra=0)
        return cls(_data(rows), queryset=model.objects.none())

    def _stock(self, model, fields, rows):
        cls = modelformset_factory(model, fields=fields, extra=0)
        return cls(_data(rows), queryset=model.objects.none())

    def test_constraint_pair_queries_are_constant_in_form_count(self):
        small = [{"left": f"L{i}", "right": f"R{i}"} for i in range(3)]
        big = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_small:
            assert self._our(ConstraintPair, ["left", "right"], small).is_valid()
        with CaptureQueriesContext(connection) as q_big:
            assert self._our(ConstraintPair, ["left", "right"], big).is_valid()

        assert len(q_small.captured_queries) == len(q_big.captured_queries)

    def test_constraint_pair_uses_fewer_queries_than_stock(self):
        rows = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_ours:
            assert self._our(ConstraintPair, ["left", "right"], rows).is_valid()
        with CaptureQueriesContext(connection) as q_stock:
            assert self._stock(ConstraintPair, ["left", "right"], rows).is_valid()

        assert len(q_ours.captured_queries) < len(q_stock.captured_queries)

    def test_unique_part_is_batched_even_next_to_a_check(self):
        # Both the unique part and the check are batched, so we beat stock's
        # several-queries-per-form by a wide margin.
        rows = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_ours:
            assert self._our(UniqueAndCheckPair, ["left", "right"], rows).is_valid()
        with CaptureQueriesContext(connection) as q_stock:
            assert self._stock(UniqueAndCheckPair, ["left", "right"], rows).is_valid()

        assert len(q_ours.captured_queries) < len(q_stock.captured_queries)


# ---------------------------------------------------------------------------
# Efficiency: CheckConstraints are batched into one round trip
# ---------------------------------------------------------------------------


class TestCheckBatchingEfficiency:
    def _our(self, model, fields, rows):
        cls = formwork_modelformset_factory(model, fields=fields, extra=0)
        return cls(_data(rows), queryset=model.objects.none())

    def _stock(self, model, fields, rows):
        cls = modelformset_factory(model, fields=fields, extra=0)
        return cls(_data(rows), queryset=model.objects.none())

    def test_multi_check_queries_are_constant_in_form_count(self):
        small = [{"left": f"L{i}", "right": f"R{i}"} for i in range(3)]
        big = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_small:
            assert self._our(MultiCheck, ["left", "right"], small).is_valid()
        with CaptureQueriesContext(connection) as q_big:
            assert self._our(MultiCheck, ["left", "right"], big).is_valid()

        assert len(q_small.captured_queries) == len(q_big.captured_queries)

    def test_multi_check_uses_fewer_queries_than_stock(self):
        rows = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_ours:
            assert self._our(MultiCheck, ["left", "right"], rows).is_valid()
        with CaptureQueriesContext(connection) as q_stock:
            assert self._stock(MultiCheck, ["left", "right"], rows).is_valid()

        assert len(q_ours.captured_queries) < len(q_stock.captured_queries)

    def test_unique_and_check_queries_are_constant_in_form_count(self):
        small = [{"left": f"L{i}", "right": f"R{i}"} for i in range(3)]
        big = [{"left": f"L{i}", "right": f"R{i}"} for i in range(12)]

        with CaptureQueriesContext(connection) as q_small:
            assert self._our(UniqueAndCheckPair, ["left", "right"], small).is_valid()
        with CaptureQueriesContext(connection) as q_big:
            assert self._our(UniqueAndCheckPair, ["left", "right"], big).is_valid()

        assert len(q_small.captured_queries) == len(q_big.captured_queries)


# ---------------------------------------------------------------------------
# Non-batchable: GeneratedField and custom-collation unique constraints
# ---------------------------------------------------------------------------


class GeneratedItem(models.Model):
    """Unique constraint covering a GeneratedField; must not be batched."""

    base = models.CharField(max_length=50)
    upper = models.GeneratedField(
        expression=Upper("base"),
        output_field=models.CharField(max_length=50),
        db_persist=True,
    )

    class Meta:
        app_label = "e2e"
        constraints = [models.UniqueConstraint(fields=["upper"], name="uq_generated_item_upper")]

    def __str__(self):
        return self.base


class CollatedItem(models.Model):
    """Unique constraint over a custom-collation field; must not be batched."""

    code = models.CharField(max_length=50, db_collation="NOCASE")

    class Meta:
        app_label = "e2e"
        constraints = [models.UniqueConstraint(fields=["code"], name="uq_collated_item_code")]

    def __str__(self):
        return self.code


def test_plain_unique_constraint_is_batchable():
    """Control: a plain field-based UniqueConstraint stays on the batched path."""
    constraint = ConstraintPair._meta.constraints[0]
    assert FormworkBaseModelFormSet._is_batchable_unique(constraint, ConstraintPair) is True


def test_generated_field_unique_constraint_is_not_batchable():
    """Stock validate substitutes the DB expression, so batching must bail out."""
    constraint = GeneratedItem._meta.constraints[0]
    assert FormworkBaseModelFormSet._is_batchable_unique(constraint, GeneratedItem) is False


def test_custom_collation_unique_constraint_is_not_batchable():
    """Python equality cannot replay a case-insensitive column collation."""
    constraint = CollatedItem._meta.constraints[0]
    assert FormworkBaseModelFormSet._is_batchable_unique(constraint, CollatedItem) is False


@pytest.mark.django_db(transaction=True)
def test_collated_unique_collision_matches_stock():
    """A case-insensitive duplicate must raise exactly what stock raises."""
    with connection.schema_editor() as editor:
        editor.create_model(CollatedItem)
    try:
        CollatedItem.objects.create(code="taken")
        _assert_parity(CollatedItem, ["code"], _data([{"code": "TAKEN"}]))
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(CollatedItem)


# ---------------------------------------------------------------------------
# Fallback: a failing batched unique prefetch degrades to per-form checks
# ---------------------------------------------------------------------------


def _raise_database_error(*args, **kwargs):
    """Stand-in for a batched prefetch that exceeds backend limits."""
    raise DatabaseError("simulated oversized batched query")


def test_unique_prefetch_database_error_falls_back_to_stock_errors(monkeypatch):
    """Classic unique checks must survive a failing batched prefetch."""
    UniqueCode.objects.create(code="TAKEN", label="seed")
    data = _data([{"code": "TAKEN", "label": "x"}, {"code": "FREE", "label": "y"}])
    stock_cls = modelformset_factory(UniqueCode, fields=["code", "label"], extra=0)
    stock = stock_cls(data, queryset=UniqueCode.objects.all())
    assert stock.is_valid() is False

    monkeypatch.setattr(QuerySet, "values_list", _raise_database_error)
    our_cls = formwork_modelformset_factory(UniqueCode, fields=["code", "label"], extra=0)
    ours = our_cls(data, queryset=UniqueCode.objects.all())
    assert ours.is_valid() is False
    assert _errors_repr(ours) == _errors_repr(stock)


def test_meta_unique_prefetch_database_error_falls_back_to_constraint_validate(monkeypatch):
    """Meta UniqueConstraints must survive a failing batched prefetch."""
    ConstraintPair.objects.create(left="a", right="1")
    data = _data([{"left": "a", "right": "1"}, {"left": "b", "right": "2"}])
    stock_cls = modelformset_factory(ConstraintPair, fields=["left", "right"], extra=0)
    stock = stock_cls(data, queryset=ConstraintPair.objects.all())
    assert stock.is_valid() is False

    monkeypatch.setattr(QuerySet, "values_list", _raise_database_error)
    our_cls = formwork_modelformset_factory(ConstraintPair, fields=["left", "right"], extra=0)
    ours = our_cls(data, queryset=ConstraintPair.objects.all())
    assert ours.is_valid() is False
    assert _errors_repr(ours) == _errors_repr(stock)
