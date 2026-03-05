"""Playwright e2e test fixtures.

The live_server fixture from pytest-django starts a real Django server.
We override Django settings for e2e-specific URL routing and templates.
"""

import os

import pytest

# Playwright runs an async event loop; Django blocks sync DB calls in async
# contexts by default.  This is safe for tests — the live_server runs in a
# separate thread.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


def submit(page):
    """Submit the form via htmx morph and wait for completion."""
    page.evaluate("document.querySelector('#widget-form').noValidate = true")
    page.locator("#widget-form button[type='submit']").click()
    page.wait_for_timeout(500)


@pytest.fixture(autouse=True)
def _e2e_settings(settings):
    """Override Django settings for e2e tests."""
    settings.ROOT_URLCONF = "e2e.urls"
    settings.TEMPLATES = [
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


@pytest.fixture
def widget_page(page, live_server):
    """Navigate to the widget test page and wait for Alpine + htmx init."""
    page.goto(f"{live_server.url}/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(300)  # Alpine.js init
    return page
