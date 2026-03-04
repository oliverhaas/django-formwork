"""Django settings for e2e (Playwright) tests."""

from .base import *  # noqa: F403

ROOT_URLCONF = "e2e.urls"

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
