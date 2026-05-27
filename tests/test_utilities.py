"""Tests for internal utility functions in django_formwork.widgets."""

import pytest

from django_formwork.widgets._base import _format_accept, _format_size

# ─── _format_size ───────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (1, "1 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1 KB"),
        (1536, "1.5 KB"),
        (2048, "2 KB"),
        (10240, "10 KB"),
        (1024 * 1024, "1 MB"),
        (1024 * 1024 + 512 * 1024, "1.5 MB"),
        (5 * 1024 * 1024, "5 MB"),
        (10 * 1024 * 1024, "10 MB"),
    ],
)
def test_format_size(size, expected):
    assert _format_size(size) == expected


# ─── _format_accept ─────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("accept", "expected"),
    [
        ("image/*", "Images"),
        ("video/*", "Videos"),
        ("audio/*", "Audios"),
        (".png", "PNG"),
        (".png,.jpg,.jpeg", "PNG, JPG, JPEG"),
        ("application/pdf", "PDF"),
        (".doc,.pdf", "DOC, PDF"),
        ("image/*,.pdf", "Images, PDF"),
        (".PNG", "PNG"),
    ],
)
def test_format_accept(accept, expected):
    assert _format_accept(accept) == expected


@pytest.mark.unit
def test_format_accept_empty():
    assert _format_accept("") == ""


@pytest.mark.unit
def test_format_accept_whitespace_only():
    assert _format_accept("   ") == ""


@pytest.mark.unit
def test_format_accept_strips_whitespace():
    assert _format_accept(" .png , .jpg ") == "PNG, JPG"
