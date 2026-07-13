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

from collections import defaultdict
from contextlib import nullcontext
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import DatabaseError, connection, connections, router, transaction
from django.db.models import BooleanField, CheckConstraint, Q, UniqueConstraint, Value
from django.db.models.functions import Coalesce
from django.db.models.sql import Query
from django.forms.models import (
    BaseInlineFormSet,
    BaseModelFormSet,
    inlineformset_factory,
    modelformset_factory,
)

from django_formwork.forms import FormworkModelForm
from django_formwork.renderers import FormworkRenderer

if TYPE_CHECKING:
    from datetime import date as date_type

    from django.db.models import Model

__all__ = [
    "FormworkBaseInlineFormSet",
    "FormworkBaseModelFormSet",
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

    Mixed in *before* :class:`~django.forms.models.BaseModelFormSet`.  Children
    are told to defer their per-form against-the-database checks; the formset
    then runs one batched query per distinct uniqueness check in
    :meth:`validate_unique` and rebuilds exactly the errors Django would have
    raised per form.

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
        deleted_forms: list[Any]

    def _construct_form(self, i: int, **kwargs: Any) -> Any:  # noqa: ANN401
        form = super()._construct_form(i, **kwargs)  # type: ignore[misc]
        # Honored by FormworkModelForm, which then sets ``_uniqueness_deferred``.
        # A plain ModelForm ignores it and keeps Django's per-form behavior
        # (still correct, just not batched).
        form._defer_unique_to_formset = True  # noqa: SLF001
        return form

    def validate_unique(self) -> None:
        # Reproduce each deferred child's against-the-database errors before the
        # in-memory cross-form dedup, so the dedup's ``valid_forms`` filter sees
        # the same forms stock Django would.  The two phases and their order
        # mirror stock ``_post_clean``: ``validate_unique`` (classic unique /
        # date checks) first, then ``validate_constraints`` (``Meta.constraints``
        # in declaration order).  Keeping them separate is what preserves the
        # message order when a check and a unique both land in ``__all__``.
        forms = self._forms_to_check()
        self._perform_classic_unique_checks([f for f in forms if getattr(f, "_validate_unique", False)])
        self._perform_meta_constraints([f for f in forms if getattr(f, "_validate_constraints", False)])
        super().validate_unique()  # type: ignore[misc]

    # -- collecting the checks -------------------------------------------------

    def _forms_to_check(self) -> list[Any]:
        deleted = set(self.deleted_forms)
        # ``_uniqueness_deferred`` is set by FormworkModelForm only after its
        # clean() ran and only when it actually skipped its own checks, i.e. the
        # same forms whose ``_post_clean`` would have queried in stock.
        return [form for form in self.forms if getattr(form, "_uniqueness_deferred", False) and form not in deleted]

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
        pass can batch -- conditional or expression uniques, custom-message
        uniques, generated or custom-collation fields -- falls through to a
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
                # One OR-of-all-forms statement can fail where stock's per-form
                # lookups succeed (e.g. backend parameter limits on a very large
                # formset); fall back to Django's per-form path rather than 500.
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

    def _prefetch_dates(
        self,
        forms: list[Any],
        date_by_form: dict[Any, list[DateCheck]],
    ) -> dict[tuple[int, str, str, str], dict[tuple[Any, ...], set[Any]]]:
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
                rows_wanted[key].append((getattr(form.instance, field), date))

        taken: dict[tuple[int, str, str, str], dict[tuple[Any, ...], set[Any]]] = {}
        for key, (model_class, lookup_type, field, unique_for) in wanted.items():
            query = Q()
            for field_value, date in rows_wanted[key]:
                if lookup_type == "date":
                    query |= Q(
                        **{
                            field: field_value,
                            f"{unique_for}__day": date.day,
                            f"{unique_for}__month": date.month,
                            f"{unique_for}__year": date.year,
                        },
                    )
                else:
                    query |= Q(**{field: field_value, f"{unique_for}__{lookup_type}": getattr(date, lookup_type)})
            existing: dict[tuple[Any, ...], set[Any]] = defaultdict(set)
            for field_value, date, pk in model_class._default_manager.filter(query).values_list(  # noqa: SLF001
                field,
                unique_for,
                "pk",
            ):
                existing[self._date_key(lookup_type, field_value, date)].add(pk)
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
            row_key = self._date_key(lookup_type, getattr(instance, field), date)
            pks = set(taken.get(key, {}).get(row_key, set()))
            if not instance._state.adding and instance._is_pk_set():  # noqa: SLF001
                pks.discard(instance.pk)
            if pks:
                errors.setdefault(field, []).append(instance.date_error_message(lookup_type, field, unique_for))


class FormworkBaseModelFormSet(_BatchedUniquenessMixin, BaseModelFormSet):
    """Model formset with batched uniqueness validation.

    Behaves exactly like Django's ``BaseModelFormSet`` but issues one
    uniqueness query per distinct check instead of one per form.  Use
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


class FormworkBaseInlineFormSet(_BatchedUniquenessMixin, BaseInlineFormSet):
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
