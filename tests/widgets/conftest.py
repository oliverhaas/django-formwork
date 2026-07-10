"""Shared fixtures and helpers for widget-level tests.

Unit and integration tests need no browser.  E2e and screenshot tests
re-export fixtures from ``tests/e2e/conftest.py`` since pytest does not
share conftest fixtures across sibling directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup, NavigableString, Tag

from django_formwork.renderers import FormworkJinja2Renderer, FormworkRenderer

# Re-export e2e fixtures and the autouse settings override so e2e widget
# tests in this directory can use them.  Listed in __all__ to satisfy
# ruff's unused-import check.
from tests.e2e.conftest import (  # noqa: F401
    _e2e_settings,
    basic_page,
    builtin_page,
    combobox_page,
    multi_select_page,
    search_select_page,
    simple_page,
    textarea_page,
    toggle_page,
    uploads_page,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.forms.renderers import BaseRenderer
    from playwright.sync_api import Locator

_SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
_DIFF_OUTPUT_DIR = Path("test-results")
_PER_PIXEL_TOLERANCE = 10  # per-channel tolerance (out of 255)


def render_widget(widget, name: str = "test", value=None, attrs: dict | None = None) -> BeautifulSoup:
    """Render a widget in isolation and return a BeautifulSoup tree."""
    html = widget.render(name, value, attrs=attrs)
    return BeautifulSoup(html, "html.parser")


def attach_server_search(
    widget,
    *,
    count: int | None = None,
    icons: bool = False,
    descriptions: bool = False,
    key: str | None = None,
) -> None:
    """Wire a SearchSelect/MultiSelect/ComboBox into the registry as if it were
    auto-registered, so unit tests can exercise the server-side rendering paths
    without going through a full FormworkForm.

    ``count`` populates a fake queryset whose ``.count()`` and slicing yield
    that many objects with ``label`` / ``icon`` / ``description`` attributes.
    """
    from django_formwork._registry import SearchRegistration, register

    key = key or f"tests.widget.{type(widget).__name__}.{id(widget)}"

    class _Obj:
        def __init__(self, i: int) -> None:
            self.pk = str(i)
            self.label = f"Item {i}"
            self.icon = f"\U0001f4cd{i}" if icons else ""
            self.description = f"desc {i}" if descriptions else ""

        def __str__(self) -> str:
            return self.label

    class _QS:
        def __init__(self, n: int) -> None:
            self._items = [_Obj(i) for i in range(n)]

        def count(self) -> int:
            return len(self._items)

        def all(self) -> _QS:
            return self

        def __getitem__(self, key):
            return self._items[key]

        def __iter__(self):
            return iter(self._items)

    n = count if count is not None else 0
    factory = (lambda: _QS(n)) if count is not None else None
    register(
        key,
        SearchRegistration(
            queryset_factory=factory,
            search_fields=("label",) if factory else (),
            label_from_instance=(lambda obj: obj.label) if factory else None,
            icon_from_instance=(lambda obj: obj.icon) if (factory and icons) else None,
            description_from_instance=(lambda obj: obj.description) if (factory and descriptions) else None,
        ),
    )
    widget._registry_key = key


def make_server_widget(
    widget_cls,
    *,
    count: int | None = 10,
    icons: bool = False,
    descriptions: bool = False,
    **kwargs,
):
    """Build a SearchSelect/MultiSelect/ComboBox already wired into the registry.

    Drop-in for tests that previously created a widget with ``search_url=``
    and expected server-side mode to be active.
    """
    widget = widget_cls(**kwargs)
    attach_server_search(widget, count=count, icons=icons, descriptions=descriptions)
    return widget


def render_form(form, renderer: BaseRenderer | None = None) -> BeautifulSoup:
    """Render a form via a formwork renderer and return a BeautifulSoup tree."""
    if renderer is not None:
        form.renderer = renderer
    return BeautifulSoup(str(form), "html.parser")


def _normalize(node: Tag | NavigableString) -> tuple:
    """Reduce an element to a comparable tuple, ignoring insignificant whitespace."""
    if isinstance(node, NavigableString):
        return ("text", " ".join(str(node).split()))
    children = [_normalize(c) for c in node.children if not (isinstance(c, NavigableString) and not str(c).strip())]
    return (node.name, dict(sorted(node.attrs.items())), children)


def assert_html_equivalent(a: Tag, b: Tag) -> None:
    """Assert two BeautifulSoup elements are equivalent, ignoring insignificant whitespace.

    Compares tag names, attribute dicts (order-insensitive), and children
    recursively.  Whitespace-only text nodes between elements are skipped.
    Text node whitespace is collapsed to single spaces.
    """
    norm_a = _normalize(a)
    norm_b = _normalize(b)
    assert norm_a == norm_b, f"HTML trees differ.\nA:\n{a}\n\nB:\n{b}"


@pytest.fixture(autouse=True)
def _clean_widget_registry():
    """Drop any registry entries created by ``attach_server_search`` so tests
    don't leak state across the module."""
    from django_formwork._registry import get_registry

    yield
    get_registry().clear()


@pytest.fixture(params=["dtl", "jinja2"], ids=["dtl", "jinja2"])
def renderer(request) -> FormworkRenderer | FormworkJinja2Renderer:
    """Parametrized renderer: each integration test runs against both engines."""
    if request.param == "dtl":
        return FormworkRenderer()
    return FormworkJinja2Renderer()


