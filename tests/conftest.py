from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django import forms

from django_formwork.forms import FormworkForm
from django_formwork.widgets import MultiSelect, Range, Rating, Toggle

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator

_DIFF_OUTPUT_DIR = Path("test-results")
_PER_PIXEL_TOLERANCE = 10  # per-channel tolerance (out of 255)


def pytest_addoption(parser):
    parser.addoption(
        "--update-screenshots",
        action="store_true",
        default=False,
        help="Regenerate screenshot baselines instead of comparing.",
    )


class SimpleForm(forms.Form):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


class AllWidgetsForm(FormworkForm):
    text = forms.CharField()
    email = forms.EmailField()
    url = forms.URLField()
    number = forms.IntegerField()
    password = forms.CharField(widget=forms.PasswordInput)
    textarea = forms.CharField(widget=forms.Textarea)
    checkbox = forms.BooleanField(required=False)
    select = forms.ChoiceField(choices=[("a", "A"), ("b", "B")])
    radio = forms.ChoiceField(
        choices=[("x", "X"), ("y", "Y")],
        widget=forms.RadioSelect,
    )
    multi_checkbox = forms.MultipleChoiceField(
        choices=[("1", "One"), ("2", "Two")],
        widget=forms.CheckboxSelectMultiple,
    )
    date = forms.DateField()
    file = forms.FileField(required=False)
    hidden = forms.CharField(widget=forms.HiddenInput)
    color = forms.CharField(widget=forms.ColorInput, required=False)
    phone = forms.CharField(widget=forms.TelInput, required=False)
    search = forms.CharField(widget=forms.SearchInput, required=False)
    select_multiple = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=forms.SelectMultiple,
        required=False,
    )
    multi_select_dropdown = forms.MultipleChoiceField(
        choices=[("a", "A"), ("b", "B")],
        widget=MultiSelect,
        required=False,
    )


class CustomWidgetsForm(FormworkForm):
    toggle = forms.BooleanField(widget=Toggle, required=False)
    volume = forms.IntegerField(widget=Range(attrs={"min": "0", "max": "100"}))
    rating = forms.TypedChoiceField(
        choices=Rating.make_choices(5),
        coerce=int,
        widget=Rating,
    )


class SimpleFormworkForm(FormworkForm):
    name = forms.CharField(help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)


@pytest.fixture
def simple_form():
    return SimpleForm()


@pytest.fixture
def all_widgets_form():
    return AllWidgetsForm()


@pytest.fixture
def custom_widgets_form():
    return CustomWidgetsForm()


@pytest.fixture
def simple_formwork_form():
    return SimpleFormworkForm()


@pytest.fixture
def bound_form_with_errors():
    form = SimpleFormworkForm(data={"name": "", "email": "bad", "message": ""})
    form.is_valid()
    return form


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
