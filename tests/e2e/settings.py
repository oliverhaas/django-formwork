"""Standalone settings for running the e2e views as a browsable example.

Usage:
    PYTHONPATH=tests uv run django-admin runserver --settings=e2e.settings
"""

import tempfile

from settings.base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "e2e.urls"
MEDIA_ROOT = tempfile.mkdtemp()
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    },
}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]
