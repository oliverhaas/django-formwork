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
defer its uniqueness check (see
:class:`~django_formwork.forms.FormworkModelForm`), then replays Django's own
``_perform_unique_checks`` / ``_perform_date_checks`` against a single prefetched
result set per check.  The validation outcome is identical to stock Django: same
errors, same messages, same placement (field key vs ``__all__``); only the query
count changes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import connection
from django.db.models import Q
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


class _BatchedUniquenessMixin:
    """Collapse a model formset's O(N x M) uniqueness queries into O(M).

    Mixed in *before* :class:`~django.forms.models.BaseModelFormSet`.  Children
    are marked to defer their per-form uniqueness check; the formset then runs
    one batched query per distinct check in :meth:`validate_unique` and rebuilds
    exactly the errors Django would have raised per form.
    """

    if TYPE_CHECKING:
        forms: list[Any]
        deleted_forms: list[Any]

    def _construct_form(self, i: int, **kwargs: Any) -> Any:  # noqa: ANN401
        form = super()._construct_form(i, **kwargs)  # type: ignore[misc]
        # Honored by FormworkModelForm. A plain ModelForm ignores it and keeps
        # Django's per-form behavior (still correct, just not batched).
        form._defer_unique_to_formset = True  # noqa: SLF001
        return form

    def validate_unique(self) -> None:
        # Reproduce each child's against-the-database uniqueness errors in one
        # batched pass *before* the in-memory cross-form dedup, so the dedup's
        # ``valid_forms`` filter sees the same forms stock Django would.
        self._perform_batched_unique_checks()
        super().validate_unique()  # type: ignore[misc]

    # -- collecting the checks -------------------------------------------------

    def _forms_to_check(self) -> list[Any]:
        deleted = set(self.deleted_forms)
        return [
            form
            for form in self.forms
            # ``_validate_unique`` is True only once a form's clean() ran, i.e.
            # the same forms whose ``_post_clean`` would have queried in stock.
            if getattr(form, "_validate_unique", False)
            and getattr(form, "_defer_unique_to_formset", False)
            and form not in deleted
        ]

    def _perform_batched_unique_checks(self) -> None:
        forms = self._forms_to_check()
        if not forms:
            return

        unique_by_form: dict[Any, list[UniqueCheck]] = {}
        date_by_form: dict[Any, list[DateCheck]] = {}
        for form in forms:
            exclude = form._get_validation_exclusions()  # noqa: SLF001
            # ``include_meta_constraints`` is left False: classic unique /
            # unique_together / unique_for_<date> only. Meta UniqueConstraints
            # keep Django's per-form ``validate_constraints`` path untouched.
            unique_checks, date_checks = form.instance._get_unique_checks(exclude=exclude)  # noqa: SLF001
            unique_by_form[form] = unique_checks
            date_by_form[form] = date_checks

        taken = self._prefetch_unique(forms, unique_by_form)
        taken_dates = self._prefetch_dates(forms, date_by_form)

        for form in forms:
            errors: dict[str, list[ValidationError]] = {}
            self._collect_unique_errors(form, unique_by_form[form], taken, errors)
            self._collect_date_errors(form, date_by_form[form], taken_dates, errors)
            if errors:
                form._update_errors(ValidationError(errors))  # noqa: SLF001

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
    ) -> dict[tuple[int, tuple[str, ...]], dict[tuple[Any, ...], set[Any]]]:
        wanted: dict[tuple[int, tuple[str, ...]], UniqueCheck] = {}
        rows_wanted: dict[tuple[int, tuple[str, ...]], set[tuple[Any, ...]]] = defaultdict(set)
        for form in forms:
            for model_class, fields in unique_by_form[form]:
                lookup = self._unique_lookup(form.instance, model_class, fields)
                if lookup is None:
                    continue
                key = (id(model_class), fields)
                wanted[key] = (model_class, fields)
                rows_wanted[key].add(lookup)

        taken: dict[tuple[int, tuple[str, ...]], dict[tuple[Any, ...], set[Any]]] = {}
        for key, (model_class, fields) in wanted.items():
            query = Q()
            for lookup in rows_wanted[key]:
                query |= Q(**dict(zip(fields, lookup, strict=True)))
            existing: dict[tuple[Any, ...], set[Any]] = defaultdict(set)
            for row in model_class._default_manager.filter(query).values_list(*fields, "pk"):  # noqa: SLF001
                existing[tuple(row[:-1])].add(row[-1])
            taken[key] = existing
        return taken

    def _collect_unique_errors(
        self,
        form: Any,  # noqa: ANN401
        checks: list[UniqueCheck],
        taken: dict[tuple[int, tuple[str, ...]], dict[tuple[Any, ...], set[Any]]],
        errors: dict[str, list[ValidationError]],
    ) -> None:
        instance = form.instance
        for model_class, fields in checks:
            lookup = self._unique_lookup(instance, model_class, fields)
            if lookup is None:
                continue
            pks = set(taken.get((id(model_class), fields), {}).get(lookup, set()))
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
