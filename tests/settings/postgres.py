"""Django settings for the suite on PostgreSQL; libpq reads ``PGHOST``, ``PGUSER`` and ``PGPASSWORD``."""

from .base import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "formwork",
    },
}
