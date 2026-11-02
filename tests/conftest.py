from __future__ import annotations

import asyncio
import contextlib
import re
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command

import django_formwork

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator

PACKAGE = Path(django_formwork.__file__).parent
MSGEN = shutil.which("msgen")

_MSGSTR = re.compile(r'^(msgstr(?:\[\d+\])?) "(.+)"$', re.MULTILINE)

_DIFF_OUTPUT_DIR = Path("test-results")
_PER_PIXEL_TOLERANCE = 10  # per-channel tolerance (out of 255)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """On PostgreSQL, add pg_trgm for the ranked search.

    Async tests query from asgiref's executor thread, whose open connection
    would keep the test database from being dropped, so close it last.
    """
    from asgiref.sync import sync_to_async
    from django.db import connection, connections

    if connection.vendor != "postgresql":
        yield
        return
    with django_db_blocker.unblock(), connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    yield
    with django_db_blocker.unblock():
        asyncio.run(sync_to_async(connections.close_all)())


def extract_messages(package: Path) -> str:
    """Run ``makemessages -l de`` on a copy of the package; returns the command's output."""
    shutil.copytree(PACKAGE, package, ignore=shutil.ignore_patterns("static", "__pycache__"))
    (package / "locale").mkdir()
    out = StringIO()
    with contextlib.chdir(package):
        call_command("makemessages", locale=["de"], no_wrap=True, stdout=out, stderr=out)
    return out.getvalue()


@pytest.fixture(scope="session")
def _pseudo_locale(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A German catalog that translates each extracted msgid to itself wrapped in ⟦⟧."""
    if not (shutil.which("xgettext") and MSGEN):
        pytest.skip("gettext is not installed")
    package = tmp_path_factory.mktemp("pseudo") / "django_formwork"
    extract_messages(package)
    po = package / "locale" / "de" / "LC_MESSAGES" / "django.po"
    english = subprocess.run([MSGEN, "--no-wrap", str(po)], capture_output=True, text=True, check=True).stdout  # noqa: S603
    po.write_text(_MSGSTR.sub(r'\1 "⟦\2⟧"', english))
    with contextlib.chdir(package):
        call_command("compilemessages", locale=["de"], use_fuzzy=True, verbosity=0)
    return package / "locale"


@pytest.fixture
def pseudo_catalog(_pseudo_locale: Path, settings) -> None:
    """Install the ⟦⟧ catalog for German, the way a project adds its own translations."""
    settings.LOCALE_PATHS = [str(_pseudo_locale)]


def pytest_addoption(parser):
    parser.addoption(
        "--update-screenshots",
        action="store_true",
        default=False,
        help="Regenerate screenshot baselines instead of comparing.",
    )


# ─── Screenshot comparison (shared by tests/widgets and tests/e2e) ────────


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
def assert_screenshot(pytestconfig: pytest.Config, request: pytest.FixtureRequest) -> Callable[[Locator, str], None]:
    """Assert a locator screenshot matches the baseline in the ``screenshots/`` dir next to the test module."""
    update_mode = pytestconfig.getoption("--update-screenshots", default=False)
    screenshots_dir = request.path.parent / "screenshots"

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
            # Absolute-positioned dropdowns overflow the locator's box; static keeps them inside it.
            no_anim += " .dropdown-content { position: static !important; }"
            # The position override can't reach the top layer; popovers
            # need their attribute removed to rejoin normal flow.
            locator.evaluate(
                "el => el.querySelectorAll('.dropdown-content[popover]').forEach(p => {"
                " p._formworkPopoverObserver?.disconnect();"
                " if (p.matches(':popover-open')) p.hidePopover();"
                " p.removeAttribute('popover'); })",
            )
        if padding:
            locator.evaluate(f"el => el.style.padding = '{padding}px'")
        actual_bytes = locator.screenshot(
            animations="disabled",
            caret="hide",
            style=no_anim,
        )

        baseline_path = screenshots_dir / name

        if update_mode:
            if baseline_path.exists():
                passed, _, _ = _compare_screenshots(actual_bytes, baseline_path, threshold=threshold)
                if passed:
                    return  # Existing baseline is close enough.
            screenshots_dir.mkdir(exist_ok=True)
            baseline_path.write_bytes(actual_bytes)
            return

        if not baseline_path.exists():
            screenshots_dir.mkdir(exist_ok=True)
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
