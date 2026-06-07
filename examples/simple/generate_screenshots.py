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


def _shot(page, path: str, out_name: str, *, open_dropdown: bool = False) -> None:
    page.goto(f"{BASE}{path}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(400)  # Alpine + htmx init
    if open_dropdown:
        page.locator("details.dropdown, .dropdown").first.click()
        page.wait_for_timeout(400)
    card = page.locator(".card").first
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card.screenshot(path=str(OUT_DIR / out_name), animations="disabled", caret="hide")


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
            _shot(page, "/cookbook/2/", "step-2.png", open_dropdown=True)
            _shot(page, "/cookbook/3/", "step-3.png")
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
