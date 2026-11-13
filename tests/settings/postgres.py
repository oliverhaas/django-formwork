"""Django settings for the suite on PostgreSQL; libpq reads ``PGHOST``, ``PGUSER`` and ``PGPASSWORD``."""

from .base import *  # noqa: F403
from .base import INSTALLED_APPS

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "formwork",
    },
}

# The admin's pghistory backend needs PostgreSQL triggers.
INSTALLED_APPS = [*INSTALLED_APPS, "pgtrigger", "pghistory", "history_app"]
