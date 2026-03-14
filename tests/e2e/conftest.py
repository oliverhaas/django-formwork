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


def _navigate(page, live_server, path):
    """Navigate to a page and wait for Alpine + htmx init."""
    page.goto(f"{live_server.url}{path}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(300)  # Alpine.js init
    return page


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
def basic_page(page, live_server):
    """Navigate to the basic forms page."""
    return _navigate(page, live_server, "/basic/")


@pytest.fixture
def elements_page(page, live_server):
    """Navigate to the standalone elements page."""
    return _navigate(page, live_server, "/elements/")


@pytest.fixture
def simple_page(page, live_server):
    """Navigate to the simple custom widgets page."""
    return _navigate(page, live_server, "/simple/")


@pytest.fixture
def search_select_page(page, live_server):
    """Navigate to the SearchSelect page."""
    return _navigate(page, live_server, "/search-select/")


@pytest.fixture
def multi_select_page(page, live_server):
    """Navigate to the MultiSelect page."""
    return _navigate(page, live_server, "/multi-select/")


@pytest.fixture
def combobox_page(page, live_server):
    """Navigate to the ComboBox page."""
    return _navigate(page, live_server, "/combobox/")


@pytest.fixture
def rating_page(page, live_server):
    """Navigate to the Rating page."""
    return _navigate(page, live_server, "/rating/")


@pytest.fixture
def uploads_page(page, live_server):
    """Navigate to the file uploads page."""
    return _navigate(page, live_server, "/uploads/")


@pytest.fixture
def textarea_page(page, live_server):
    """Navigate to the ValidatedTextarea page."""
    return _navigate(page, live_server, "/textarea/")


@pytest.fixture
def complex_page(page, live_server):
    """Navigate to the complex forms page."""
    return _navigate(page, live_server, "/complex/")
