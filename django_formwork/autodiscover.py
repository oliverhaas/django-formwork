"""Import every app's ``forms`` module so search endpoints self-register.

Search-capable widgets register their endpoints in the form metaclass at
class-definition time (see :mod:`django_formwork.registry`).  That only happens
once the form module is actually imported.  A worker that never imports a given
``forms`` module would return 404 for its search endpoints, so
:meth:`FormworkConfig.ready` calls :func:`autodiscover_forms` to import them all
up front, in every process.
"""

from __future__ import annotations

from django.utils.module_loading import autodiscover_modules

__all__ = ["autodiscover_forms"]


def autodiscover_forms() -> None:
    """Import the ``forms`` submodule of every installed app."""
    autodiscover_modules("forms")
