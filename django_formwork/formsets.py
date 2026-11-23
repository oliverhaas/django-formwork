"""Efficient, DaisyUI-styled model formsets.

Django validates uniqueness one child form at a time: every
``ModelForm._post_clean`` calls ``instance.validate_unique()``, which runs one
``.exists()`` query *per unique check, per form*.  A formset with N rows and M
unique checks therefore issues N x M round trips for the against-the-database
check.  Django's own ``BaseModelFormSet.validate_unique`` does not help here: it
only dedups the submitted rows against *each other*, in memory, and never
batches the database hit.

:class:`FormworkBaseModelFormSet` collapses those N x M queries into one query
per distinct unique check, regardless of row count.  It tells each child form to
defer its checks (see :class:`~django_formwork.forms.FormworkModelForm`), then
replays Django's own ``_perform_unique_checks`` / ``_perform_date_checks``
against a single prefetched result set per check.  The same batching covers the
field-based ``Meta.constraints`` ``UniqueConstraint`` s that Django treats as
total (no condition, no expressions, default message), and every
``CheckConstraint`` is evaluated for all forms in one round trip (the same
tableless query ``Q.check`` runs, wrapped as side-by-side scalar subqueries).
The only constraints still replayed per form with Django's own
``constraint.validate()`` are the ones neither pass can batch: conditional or
expression unique constraints, custom message uniques, and unique constraints
touching a ``GeneratedField`` or a field with a custom ``db_collation``.  The
validation outcome is identical to stock Django: same errors, same messages,
same placement (field key vs ``__all__``); only the query count changes.

Two known divergences remain, both Python-side replays of a comparison the
database performs in SQL on the stock path.  Classic ``unique`` /
``unique_together`` lookups group prefetched rows by Python equality, so a
case-insensitive column collation (MySQL ``*_ci`` collations,
``db_collation="NOCASE"``, PostgreSQL citext) can hide a duplicate that stock's
collation-aware SQL comparison would report; the batched path then defers it to
the ``IntegrityError`` at save time.  ``UniqueConstraint`` s over such fields
opt out of batching (see ``_is_batchable_unique``), but classic unique fields
with a custom ``db_collation`` stay batched.  Likewise, ``unique_for_<date>``
checks against a ``DateTimeField`` group prefetched rows by
``.year``/``.month``/``.day`` of the stored (UTC) value, while stock's
``__year``/``__month``/``__day`` lookups convert to the current time zone in
SQL, so under a non-UTC ``TIME_ZONE`` a row near midnight can be keyed to a
different day than stock and its duplicate missed.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from contextlib import contextmanager, nullcontext, suppress
from functools import cached_property, partial
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import DatabaseError, connection, connections, router, transaction
from django.db.models import (
    BooleanField,
    CheckConstraint,
    CompositePrimaryKey,
    Field,
    ForeignKey,
    IntegerField,
    Model,
    Q,
    UniqueConstraint,
    Value,
    prefetch_related_objects,
)
from django.db.models.expressions import DatabaseDefault
from django.db.models.functions import Coalesce
from django.db.models.sql import Query
from django.forms import Media
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import (
    BaseInlineFormSet,
    BaseModelFormSet,
    ModelChoiceField,
    inlineformset_factory,
    modelformset_factory,
)
from django.utils.translation import gettext as _

from django_formwork.forms import FormworkModelForm, RowRenderMixin
from django_formwork.renderers import FormworkRenderer, formwork_renderer
from django_formwork.widgets._stub import stub_formset, with_query
from django_formwork.widgets.select import cache_cells, column_options, rows_share_choices, share_choices

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator
    from datetime import date as date_type

    from django.forms import BaseFormSet, BoundField
    from django.utils.safestring import SafeString


__all__ = [
    "FormworkBaseInlineFormSet",
    "FormworkBaseModelFormSet",
    "TableRenderMixin",
    "formwork_inlineformset_factory",
    "formwork_modelformset_factory",
]

# A single unique check, as produced by ``Model._get_unique_checks``:
# ``(model_class, (field_name, ...))``.
UniqueCheck = tuple[type["Model"], tuple[str, ...]]
# A single date check: ``(model_class, lookup_type, field, unique_for)``.
DateCheck = tuple[type["Model"], str, str, str]
# Prefetched existence sets per unique check, keyed by
# ``(id(model_class), fields, using)``: each maps a lookup-value tuple to the
# pks of the existing rows that carry those values.
TakenUniques = dict[tuple[int, tuple[str, ...], str | None], dict[tuple[Any, ...], set[Any]]]


class _BatchedUniquenessMixin:
    """Collapse a model formset's O(N x M) uniqueness queries into O(M).

    Mixed in *before* :class:`~django.forms.models.BaseModelFormSet`.  In
    :meth:`full_clean` the children are cleaned with their per-form
    against-the-database checks deferred; the formset then runs one batched
    query per distinct uniqueness check and rebuilds exactly the errors Django
    would have raised per form, before ``validate_max`` / ``validate_min`` and
    ``clean()`` run.  A child validated on its own (``form.is_valid()`` before
    the formset) runs Django's per-form checks itself.

    Batched: classic ``unique`` / ``unique_together`` / ``unique_for_<date>``,
    the field-based ``Meta.constraints`` ``UniqueConstraint`` s that Django treats
    as total (no condition, no expressions, default message, nulls distinct), and
    every ``CheckConstraint`` (all forms in one round trip).  What stays on
    Django's per-form ``constraint.validate()`` path is only what cannot share a
    batched query: conditional or expression ``UniqueConstraint`` s, custom
    violation messages, and constraints touching a ``GeneratedField`` or a
    custom ``db_collation``.  Either way the result is identical to stock; see
    the module docstring for the known collation and time-zone divergences.
    """

    if TYPE_CHECKING:
        forms: list[Any]
        is_bound: bool

    def _construct_form(self, i: int, **kwargs: Any) -> Any:  # noqa: ANN401
        form = super()._construct_form(i, **kwargs)  # type: ignore[misc]
        # Exempts the form from FORMWORK_FORCE_ASYNC: a formset validates and saves synchronously.
        form._formwork_in_formset = True  # noqa: SLF001
        return form

    def full_clean(self) -> None:
        if self.is_bound:
            self._clean_forms_batched()
        super().full_clean()  # type: ignore[misc]

    def _clean_forms_batched(self) -> None:
        """Clean every child, then add its database errors before ``validate_max`` and ``clean()``.

        The phases follow stock ``_post_clean`` (unique checks, then ``Meta.constraints``),
        which keeps the ``__all__`` message order.
        """
        forms = self.forms
        # A plain ModelForm ignores the flag and keeps Django's per-form checks.
        for form in forms:
            form._defer_unique_to_formset = True  # noqa: SLF001
        try:
            for form in forms:
                form.errors  # noqa: B018 (runs the child's full_clean())
        finally:
            for form in forms:
                form._defer_unique_to_formset = False  # noqa: SLF001
        # Deleted children are checked too: stock's _post_clean queries for them
        # as well, and the formset drops their errors.
        deferred = [form for form in forms if getattr(form, "_uniqueness_deferred", False)]
        for form in deferred:
            form._uniqueness_deferred = False  # noqa: SLF001
        self._perform_classic_unique_checks([f for f in deferred if getattr(f, "_validate_unique", False)])
        self._perform_meta_constraints([f for f in deferred if getattr(f, "_validate_constraints", False)])

    # -- collecting the checks -------------------------------------------------

    @staticmethod
    def _is_batchable_unique(constraint: Any, model_class: type[Model]) -> TypeGuard[UniqueConstraint]:  # noqa: ANN401
        """True for the ``UniqueConstraint`` s Django folds into unique checks.

        These are the "total" unique constraints (``Meta.total_unique_constraints``):
        field-based, no condition, no expressions.  We narrow further to the ones
        whose error is byte-for-byte a classic uniqueness error: nulls distinct
        (so a NULL skips the check, as ``_perform_unique_checks`` does) and the
        default violation message (so Django uses ``unique_error_message``).
        Constraints touching a ``GeneratedField`` bail out because stock
        ``UniqueConstraint.validate`` substitutes the field's DB expression where
        the batched lookup would read a value the database has not computed yet;
        a custom ``db_collation`` bails out because the batched replay compares
        values with Python equality, not the column's collation.
        """
        if not (
            isinstance(constraint, UniqueConstraint)
            and constraint.condition is None
            and not constraint.contains_expressions
            and constraint.nulls_distinct is not False
            and constraint.violation_error_message == constraint.default_violation_error_message
        ):
            return False
        fields = [model_class._meta.get_field(name) for name in constraint.fields]  # noqa: SLF001
        return not any(getattr(f, "generated", False) or getattr(f, "db_collation", None) for f in fields)

    def _meta_unique_checks(self, instance: Model, exclude: set[str]) -> list[UniqueCheck]:
        """Batchable ``UniqueConstraint`` s as ``(model_class, fields)`` checks.

        Mirrors how ``_get_unique_checks(include_meta_constraints=True)`` folds
        total unique constraints into the unique-check list, restricted to the
        subset :meth:`_is_batchable_unique` accepts.
        """
        return [
            (model_class, tuple(constraint.fields))
            for model_class, constraints in instance.get_constraints()
            for constraint in constraints
            if self._is_batchable_unique(constraint, model_class)
            and not any(name in exclude for name in constraint.fields)
        ]

    def _perform_classic_unique_checks(self, forms: list[Any]) -> None:
        """Batched stand-in for ``Model.validate_unique`` (phase one).

        Classic ``unique`` / ``unique_together`` / ``unique_for_<date>`` only.
        The field-based ``Meta.constraints`` ``UniqueConstraint`` s are handled in
        :meth:`_perform_meta_constraints` instead, so they keep their place in
        ``Meta`` declaration order (stock validates them via
        ``validate_constraints``, not ``validate_unique``).
        """
        if not forms:
            return

        unique_by_form: dict[Any, list[UniqueCheck]] = {}
        date_by_form: dict[Any, list[DateCheck]] = {}
        for form in forms:
            exclude = form._get_validation_exclusions()  # noqa: SLF001
            unique_checks, date_checks = form.instance._get_unique_checks(exclude=exclude)  # noqa: SLF001
            unique_by_form[form] = list(unique_checks)
            date_by_form[form] = date_checks

        taken = self._prefetch_unique(forms, unique_by_form)
        taken_dates = self._prefetch_dates(forms, date_by_form)

        for form in forms:
            errors: dict[str, list[ValidationError]]
            if taken is None:
                # The batched query failed as one statement (see the
                # DatabaseError note in _prefetch_unique); replay stock's
                # per-form checks, which query one check at a time.
                errors = form.instance._perform_unique_checks(unique_by_form[form])  # noqa: SLF001
            else:
                errors = {}
                self._collect_unique_errors(form, unique_by_form[form], taken, errors)
            if taken_dates is None:
                # Same batched-query fallback as above, for date checks.
                for key, msgs in form.instance._perform_date_checks(date_by_form[form]).items():  # noqa: SLF001
                    errors.setdefault(key, []).extend(msgs)
            else:
                self._collect_date_errors(form, date_by_form[form], taken_dates, errors)
            if errors:
                form._update_errors(ValidationError(errors))  # noqa: SLF001

    def _perform_meta_constraints(self, forms: list[Any]) -> None:
        """Batched stand-in for ``Model.validate_constraints`` (phase two).

        Walks ``get_constraints()`` in ``Meta`` declaration order, exactly as
        stock does, and accumulates each form's errors in that order so the
        ``__all__`` message order is identical even when a check and a unique both
        fail the same row.  Two kinds of verdict are sourced from batched passes
        rather than a query per form: field-based ``UniqueConstraint`` s
        (:meth:`_is_batchable_unique`, prefetched here) and every
        ``CheckConstraint`` (:meth:`_evaluate_batched_checks`).  Whatever neither
        pass can batch (conditional or expression uniques, custom-message
        uniques, generated or custom-collation fields) falls through to a
        per-form ``constraint.validate()``.
        """
        if not forms:
            return

        # One prefetch covering the batchable meta-uniques across every form, so
        # the in-order replay below is pure dict lookups, not N queries.  It
        # runs against the write database, as stock validate_constraints does.
        meta_unique_by_form = {
            form: self._meta_unique_checks(form.instance, form._get_validation_exclusions())  # noqa: SLF001
            for form in forms
        }
        taken = self._prefetch_unique(forms, meta_unique_by_form, for_write=True)
        check_verdicts = self._evaluate_batched_checks(forms)

        for form in forms:
            errors = self._collect_meta_constraint_errors(form, taken, check_verdicts)
            if errors:
                form._update_errors(ValidationError(errors))  # noqa: SLF001

    def _collect_meta_constraint_errors(
        self,
        form: Any,  # noqa: ANN401
        taken: TakenUniques | None,
        check_verdicts: dict[tuple[int, int], bool] | None,
    ) -> dict[str, list[ValidationError]]:
        """One form's ``validate_constraints`` errors, in ``Meta`` order.

        Batchable uniques consult ``taken`` and batched checks consult
        ``check_verdicts``; anything else, including every constraint when a
        batched pass reported ``None``, falls back to the constraint's own
        ``validate()``.  Errors accumulate in iteration order, so a check and a
        unique that both fail land in ``__all__`` exactly as stock orders them.
        """
        instance = form.instance
        exclude = form._get_validation_exclusions()  # noqa: SLF001
        using = router.db_for_write(instance.__class__, instance=instance)
        errors: dict[str, list[ValidationError]] = {}
        for model_class, constraints in instance.get_constraints():
            for constraint in constraints:
                if taken is not None and self._is_batchable_unique(constraint, model_class):
                    # validate() early-returns on an excluded field; mirror that,
                    # otherwise consult the prefetched existence set in this
                    # constraint's Meta position.
                    if not any(name in exclude for name in constraint.fields):
                        self._collect_unique_errors(
                            form,
                            [(model_class, tuple(constraint.fields))],
                            taken,
                            errors,
                            using=using,
                        )
                    continue
                key = (id(form), id(constraint))
                if check_verdicts is not None and key in check_verdicts:
                    # Already evaluated in the batched check pass; rebuild the
                    # exact error CheckConstraint.validate would have raised.
                    if not check_verdicts[key]:
                        error = ValidationError(
                            constraint.get_violation_error_message(),
                            code=constraint.violation_error_code,
                        )
                        errors = self._route_constraint_error(errors, constraint, error)
                    continue
                try:
                    constraint.validate(model_class, instance, exclude=exclude, using=using)
                except ValidationError as error:
                    errors = self._route_constraint_error(errors, constraint, error)
        return errors

    @staticmethod
    def _route_constraint_error(
        errors: dict[str, list[ValidationError]],
        constraint: Any,  # noqa: ANN401
        error: ValidationError,
    ) -> dict[str, list[ValidationError]]:
        """Place a constraint error where ``Model.validate_constraints`` would."""
        if getattr(error, "code", None) == "unique" and len(constraint.fields) == 1:
            errors.setdefault(constraint.fields[0], []).append(error)
        else:
            errors = error.update_error_dict(errors)
        return errors

    # -- CheckConstraints (batched into one round trip) ------------------------

    def _evaluate_batched_checks(self, forms: list[Any]) -> dict[tuple[int, int], bool] | None:
        """Evaluate every batchable ``CheckConstraint`` across all forms at once.

        Returns a ``{(id(form), id(constraint)): satisfied}`` map, or ``None`` to
        tell the caller to fall back to per-form ``constraint.validate()`` (see
        the ``DatabaseError`` note).  Mirrors ``CheckConstraint.validate``: a
        check whose condition references an excluded field is skipped (validate
        would return without error), and a verdict is ``Q.check``'s
        ``execute_sql(...) is not None``.
        """
        jobs: dict[str, list[tuple[tuple[int, int], Any, dict[str, Any]]]] = defaultdict(list)
        for form in forms:
            instance = form.instance
            exclude = form._get_validation_exclusions()  # noqa: SLF001
            using = router.db_for_write(instance.__class__, instance=instance)
            for model_class, constraints in instance.get_constraints():
                for constraint in constraints:
                    if not isinstance(constraint, CheckConstraint):
                        continue
                    if exclude and constraint._expression_refs_exclude(model_class, constraint.condition, exclude):  # type: ignore[attr-defined]  # noqa: SLF001
                        continue
                    against = instance._get_field_expression_map(meta=model_class._meta, exclude=exclude)  # noqa: SLF001
                    jobs[using].append(((id(form), id(constraint)), constraint.condition, against))

        verdicts: dict[tuple[int, int], bool] = {}
        for using, group in jobs.items():
            try:
                satisfied = self._run_batched_checks([(condition, against) for _, condition, against in group], using)
            except DatabaseError:
                # Q.check swallows a DatabaseError per row and treats that row as
                # passing.  A batched failure cannot be attributed per row, so
                # fall back to Django's per-form validate() rather than guess.
                return None
            for (key, _condition, _against), ok in zip(group, satisfied, strict=True):
                verdicts[key] = ok
        return verdicts

    def _run_batched_checks(self, items: list[tuple[Any, dict[str, Any]]], using: str) -> list[bool]:
        """Run all check conditions for one database in a single statement.

        Each condition compiles to the same tableless ``SELECT 1 WHERE ...`` that
        ``Q.check`` would run; we wrap each as a scalar subquery and select them
        side by side, so ``column is not None`` is that check's verdict.
        """
        conn = connections[using]
        fragments: list[str] = []
        params: list[Any] = []
        for condition, against in items:
            sql, sql_params = self._build_check_query(condition, against, using).get_compiler(using=using).as_sql()
            fragments.append(f"({sql})")
            params.extend(sql_params)
        # FROM-less SELECT: valid on PostgreSQL/SQLite, not Oracle. The caller
        # catches the DatabaseError and falls back to per-form validation.
        select = "SELECT " + ", ".join(f"{fragment} AS c{i}" for i, fragment in enumerate(fragments))
        # Match Q.check: isolate the read in a savepoint when already inside a
        # transaction, so a backend error rolls back cleanly.
        atomic = transaction.atomic(using=using) if conn.in_atomic_block else nullcontext()
        with atomic, conn.cursor() as cursor:
            cursor.execute(select, params)
            row = cursor.fetchone()
        return [value is not None for value in row]

    @staticmethod
    def _build_check_query(condition: Any, against: dict[str, Any], using: str) -> Query:  # noqa: ANN401
        """The tableless query ``Q.check`` builds for one condition and row.

        A faithful copy of ``django.db.models.query_utils.Q.check`` up to the
        point of execution, so the compiled SQL is byte-for-byte what stock would
        run; only the transport (batched scalar subqueries) differs.
        """
        query = Query(None)
        for name, value in against.items():
            resolved = value if hasattr(value, "resolve_expression") else Value(value)
            query.add_annotation(resolved, name, select=False)
        query.add_annotation(Value(1), "_check")
        if connections[using].features.supports_comparing_boolean_expr:
            # Coalesce(..., Value(value=True)) is byte-identical to Q.check's
            # literal True (Coalesce wraps non-expressions in Value); spelled out
            # here to keep the boolean out of a positional argument.
            query.add_q(Q(Coalesce(condition, Value(value=True), output_field=BooleanField())))
        else:
            query.add_q(Q(condition))
        return query

    # -- unique / unique_together ---------------------------------------------

    @staticmethod
    def _unique_lookup(instance: Model, model_class: type[Model], fields: tuple[str, ...]) -> tuple[Any, ...] | None:
        """Ordered lookup values for one unique check, or None to skip it.

        Mirrors the per-field skip rules in ``Model._perform_unique_checks``.
        """
        values: list[Any] = []
        for field_name in fields:
            # Unique-check names always resolve to concrete fields (with attname),
            # never reverse relations; the stub can't know that.
            f = instance._meta.get_field(field_name)  # noqa: SLF001
            value = getattr(instance, f.attname)  # type: ignore[union-attr]
            if value is None or (value == "" and connection.features.interprets_empty_strings_as_nulls):
                return None
            if f in model_class._meta.pk_fields and not instance._state.adding:  # noqa: SLF001
                return None
            values.append(value)
        return tuple(values)

    def _prefetch_unique(
        self,
        forms: list[Any],
        unique_by_form: dict[Any, list[UniqueCheck]],
        *,
        for_write: bool = False,
    ) -> TakenUniques | None:
        """Existence sets for every wanted unique lookup, in one query per check.

        ``for_write`` routes each form's lookups to its write database, as stock
        ``validate_constraints`` does for ``Meta.constraints``; the default read
        routing matches stock ``_perform_unique_checks``.  Returns ``None`` to
        tell the caller to fall back to Django's per-form path (see the
        ``DatabaseError`` note).
        """
        wanted: dict[tuple[int, tuple[str, ...], str | None], tuple[type[Model], tuple[str, ...], str | None]] = {}
        rows_wanted: dict[tuple[int, tuple[str, ...], str | None], set[tuple[Any, ...]]] = defaultdict(set)
        for form in forms:
            instance = form.instance
            using = router.db_for_write(instance.__class__, instance=instance) if for_write else None
            for model_class, fields in unique_by_form[form]:
                lookup = self._unique_lookup(instance, model_class, fields)
                if lookup is None:
                    continue
                key = (id(model_class), fields, using)
                wanted[key] = (model_class, fields, using)
                rows_wanted[key].add(lookup)

        taken: TakenUniques = {}
        for key, (model_class, fields, using) in wanted.items():
            query = Q()
            for lookup in rows_wanted[key]:
                query |= Q(**dict(zip(fields, lookup, strict=True)))
            manager = model_class._default_manager  # noqa: SLF001
            queryset = (manager.using(using) if using is not None else manager).filter(query)
            existing: dict[tuple[Any, ...], set[Any]] = defaultdict(set)
            # Isolate the read in a savepoint when already inside a transaction,
            # so a backend error rolls back cleanly (as _run_batched_checks does).
            atomic = (
                transaction.atomic(using=queryset.db) if connections[queryset.db].in_atomic_block else nullcontext()
            )
            try:
                with atomic:
                    for row in queryset.values_list(*fields, "pk"):
                        existing[tuple(row[:-1])].add(row[-1])
            except DatabaseError:
                # One big OR can exceed backend parameter limits; signal fallback.
                return None
            taken[key] = existing
        return taken

    def _collect_unique_errors(
        self,
        form: Any,  # noqa: ANN401
        checks: list[UniqueCheck],
        taken: TakenUniques,
        errors: dict[str, list[ValidationError]],
        using: str | None = None,
    ) -> None:
        instance = form.instance
        for model_class, fields in checks:
            lookup = self._unique_lookup(instance, model_class, fields)
            if lookup is None:
                continue
            pks = set(taken.get((id(model_class), fields, using), {}).get(lookup, set()))
            if not instance._state.adding and instance._is_pk_set(model_class._meta):  # noqa: SLF001
                pks.discard(instance._get_pk_val(model_class._meta))  # noqa: SLF001
            if pks:
                key = fields[0] if len(fields) == 1 else NON_FIELD_ERRORS
                errors.setdefault(key, []).append(instance.unique_error_message(model_class, fields))

    # -- unique_for_<date/year/month> -----------------------------------------

    @staticmethod
    def _date_key(lookup_type: str, field_value: Any, date: date_type) -> tuple[Any, ...]:  # noqa: ANN401
        if lookup_type == "date":
            return (field_value, date.year, date.month, date.day)
        return (field_value, getattr(date, lookup_type))

    @staticmethod
    def _date_field_attname(model_class: type[Model], field: str) -> str:
        """Raw column attribute (``region_id`` for a FK), as the prefetch reads it."""
        return model_class._meta.get_field(field).attname  # type: ignore[union-attr]  # noqa: SLF001

    def _prefetch_dates(
        self,
        forms: list[Any],
        date_by_form: dict[Any, list[DateCheck]],
    ) -> dict[tuple[int, str, str, str], dict[tuple[Any, ...], set[Any]]] | None:
        wanted: dict[tuple[int, str, str, str], DateCheck] = {}
        rows_wanted: dict[tuple[int, str, str, str], list[tuple[Any, date_type]]] = defaultdict(list)
        for form in forms:
            for check in date_by_form[form]:
                model_class, _lookup_type, field, unique_for = check
                date = getattr(form.instance, unique_for)
                if date is None:
                    continue
                key = (id(model_class), check[1], field, unique_for)
                wanted[key] = check
                rows_wanted[key].append((getattr(form.instance, self._date_field_attname(model_class, field)), date))

        taken: dict[tuple[int, str, str, str], dict[tuple[Any, ...], set[Any]]] = {}
        for key, (model_class, lookup_type, field, unique_for) in wanted.items():
            attname = self._date_field_attname(model_class, field)
            query = Q()
            for field_value, date in rows_wanted[key]:
                if lookup_type == "date":
                    query |= Q(
                        **{
                            attname: field_value,
                            f"{unique_for}__day": date.day,
                            f"{unique_for}__month": date.month,
                            f"{unique_for}__year": date.year,
                        },
                    )
                else:
                    query |= Q(**{attname: field_value, f"{unique_for}__{lookup_type}": getattr(date, lookup_type)})
            existing: dict[tuple[Any, ...], set[Any]] = defaultdict(set)
            queryset = model_class._default_manager.filter(query)  # noqa: SLF001
            # Savepoint-isolate the read, as the sibling prefetch paths do.
            atomic = (
                transaction.atomic(using=queryset.db) if connections[queryset.db].in_atomic_block else nullcontext()
            )
            try:
                with atomic:
                    for field_value, date, pk in queryset.values_list(attname, unique_for, "pk"):
                        existing[self._date_key(lookup_type, field_value, date)].add(pk)
            except DatabaseError:
                # One big OR can exceed backend parameter limits; signal fallback.
                return None
            taken[key] = existing
        return taken

    def _collect_date_errors(
        self,
        form: Any,  # noqa: ANN401
        checks: list[DateCheck],
        taken: dict[tuple[int, str, str, str], dict[tuple[Any, ...], set[Any]]],
        errors: dict[str, list[ValidationError]],
    ) -> None:
        instance = form.instance
        for check in checks:
            model_class, lookup_type, field, unique_for = check
            date = getattr(instance, unique_for)
            if date is None:
                continue
            key = (id(model_class), lookup_type, field, unique_for)
            field_value = getattr(instance, self._date_field_attname(model_class, field))
            row_key = self._date_key(lookup_type, field_value, date)
            pks = set(taken.get(key, {}).get(row_key, set()))
            if not instance._state.adding and instance._is_pk_set():  # noqa: SLF001
                pks.discard(instance.pk)
            if pks:
                errors.setdefault(field, []).append(instance.date_error_message(lookup_type, field, unique_for))


def initial_many_to_many(form_class: type[Any]) -> list[str]:
    """The many-to-many fields whose values a model form reads from its instance, as ``model_to_dict`` picks them."""
    meta = form_class._meta  # noqa: SLF001
    return [
        field.name
        for field in meta.model._meta.many_to_many  # noqa: SLF001
        if field.editable
        and (meta.fields is None or field.name in meta.fields)
        and not (meta.exclude and field.name in meta.exclude)
    ]


class _RowField(ModelChoiceField):
    """The hidden primary key of a formset's row, found among the rows the formset loads for all its forms."""

    def __init__(
        self,
        queryset: Any,  # noqa: ANN401
        *,
        rows: Callable[[Any], dict[Any, Model]],
        key: Callable[[Any], Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(queryset, **kwargs)
        self.rows = rows
        self.key = key

    def to_python(self, value: Any) -> Any:  # noqa: ANN401
        queryset: Any = self.queryset
        if value not in self.empty_values and not isinstance(value, queryset.model):
            # A key the forms did not post as the formset reads them gets Django's own lookup.
            with suppress(KeyError, TypeError, ValidationError):
                return self.rows(queryset)[self.key(value)]
        return super().to_python(value)


class _PostedChoices:
    """The rows that the forms of a formset posted for one relation, by their value, loaded once for all forms."""

    def __init__(self, queryset: Any, key: str, values: Callable[[], set[str]]) -> None:  # noqa: ANN401
        self.queryset = queryset
        self.key = key
        self.values = values

    @cached_property
    def rows(self) -> dict[str, Model]:
        opts = self.queryset.model._meta  # noqa: SLF001
        key = opts.pk if self.key == "pk" else opts.get_field(self.key)
        low, high = (
            connections[self.queryset.db].ops.integer_field_range(key.get_internal_type())
            if isinstance(key, IntegerField)
            else (None, None)
        )
        # Values that Django's own lookup never sends to the database keep that lookup.
        # ``__in`` would send an out-of-range integer, and PostgreSQL rejects a null character.
        values = set()
        for value in self.values():
            with suppress(ValueError, TypeError, ValidationError):
                prepared = key.get_prep_value(value)
                out_of_range = isinstance(prepared, int) and (
                    (low is not None and prepared < low) or (high is not None and prepared > high)
                )
                if not out_of_range and "\x00" not in value:
                    values.add(value)
        if not values:
            return {}
        return {str(getattr(row, self.key)): row for row in self.queryset.filter(**{f"{self.key}__in": values})}

    def to_python(self, field: ModelChoiceField, value: Any) -> Any:  # noqa: ANN401
        """Django's ``to_python``, which finds a posted value among ``rows`` instead of its own query."""
        if isinstance(value, str) and value not in field.empty_values:
            field.validate_no_null_characters(value)
            if (row := self.rows.get(value)) is not None:
                # Each form gets an instance of its own, as from its own query.
                return copy.copy(row)
        return type(field).to_python(field, value)


class _ForeignKeyChecks:
    """Django's model-level check that a foreign key names a row, with one query per relation for all forms.

    A row that the batched query does not return, and a foreign key of a subclass that changes
    its own ``validate()`` or ``clean()``, gets Django's own query and error.
    """

    def __init__(self, posted: Callable[[str], _PostedChoices | None]) -> None:
        self.posted = posted
        self.found: dict[tuple[Field[Any, Any], str], set[Any]] = {}

    @contextmanager
    def serving(self, instance: Model) -> Generator[None]:
        """Let ``instance.full_clean()`` look up its foreign keys among the rows of all forms."""
        # The batch stands in for Django's own clean_fields() only; an override, such as the
        # admin import's on each instance, keeps its own lookups.
        if type(instance).clean_fields is not Model.clean_fields or "clean_fields" in vars(instance):
            yield
            return
        instance.clean_fields = partial(self.clean_fields, instance)  # type: ignore[method-assign]
        try:
            yield
        finally:
            del instance.clean_fields

    def clean_fields(self, instance: Model, exclude: Collection[str] | None = None) -> None:
        """Django's ``Model.clean_fields()``, with :meth:`clean` for ``field.clean()``."""
        if exclude is None:
            exclude = set()
        errors = {}
        for f in instance._meta.fields:  # noqa: SLF001
            if f.name in exclude or f.generated:
                continue
            raw_value = getattr(instance, f.attname)
            if f.blank and raw_value in f.empty_values:
                continue
            if isinstance(raw_value, DatabaseDefault):
                continue
            try:
                setattr(instance, f.attname, self.clean(f, raw_value, instance))
            except ValidationError as e:
                errors[f.name] = e.error_list
        if errors:
            raise ValidationError(errors)

    def clean(self, field: Field[Any, Any], raw_value: Any, instance: Model) -> Any:  # noqa: ANN401
        """``field.clean()``, which skips the query of ``ForeignKey.validate()`` for a row the batch found."""
        if not (
            isinstance(field, ForeignKey)
            and type(field).clean is Field.clean
            and type(field).validate is ForeignKey.validate
            and not field.remote_field.parent_link
            and not callable(field.remote_field.limit_choices_to)
        ):
            return field.clean(raw_value, instance)
        value = field.to_python(raw_value)
        if value is None or value not in self._found(field, instance):
            return field.clean(raw_value, instance)
        super(ForeignKey, field).validate(value, instance)
        field.run_validators(value)
        return value

    def _found(self, field: ForeignKey[Any, Any], instance: Model) -> set[Any]:
        """The values of ``field`` that the forms posted and that name a row ``ForeignKey.validate()`` accepts."""
        target = field.remote_field.model
        using = router.db_for_read(target, instance=instance)
        if (field, using) not in self.found:
            posted = self.posted(field.name)
            values = {getattr(row, field.target_field.attname) for row in posted.rows.values()} if posted else set()
            rows = target._base_manager.using(using).filter(**{f"{field.remote_field.field_name}__in": values})  # noqa: SLF001
            rows = rows.complex_filter(field.get_limit_choices_to())
            self.found[field, using] = set(rows.values_list(field.target_field.attname, flat=True)) if values else set()
        return self.found[field, using]


def _has_unique_key(field: ModelChoiceField) -> bool:
    """Whether a value names at most one row, so that one query can find the rows of all values."""
    queryset: Any = field.queryset
    opts = queryset.model._meta  # noqa: SLF001
    key = opts.pk if field.to_field_name is None else opts.get_field(field.to_field_name)
    return key.unique and not isinstance(key, CompositePrimaryKey)


class _LoadedAtOnceMixin:
    """Load what the forms of a model formset read from the database for all forms at once.

    Django runs these once per form: the posted primary keys, the many-to-many initials and the posted relations.
    """

    if TYPE_CHECKING:
        _pk_field: Any
        data: Any
        files: Any
        form: type[Any]
        model: Any
        get_queryset: Callable[[], Any]
        initial_form_count: Callable[[], int]
        total_form_count: Callable[[], int]
        _get_to_python: Callable[[Any], Callable[[Any], Any]]

        def add_prefix(self, index: int | str) -> str: ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._many_to_many_loaded = False
        self._posted_rows: dict[str, dict[Any, Model]] = {}
        self._posted_choices: dict[str, _PostedChoices | None] = {}
        self._foreign_key_checks = _ForeignKeyChecks(self._posted_choices.get)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i: int, **kwargs: Any) -> Any:  # noqa: ANN401
        # The saved rows the first one comes from; Django loads them all at that point too.
        if i < self.initial_form_count() and not self._many_to_many_loaded:
            self._many_to_many_loaded = True
            if names := initial_many_to_many(self.form):
                prefetch_related_objects(list(self.get_queryset()), *names)
        form = super()._construct_form(i, **kwargs)  # type: ignore[misc]
        if form.is_bound:
            # A FormworkModelForm checks its foreign keys with these; a plain ModelForm ignores them.
            form._foreign_key_checks = self._foreign_key_checks  # noqa: SLF001
        return form

    def add_fields(self, form: Any, index: int | None) -> None:  # noqa: ANN401
        name = self.model._meta.pk.name  # noqa: SLF001
        before = form.fields.get(name)
        super().add_fields(form, index)  # type: ignore[misc]
        field = form.fields.get(name)
        if form.is_bound and field is not before and type(field) is ModelChoiceField:
            form.fields[name] = _RowField(
                field.queryset,
                rows=self._rows,
                key=self._get_to_python(self._pk_field),
                initial=field.initial,
                required=field.required,
                widget=field.widget,
            )
        if form.is_bound:
            for field_name, choice_field in form.fields.items():
                if choices := self._choices_posted_for(field_name, choice_field):
                    choice_field.to_python = partial(choices.to_python, choice_field)

    def _choices_posted_for(self, name: str, field: Any) -> _PostedChoices | None:  # noqa: ANN401
        """The rows the forms posted for a relation field, or None where each form keeps Django's query."""
        if name not in self._posted_choices:
            shared = (
                isinstance(field, ModelChoiceField)
                and type(field).to_python is ModelChoiceField.to_python
                and field.queryset is not None
                and not field.disabled
                and _has_unique_key(field)
                and rows_share_choices(cast("Any", self), field)
            )
            self._posted_choices[name] = (
                _PostedChoices(field.queryset, field.to_field_name or "pk", partial(self._posted_values, name, field))
                if shared
                else None
            )
        return self._posted_choices[name]

    def _posted_values(self, name: str, field: Any) -> set[str]:  # noqa: ANN401
        values = set()
        for i in range(self.total_form_count()):
            value = field.widget.value_from_datadict(self.data, self.files, f"{self.add_prefix(i)}-{name}")
            if isinstance(value, str) and value not in field.empty_values:
                values.add(value)
        return values

    def _rows(self, queryset: Any) -> dict[Any, Model]:  # noqa: ANN401
        """The rows of the primary keys the forms posted, by key, with one query per database."""
        if queryset.db not in self._posted_rows:
            to_python = self._get_to_python(self._pk_field)
            keys = set()
            for i in range(self.total_form_count()):
                with suppress(TypeError, ValidationError):
                    keys.add(to_python(self.data.get(f"{self.add_prefix(i)}-{self._pk_field.name}")))
            keys.discard(None)
            self._posted_rows[queryset.db] = queryset.in_bulk(keys)
        return self._posted_rows[queryset.db]


class TableRenderMixin:
    """Add ``as_rows()`` to a formset: render it as one editable ``<table>``."""

    template_name_table = "formwork/tables/table.html"
    #: Add another appends a row. A model formset with ``edit_only=True`` has none either way.
    can_add = True

    if TYPE_CHECKING:
        form: type[Any]
        forms: list[Any]
        empty_form: Any
        can_delete: bool
        renderer: Any
        render: Any
        initial_form_count: Any

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give the form of a formset class the row methods when it has none, as a plain ``ModelForm``."""
        super().__init_subclass__(**kwargs)
        form = cls.__dict__.get("form")
        if form is not None and not issubclass(form, RowRenderMixin):
            cls.form = type(form.__name__, (RowRenderMixin, form), {})

    def as_rows(self, save_url: str = "", *, flush: bool = False, cell_url: str = "") -> SafeString:
        return self.render_table(self.get_table_context(save_url=save_url, flush=flush, cell_url=cell_url))

    def render_table(self, context: dict[str, Any]) -> SafeString:
        """The table template with ``context``, a dict from ``get_table_context()``."""
        return self.render(self.template_name_table, context, formwork_renderer(self.renderer))

    def row_url(self, form: Any) -> str:  # noqa: ANN401, ARG002
        """The page of the row of ``form``, which the row links in its last column; ``""`` for none."""
        return ""

    def row_details(self, form: Any) -> str | None:  # noqa: ANN401, ARG002
        """What opens under the row of ``form`` when the row is clicked; ``None`` for none.

        A ``SafeString``, such as ``render_to_string()`` or ``format_html()`` returns, shows as HTML, any other as text.
        A table with ``save_url`` has none: its rows re-render one by one, without the formset.
        """
        return None

    def get_table_context(self, *, save_url: str = "", flush: bool = False, cell_url: str = "") -> dict[str, Any]:
        """The table template's context: the headers, a row context per form, and the row that Add another copies.

        With ``save_url``, each row saves by itself and the table has no Add another, Remove or Delete.
        With ``cell_url``, the selects, combo boxes and date pickers of saved rows render as stubs that load from it.
        """
        formset = cast("BaseFormSet[Any]", self)
        # The rows load the choices of a relation once, whether they render in full or as stubs.
        share_choices(formset)
        if cell_url:
            stub_formset(formset, lambda name: with_query(cell_url, field=name))
        option_lists = column_options(formset)
        cache_cells(formset)
        can_add = not save_url and self.can_add and not getattr(self, "edit_only", False)
        can_delete = not save_url and self.can_delete
        initial = self.initial_form_count()
        links = [self.row_url(form) for form in self.forms]
        details = [None if save_url else self.row_details(form) for form in self.forms]
        expandable = any(html is not None for html in details)
        new_rows = len(self.forms) > initial
        actions = not save_url and (can_add or can_delete or new_rows or any(links))
        rows = [
            form.get_row_context(
                new=index >= initial,
                can_delete=can_delete,
                save_url=save_url,
                actions=actions,
                link=links[index],
                details=details[index],
                expandable=expandable,
            )
            for index, form in enumerate(self.forms)
        ]
        empty_form = self.empty_form
        empty_row = empty_form.get_row_context(new=True, actions=actions, expandable=expandable) if can_add else None
        model = getattr(self, "model", None)
        opts = model._meta if model is not None else None  # noqa: SLF001
        # The texts with a name are built here, not in the template: makemessages finds no Jinja trans block.
        names = {
            "empty_text": _("No %(name)s yet.") % {"name": opts.verbose_name_plural if opts is not None else _("rows")},
            "add_text": _("Add another %(name)s") % {"name": opts.verbose_name if opts is not None else _("row")},
        }
        return {
            "formset": self,
            "headers": [
                _header(bound_field)
                for bound_field in empty_form.visible_fields()
                if bound_field.name != DELETION_FIELD_NAME
            ],
            "rows": rows,
            "empty_row": empty_row,
            "actions": actions and (bool(rows) or empty_row is not None),
            "expandable": expandable,
            "flush": flush,
            "footer": "",
            "option_lists": option_lists,
            **names,
        }

    @property
    def media(self) -> Media:
        from django_formwork.widgets._base import _ModuleScript

        return super().media + Media(js=[_ModuleScript("formwork/tables.js")])  # type: ignore[misc]


def _header(bound_field: BoundField) -> dict[str, Any]:
    """A column's header: the label, a red asterisk for a required field, and the help text."""
    shows_value = bound_field.field.disabled
    return {
        "name": bound_field.name,
        "label": bound_field.label,
        "required": getattr(bound_field, "is_mandatory", bound_field.field.required) and not shows_value,
        "help_text": bound_field.help_text,
        # A boxed widget sets its value in from the cell's edge, and the header lines up with the value.
        "indent": not shows_value
        and getattr(bound_field.field.widget, "input_type", None) not in {"checkbox", "radio"},
    }


class FormworkBaseModelFormSet(TableRenderMixin, _BatchedUniquenessMixin, _LoadedAtOnceMixin, BaseModelFormSet):
    """Django's ``BaseModelFormSet`` with one uniqueness query per distinct check, not one per form.

    It also loads the posted rows and the many-to-many values of all forms at once. Use
    :func:`formwork_modelformset_factory` to build a concrete subclass.
    """


def formwork_modelformset_factory(
    model: type[Model],
    *,
    form: type[Any] = FormworkModelForm,
    formset: type[FormworkBaseModelFormSet] = FormworkBaseModelFormSet,
    renderer: Any = None,  # noqa: ANN401
    **kwargs: Any,
) -> type[FormworkBaseModelFormSet]:
    """Like ``modelformset_factory`` but batched and DaisyUI-styled.

    Defaults ``form`` to :class:`~django_formwork.forms.FormworkModelForm` and
    ``formset`` to :class:`FormworkBaseModelFormSet`, and renders with
    :class:`~django_formwork.renderers.FormworkRenderer` unless a ``renderer`` is
    given.  All other arguments are forwarded to ``modelformset_factory``.
    """
    return cast(
        "type[FormworkBaseModelFormSet]",
        modelformset_factory(
            model,
            form=form,
            formset=formset,
            renderer=renderer if renderer is not None else FormworkRenderer(),
            **kwargs,
        ),
    )


class FormworkBaseInlineFormSet(TableRenderMixin, _BatchedUniquenessMixin, _LoadedAtOnceMixin, BaseInlineFormSet):
    """Inline formset with batched uniqueness validation.

    The same batching as :class:`FormworkBaseModelFormSet`, including the
    per-parent ``unique_together`` checks that inline formsets rely on (the
    foreign key is set on each child instance before validation, so it is part
    of the batched lookup).  Use :func:`formwork_inlineformset_factory`.
    """


def formwork_inlineformset_factory(
    parent_model: type[Model],
    model: type[Model],
    *,
    form: type[Any] = FormworkModelForm,
    formset: type[FormworkBaseInlineFormSet] = FormworkBaseInlineFormSet,
    renderer: Any = None,  # noqa: ANN401
    **kwargs: Any,
) -> type[FormworkBaseInlineFormSet]:
    """Like ``inlineformset_factory`` but batched and DaisyUI-styled.

    Defaults ``form`` to :class:`~django_formwork.forms.FormworkModelForm` and
    ``formset`` to :class:`FormworkBaseInlineFormSet`, and renders with
    :class:`~django_formwork.renderers.FormworkRenderer` unless a ``renderer`` is
    given.  All other arguments are forwarded to ``inlineformset_factory``.
    """
    return cast(
        "type[FormworkBaseInlineFormSet]",
        inlineformset_factory(
            parent_model,
            model,
            form=form,
            formset=formset,
            renderer=renderer if renderer is not None else FormworkRenderer(),
            **kwargs,
        ),
    )
