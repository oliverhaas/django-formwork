"""Generate cookbook screenshots from the running example app.

Prerequisites (run once, from examples/simple/):
    uv run python manage.py migrate
    uv run python manage.py formwork install
    npx @tailwindcss/cli -i app.css -o static/dist.css

Then:
    uv run python generate_screenshots.py

Writes docs/img/cookbook/step-{1..4}.png at the repo root.
"""

# ruff: noqa: INP001
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
OUT_DIR = REPO_ROOT / "docs" / "img" / "cookbook"
HOST = "127.0.0.1"
PORT = 8137
BASE = f"http://{HOST}:{PORT}"
VIEWPORT = {"width": 760, "height": 900}


def _wait_until_up(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)  # noqa: S310
        except OSError:
            time.sleep(0.3)
        else:
            return
    msg = f"server did not start at {url}"
    raise RuntimeError(msg)


def _open_assignee(page) -> None:
    """Open the assignee SearchSelect so its pre-rendered options (icon + email) show.

    Opens the <details>, clears the transient htmx ``hasError`` state (a headless
    timing artifact; the search endpoint works), and lets the absolutely-positioned
    dropdown content flow inside the card so the .card screenshot captures it.
    """
    page.evaluate(
        "const d = document.querySelector('details.search-select');"
        "if (d) { d.open = true; const a = window.Alpine && Alpine.$data(d); if (a) a.hasError = false; }",
    )
    page.add_style_tag(content=".dropdown-content { position: static !important; }")
    page.wait_for_timeout(400)


def _submit_duplicate_title(page) -> None:
    """Submit a title that already exists, so the server error morphs in."""
    page.fill("#id_title", "LEGACY")
    page.locator("#ticket-form button[type='submit']").click()
    page.wait_for_timeout(800)  # htmx morph swap
    # The error is a DaisyUI tooltip shown on hover; force it open for the shot.
    page.evaluate("document.querySelectorAll('.tooltip-error').forEach(t => t.classList.add('tooltip-open'))")
    page.wait_for_timeout(200)


def _shot(page, path: str, out_name: str, action=None) -> None:
    page.goto(f"{BASE}{path}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(400)  # Alpine + htmx init
    if action is not None:
        action(page)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page.locator(".card").first.screenshot(path=str(OUT_DIR / out_name), animations="disabled", caret="hide")


def main() -> int:
    server = subprocess.Popen(  # noqa: S603
        [sys.executable, "manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"],
        cwd=str(HERE),
    )
    try:
        _wait_until_up(f"{BASE}/cookbook/1/")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_context(viewport=VIEWPORT, device_scale_factor=1).new_page()
            _shot(page, "/cookbook/1/", "step-1.png")
            _shot(page, "/cookbook/2/", "step-2.png", _open_assignee)
            _shot(page, "/cookbook/3/", "step-3.png", _submit_duplicate_title)
            _shot(page, "/cookbook/4/", "step-4.png")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
    count = len(list(OUT_DIR.glob("step-*.png")))
    print(f"wrote {count} screenshots to {OUT_DIR}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
