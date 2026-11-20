"""Django settings for the full example project (task manager)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "example-only-not-for-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.forms",
    "django_iconx",
    "django_filters",
    "django_nplus1",
    "django_formwork",
    "django_formwork.admin",
    "taskmanager",
    "people",
    "crm",
    "billing",
    "helpdesk",
    "recruiting",
    "events",
    "content",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Logs a relation that the rows of a page load one at a time; the tests raise instead.
    "django_nplus1.NPlus1Middleware",
]

ROOT_URLCONF = "taskmanager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "taskmanager.context_processors.nav",
            ],
        },
    },
]

FORM_RENDERER = "django_formwork.FormworkRenderer"

FORMWORK_ADMIN_SITE = "taskmanager.admin_site.TaskworkAdminSite"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

# With TASKWORK_POSTGRES set to a database name, the example runs on PostgreSQL and
# django-pghistory records a few models (the audit app). The README has the setup.
if TASKWORK_POSTGRES := os.environ.get("TASKWORK_POSTGRES"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": TASKWORK_POSTGRES}}
    INSTALLED_APPS += ["pgtrigger", "pghistory", "audit"]
    # migrate installs the triggers, so the apps' own migrations stay the same on SQLite.
    PGTRIGGER_MIGRATIONS = False
    PGTRIGGER_INSTALL_ON_MIGRATE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