@pytest.fixture
def dtl_renderer() -> FormworkRenderer:
    return FormworkRenderer()


@pytest.fixture
def jinja2_renderer() -> FormworkJinja2Renderer:
    return FormworkJinja2Renderer()


def _compare_screenshots(
    actual_bytes: bytes,
    baseline_path: Path,
    threshold: float,
) -> tuple[bool, float, bytes | None]:
    """Compare a screenshot against a baseline image.

    Returns ``(passed, diff_ratio, diff_image_bytes)``.
    """
    import io

    import numpy as np
    from PIL import Image

    actual_img = Image.open(io.BytesIO(actual_bytes)).convert("RGBA")
    baseline_img = Image.open(baseline_path).convert("RGBA")

    if actual_img.size != baseline_img.size:
        return False, 1.0, _create_diff_image(actual_img, baseline_img)

    actual_arr = np.array(actual_img, dtype=np.int16)
    baseline_arr = np.array(baseline_img, dtype=np.int16)

    diff = np.abs(actual_arr - baseline_arr)
    pixel_differs = np.any(diff > _PER_PIXEL_TOLERANCE, axis=2)
    diff_count = int(np.sum(pixel_differs))
    total_pixels = actual_img.width * actual_img.height
    diff_ratio = diff_count / total_pixels

    passed = diff_ratio <= threshold
    diff_image_bytes = None if passed else _create_diff_image(actual_img, baseline_img)
    return passed, diff_ratio, diff_image_bytes


def _create_diff_image(actual_img, baseline_img) -> bytes:
    """Create a diff image highlighting changed pixels in red."""
    import io

    import numpy as np
    from PIL import Image

    width = max(actual_img.width, baseline_img.width)
    height = max(actual_img.height, baseline_img.height)

    actual_padded = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    actual_padded.paste(actual_img, (0, 0))
    baseline_padded = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    baseline_padded.paste(baseline_img, (0, 0))

    actual_arr = np.array(actual_padded, dtype=np.int16)
    baseline_arr = np.array(baseline_padded, dtype=np.int16)
    pixel_differs = np.any(np.abs(actual_arr - baseline_arr) > _PER_PIXEL_TOLERANCE, axis=2)

    result_arr = (np.array(actual_padded, dtype=np.float64) * 0.3).astype(np.uint8)
    result_arr[pixel_differs] = [255, 0, 0, 255]

    buf = io.BytesIO()
    Image.fromarray(result_arr, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def assert_screenshot(pytestconfig: pytest.Config) -> Callable[[Locator, str], None]:
    """Fixture providing a callable to assert locator screenshots match baselines.

    Usage in screenshot tests::

        def test_toggle_screenshot_default(toggle_page, assert_screenshot):
            wrapper = toggle_page.locator("#id_toggle_field")
            assert_screenshot(wrapper, "toggle-default.png")

    Pass ``--update-screenshots`` to regenerate baselines.
    """
    update_mode = pytestconfig.getoption("--update-screenshots", default=False)

    def _assert(
        locator: Locator,
        name: str,
        *,
        threshold: float = 0.002,
        padding: int = 8,
        capture_dropdown: bool = False,
    ) -> None:
        no_anim = "*, *::before, *::after { transition: none !important; animation: none !important; }"
        if capture_dropdown:
            # Dropdown content uses position:absolute and overflows the
            # parent's bounding box.  Making it static lets it flow
            # normally so the locator's box includes everything.
            no_anim += " .dropdown-content { position: static !important; }"
        # Add breathing room around the element for visual clarity.
        if padding:
            locator.evaluate(f"el => el.style.padding = '{padding}px'")
        actual_bytes = locator.screenshot(
            animations="disabled",
            caret="hide",
            style=no_anim,
        )

        baseline_path = _SCREENSHOTS_DIR / name

        if update_mode:
            if baseline_path.exists():
                passed, _, _ = _compare_screenshots(actual_bytes, baseline_path, threshold=threshold)
                if passed:
                    return  # Existing baseline is close enough.
            _SCREENSHOTS_DIR.mkdir(exist_ok=True)
            baseline_path.write_bytes(actual_bytes)
            return

        if not baseline_path.exists():
            _SCREENSHOTS_DIR.mkdir(exist_ok=True)
            baseline_path.write_bytes(actual_bytes)
            pytest.skip(f"No baseline for '{name}'; created new baseline.")
            return

        passed, diff_ratio, diff_image = _compare_screenshots(
            actual_bytes,
            baseline_path,
            threshold=threshold,
        )
        if passed:
            return

        safe_name = name.rsplit(".", 1)[0]
        _DIFF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (_DIFF_OUTPUT_DIR / f"{safe_name}-actual.png").write_bytes(actual_bytes)
        (_DIFF_OUTPUT_DIR / f"{safe_name}-baseline.png").write_bytes(baseline_path.read_bytes())
        if diff_image:
            (_DIFF_OUTPUT_DIR / f"{safe_name}-diff.png").write_bytes(diff_image)

        pytest.fail(
            f"Screenshot '{name}' differs from baseline by {diff_ratio:.4%} "
            f"(threshold: {threshold:.4%}). "
            f"Diff saved to {_DIFF_OUTPUT_DIR / safe_name}-diff.png",
        )

    return _assert
