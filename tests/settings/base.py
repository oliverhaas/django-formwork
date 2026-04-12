from pathlib import Path

SECRET_KEY = "django-formwork-test-secret-key"

MIDDLEWARE = ["django.contrib.sessions.middleware.SessionMiddleware"]
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django_iconx",
    "django_formwork",
    "e2e",
]

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    str(Path(__file__).resolve().parent.parent.parent / "django_formwork" / "static"),
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
