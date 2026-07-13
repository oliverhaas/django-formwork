"""Opinionated abstract model base.

:class:`FormworkModel` mixes in :class:`filthyfields.DirtyFieldsMixin` so
``self.get_dirty_fields()`` is available, and adds :meth:`fields_dirty`
sugar for use inside ``model.clean()`` cross-field rules.

Pair with ``FormworkModelForm(Meta.validate_dirty_only=True)`` to skip
field-level and constraint validation for fields the user did not change.
"""

from __future__ import annotations

from django.db import models
from filthyfields import DirtyFieldsMixin

__all__ = ["FormworkModel"]


class FormworkModel(DirtyFieldsMixin, models.Model):
    """Abstract base model with dirty-field tracking.

    Use as the base for any model you want to pair with
    ``validate_dirty_only=True`` on a ``FormworkModelForm``.
    """

    class Meta:
        abstract = True

    def fields_dirty(self, *names: str) -> bool:
        """True if any of ``names`` changed since the instance was loaded.

        ForeignKey changes are detected too; a relation can be named by its
        field name (``author``) or its attname (``author_id``).  New instances
        (``_state.adding=True``) always return ``True`` so ``model.clean()``
        cross-field rules fire fully on create.
        """
        if self._state.adding:
            return True
        dirty = set(self.get_dirty_fields(check_relationship=True))
        dirty |= {f.attname for f in self._meta.concrete_fields if f.name in dirty}
        return bool(set(names) & dirty)
