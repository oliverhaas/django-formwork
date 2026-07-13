"""Playwright e2e test fixtures.

The live_server fixture from pytest-django starts a real Django server.
We override Django settings for e2e-specific URL routing and templates.
"""

import os

import pytest

# Playwright runs an async event loop; Django blocks sync DB calls in async
# contexts by default.  This is safe for tests, the live_server runs in a
# separate thread.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test under tests/e2e/ with the e2e marker.

    Without this hook, ``pytest -m "not e2e"`` would still collect these
    tests (they get a chromium fixture from pytest-playwright, but the
    marker is not applied implicitly).  The marker lets the publish gate
    skip browser-backed tests when no Playwright install is present.
    """
    for item in items:
        if "tests/e2e/" in str(item.fspath) or "tests\\e2e\\" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


def submit(page):
    """Submit the form via htmx morph and wait for the swap to complete."""
    # htmx 4 fires after:swap on the source element (the form) once all
    # main and OOB swaps are done; flag it so wait_for_function is race-free.
    page.evaluate(
        """() => {
            const form = document.querySelector('form[hx-post]');
            form.noValidate = true;
            window.__fwSubmitDone = false;
            form.addEventListener('htmx:after:swap', () => { window.__fwSubmitDone = true; }, {once: true});
        }""",
    )
    page.locator("form[hx-post] button[type='submit']").click()
    page.wait_for_function("window.__fwSubmitDone === true")


def _navigate(page, live_server, path):
    """Navigate to a page and wait for Alpine + htmx init."""
    page.goto(f"{live_server.url}{path}")
    page.wait_for_load_state("domcontentloaded")
    # Alpine 3 stamps _x_dataStack on every x-data root during start(),
    # so its presence on the first root means the whole tree is initialized.
    page.wait_for_function(
        """() => {
            if (!window.htmx || !window.Alpine) return false;
            const root = document.querySelector('[x-data]');
            return root === null || root._x_dataStack !== undefined;
        }""",
    )
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
def inline_errors_page(page, live_server):
    """Navigate to the inline errors (Meta.error_display = "inline") page."""
    return _navigate(page, live_server, "/inline-errors/")


@pytest.fixture
def tight_page(page, live_server):
    """Navigate to the tight form (Meta.error_display = "tooltip") page."""
    return _navigate(page, live_server, "/tight/")


@pytest.fixture
def toggle_page(page, live_server):
    """Navigate to a page containing the Toggle widget."""
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
def uploads_page(page, live_server):
    """Navigate to the file uploads page."""
    return _navigate(page, live_server, "/uploads/")


@pytest.fixture
def textarea_page(page, live_server):
    """Navigate to the ValidatedTextarea page."""
    return _navigate(page, live_server, "/textarea/")


@pytest.fixture
def new_widgets_page(page, live_server):
    """Navigate to the new-widgets page (DatePicker, InputNumber, OTP, InputMask)."""
    return _navigate(page, live_server, "/new-widgets/")


@pytest.fixture
def builtin_page(page, live_server):
    """Navigate to the built-in compound widgets page."""
    return _navigate(page, live_server, "/builtin/")


@pytest.fixture
def icon_modifiers_page(page, live_server):
    """Navigate to the icon modifiers demo page."""
    return _navigate(page, live_server, "/icon-modifiers/")


@pytest.fixture
def complex_page(page, live_server):
    """Navigate to the complex forms page."""
    return _navigate(page, live_server, "/complex/")


@pytest.fixture
def autosave_page(page, live_server):
    """Navigate to the auto-save form page."""
    return _navigate(page, live_server, "/autosave/")
