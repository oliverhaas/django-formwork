"""Settings for mypy type checking (excludes e2e app).

mypy runs from the project root where the e2e package isn't importable,
so we duplicate base settings without the e2e app.
"""

SECRET_KEY = "django-formwork-test-secret-key"

MIDDLEWARE = ["django.contrib.sessions.middleware.SessionMiddleware"]
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django_formwork",
]

STATIC_URL = "/static/"

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
