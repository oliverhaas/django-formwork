"""Settings for browsing the admin demo.

Usage:
    PYTHONPATH=tests uv run django-admin runserver --settings=admin_app.settings
"""

from settings.base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "admin_app.demo_urls"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "admin_demo.sqlite3",
    },
}
