SECRET_KEY = "django-formwork-test-secret-key"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django_formwork",
]

STATIC_URL = "/static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
