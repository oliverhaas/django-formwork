from pathlib import Path

import pytest


@pytest.mark.unit
def test_py_typed_marker_exists():
    """py.typed marker file exists for PEP 561 compliance."""
    marker = Path(__file__).parent.parent / "django_formwork" / "py.typed"
    assert marker.exists()
