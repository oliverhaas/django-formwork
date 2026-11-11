"""Playwright e2e test fixtures.

The live_server fixture from pytest-django starts a real Django server.
We override Django settings for e2e-specific URL routing and templates.
"""

import io
import os
from pathlib import Path

import numpy as np
import pytest
from django.template import engines
from django.test import RequestFactory
from e2e.views import _page_html
from PIL import Image
from playwright.sync_api import expect

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
    """Navigate to a page containing the ToggleInput widget."""
    return _navigate(page, live_server, "/simple/")


@pytest.fixture
def select_page(page, live_server):
    """Navigate to the Select page."""
    return _navigate(page, live_server, "/select/")


@pytest.fixture
def select_multiple_page(page, live_server):
    """Navigate to the SelectMultiple page."""
    return _navigate(page, live_server, "/select-multiple/")


@pytest.fixture
def combobox_page(page, live_server):
    """Navigate to the ComboBox page."""
    return _navigate(page, live_server, "/combobox/")


@pytest.fixture
def dropdowns_page(page, live_server):
    """Navigate to the dropdown behaviour page."""
    return _navigate(page, live_server, "/dropdowns/")


@pytest.fixture
def read_only_page(page, live_server):
    """Navigate to the dropdowns inside a disabled fieldset."""
    return _navigate(page, live_server, "/read-only/")


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
    """Navigate to the new-widgets page (DatePicker, StepperNumberInput, OTP, InputMask)."""
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


@pytest.fixture
def autosave_dropdowns_page(page, live_server):
    """Navigate to the auto-saving form with a Select."""
    return _navigate(page, live_server, "/autosave-dropdowns/")


@pytest.fixture
def translated_page(page, live_server, pseudo_catalog):
    """Navigate to the page rendered in German, with formwork's strings from the ⟦⟧ catalog."""
    return _navigate(page, live_server, "/translated/")


@pytest.fixture
def sections_page(page, live_server):
    """Navigate to the section-forms page."""
    return _navigate(page, live_server, "/sections/")


_MORPH_PAGE = engines["django"].from_string(
    _page_html(
        "Morph",
        '<div class="card-body"><form id="morph_form" class="flex flex-col gap-5" data-revision="{{ revision }}" '
        'novalidate hx-post="" hx-trigger="save" hx-select="#morph_form" hx-swap="outerMorph">{{ form }}</form></div>',
    )
)
_CHANNEL_TOLERANCE = 8
_STRAY_PIXELS = 6
_CSS_IMAGES_LOADED = r"""() => [...document.querySelectorAll("*")]
    .filter((el) => el.checkVisibility())
    .flatMap((el) => {
        const style = getComputedStyle(el);
        return [...`${style.maskImage} ${style.backgroundImage}`.matchAll(/url\("(.+?)"\)/g)];
    })
    .every(([, url]) => url.startsWith("data:") || performance.getEntriesByName(url).length)"""
_NEXT_FRAME = "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"


class MorphPage:
    """A page with one form whose save the test answers.

    The answer renders the form bound to the posted data, like a view that validates on save."""

    def __init__(self, page, live_server, output):
        self.page = page
        self.live_server = live_server
        self.output = output
        self.form = page.locator("#morph_form")
        self.revision = 0
        self.reply = None
        self.errors = []
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.on("console", self._on_console)
        page.on("response", self._on_response)

    def open(self, form_class, data=None):
        """Load the page with the form, bound to ``data`` if given."""
        self.form_class = form_class
        self.data = data
        self.page.route(f"{self.live_server.url}/morph/", self._respond)
        self._load()

    def morph(self, data=None):
        """Save the form and wait until the answer is morphed in; it renders ``data``, else the posted data."""
        self.reply = data
        revision = self.revision + 1
        self.form.dispatch_event("save")
        expect(self.form).to_have_attribute("data-revision", str(revision))
        expect(self.page.locator(".htmx-request")).to_have_count(0)

    def assert_morph_keeps_state(self):
        """A save answered with what the user entered changes no pixel and replaces no node."""
        self.form.evaluate("form => form.querySelectorAll('*').forEach(el => el.morphProbe = true)")
        before = self._screenshot()
        self.morph()
        after = self._screenshot()
        replaced = self.form.evaluate(
            "form => [...form.querySelectorAll('*')].filter(el => !el.morphProbe).map(el => el.outerHTML.slice(0, 200))"
        )
        assert not self.errors
        assert not replaced, "The morph replaced nodes"
        self._assert_same(before, after, "before", "after")

    def assert_morph_shows(self, data):
        """A save answered with other data looks like a fresh load of that data, after the user left the field."""
        self.page.evaluate("document.activeElement?.blur()")
        self.morph(data)
        morphed = self._screenshot()
        self.data = data
        self._load()
        loaded = self._screenshot()
        assert not self.errors
        self._assert_same(morphed, loaded, "morphed", "loaded")

    def _on_console(self, message):
        if message.type == "error" and not message.text.startswith("Failed to load resource"):
            self.errors.append(message.text)

    def _on_response(self, response):
        if response.status >= 400:
            self.errors.append(f"{response.status} {response.url}")

    def _load(self):
        _navigate(self.page, self.live_server, "/morph/")
        self.page.evaluate("document.fonts.ready.then(() => true)")

    def _screenshot(self):
        """With the mouse off every control, after each visible icon, a CSS mask image, has loaded."""
        self.page.mouse.move(0, 0)
        self.page.wait_for_function(_CSS_IMAGES_LOADED)
        self.page.evaluate(_NEXT_FRAME)
        return self.page.screenshot(
            animations="disabled",
            caret="hide",
            style="*, *::before, *::after { transition: none !important; }",
        )

    def _assert_same(self, first, second, *names):
        """Allows a few stray pixels: under parallel load, two loads of one page can differ on a glyph edge."""
        a, b = (np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.int16) for png in (first, second))
        if a.shape == b.shape and (np.abs(a - b) > _CHANNEL_TOLERANCE).any(axis=2).sum() <= _STRAY_PIXELS:
            return
        self.output.mkdir(parents=True, exist_ok=True)
        for name, png in zip(names, (first, second), strict=True):
            (self.output / f"{name}.png").write_bytes(png)
        pytest.fail(f"The screens differ, see {self.output}")

    def _respond(self, route):
        data, files = self.data, None
        if route.request.method == "POST":
            self.revision += 1
            if self.reply is None:
                posted = RequestFactory().generic(
                    "POST",
                    "/morph/",
                    route.request.post_data_buffer or b"",
                    content_type=route.request.headers.get("content-type", ""),
                )
                data, files = posted.POST, posted.FILES
            else:
                data = self.reply
        form = self.form_class() if data is None else self.form_class(data, files)
        html = _MORPH_PAGE.render({"form": form, "revision": self.revision})
        route.fulfill(content_type="text/html", body=html)


@pytest.fixture
def morph_page(page, live_server, output_path):
    """A page whose one form the test defines, saved with a morph."""
    return MorphPage(page, live_server, Path(output_path))
